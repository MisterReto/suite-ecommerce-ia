"""Prepara medios para un producto sin hacer PUT a WooCommerce.

Sync Lite carga `Media Sync` una vez al inicio del lote; aquí solo anexamos las
filas nuevas directamente para evitar revalidar la pestaña en cada SKU.
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
        raise ValueError(f"{sku} no tiene nombres en la columna imagenes.")

    required_missing = [
        r["requested_filename"] for r in refs
        if not r.get("drive_file") and not r.get("optional_legacy")
    ]
    if required_missing:
        raise ValueError(
            f"Faltan archivos obligatorios en Drive para {sku}: {', '.join(required_missing)}"
        )

    ordered_ids: list[int] = []
    logs: list[list[Any]] = []
    reused = 0
    uploaded_count = 0

    for ref in [r for r in refs if r.get("drive_file")]:
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
            existing = wp_client.find_media_by_filename(filename)
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
                    alt_text=str(row.get("nombre_producto") or ""),
                    title=str(row.get("nombre_producto") or sku),
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
        raise ValueError(f"No hay imágenes resolubles en Drive para {sku}.")

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
        "backend_verified": None,
        "note": "Medios preparados; WooCommerce se actualizará en el PUT final del producto.",
    }
