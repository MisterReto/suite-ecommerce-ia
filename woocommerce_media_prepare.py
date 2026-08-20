"""Prepara medios para un producto sin hacer PUT a WooCommerce.

Sync Lite carga `Media Sync` una vez al inicio del lote; aquí solo anexamos las
filas nuevas directamente para evitar revalidar la pestaña en cada SKU.

Regla importante para catálogo legacy:
- si existe un set generado completo/resoluble, se prepara para reemplazar las imágenes;
- si faltan imágenes generadas obligatorias, NO se bloquea el producto: se devuelve
  `assigned_media_ids=[]` y el PUT final conserva las imágenes actuales de WooCommerce.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from wordpress_media import WordPressMediaClient
from woocommerce_image_sync import (
    MEDIA_SYNC_SHEET,
    _download_drive_file,
    resolve_product_images,
)


def _append_logs_fast(sheets_service, spreadsheet_id: str, values: list[list[Any]]) -> None:
    if not values:
        return
    sheets_service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"'{MEDIA_SYNC_SHEET}'!A:I",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": values},
    ).execute()


def _skip_images(sku: str, reason: str, missing: list[str] | None = None) -> dict[str, Any]:
    """Resultado no fatal: producto se sincroniza sin tocar las imágenes remotas."""
    return {
        "sku": sku,
        "assigned_media_ids": [],
        "uploaded": 0,
        "reused": 0,
        "optional_legacy_ignored": 0,
        "images_skipped": True,
        "missing_images": list(missing or []),
        "backend_verified": None,
        "note": reason,
    }


def prepare_product_media(
    *,
    row: dict[str, Any],
    drive_index: dict[str, dict[str, Any]],
    media_cache: dict[str, dict[str, Any]],
    drive_factory: Callable[[], Any],
    sheets_service,
    spreadsheet_id: str,
    wp_client: WordPressMediaClient,
) -> dict[str, Any]:
    if not wp_client.write_enabled:
        raise RuntimeError("WP_MEDIA_WRITE_ENABLED=false")

    sku = str(row.get("sku") or "").strip()
    refs = resolve_product_images(row, drive_index)
    if not refs:
        return _skip_images(
            sku,
            "El producto no tiene nombres de imagen en Lista completa; se conservarán las imágenes actuales de WooCommerce.",
        )

    required_missing = [
        r["requested_filename"] for r in refs
        if not r.get("drive_file") and not r.get("optional_legacy")
    ]
    if required_missing:
        return _skip_images(
            sku,
            "No existe un set generado completo en Drive; se sincronizará el producto sin reemplazar sus imágenes actuales.",
            required_missing,
        )

    sync_refs = [r for r in refs if r.get("drive_file")]
    if not sync_refs:
        return _skip_images(
            sku,
            "No hay archivos de imagen resolubles en Drive; se conservarán las imágenes actuales de WooCommerce.",
        )

    uncached_names = [
        r["resolved_filename"]
        for r in sync_refs
        if str(r["drive_file"]["id"]) not in media_cache
    ]
    # Una sola búsqueda WordPress para todas las imágenes del SKU.
    existing_by_name = wp_client.find_media_by_filenames(uncached_names) if uncached_names else {}

    ordered_ids: list[int] = []
    logs: list[list[Any]] = []
    reused = 0
    uploaded_count = 0

    for ref in sync_refs:
        drive_file = ref["drive_file"]
        file_id = str(drive_file["id"])
        cached = media_cache.get(file_id)
        if cached and str(cached.get("wp_media_id") or "").strip():
            media_id = int(float(cached["wp_media_id"]))
            media_url = str(cached.get("wp_media_url") or "")
            status = "cache"
            reused += 1
        else:
            filename = ref["resolved_filename"]
            existing = existing_by_name.get(filename.casefold())
            if existing:
                media_id = int(existing["id"])
                media_url = str(existing.get("source_url") or "")
                status = "wordpress_existing"
                reused += 1
            else:
                data = _download_drive_file(drive_factory(), file_id)
                uploaded = wp_client.upload_media(
                    filename,
                    data,
                    mime_type=drive_file.get("mimeType"),
                    # El PUT final del producto asigna las imágenes. Evitamos una
                    # segunda petición por medio solo para metadata durante lotes.
                    alt_text="",
                    title="",
                )
                media_id = int(uploaded["id"])
                media_url = str(uploaded.get("source_url") or "")
                status = "uploaded"
                uploaded_count += 1
                del data

            media_cache[file_id] = {
                "drive_file_id": file_id,
                "wp_media_id": media_id,
                "wp_media_url": media_url,
            }

        ordered_ids.append(media_id)
        logs.append([
            datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            sku,
            ref["requested_filename"],
            ref["resolved_filename"],
            file_id,
            media_id,
            media_url,
            status,
            ref["resolution"],
        ])

    if not ordered_ids:
        return _skip_images(
            sku,
            "No se obtuvo ningún medio válido; se conservarán las imágenes actuales de WooCommerce.",
        )

    _append_logs_fast(sheets_service, spreadsheet_id, logs)
    optional_ignored = sum(
        1 for r in refs if r.get("optional_legacy") and not r.get("drive_file")
    )
    return {
        "sku": sku,
        "assigned_media_ids": ordered_ids,
        "uploaded": uploaded_count,
        "reused": reused,
        "optional_legacy_ignored": optional_ignored,
        "images_skipped": False,
        "missing_images": [],
        "backend_verified": None,
        "note": "Medios preparados; WooCommerce se actualizará en el PUT final del producto.",
    }
