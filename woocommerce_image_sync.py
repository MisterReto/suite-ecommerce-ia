"""Resolución y sincronización de imágenes Drive -> WordPress -> WooCommerce.

- `Lista completa.imagenes` es la fuente de verdad para los nombres solicitados.
- Si un nombre legacy SKU_1.png/SKU_2.png/SKU_3.png no existe, se intenta el
  patrón actual de la app: _1_hd.jpg, _2_uso.jpg, _3_comercial.jpg.
- Media Sync evita subir dos veces el mismo archivo de Drive.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import io
import os
import re
from typing import Any, Callable

from googleapiclient.http import MediaIoBaseDownload

from wordpress_media import WordPressMediaClient
from woocommerce_client import WooCommerceClient

IMAGES_FOLDER_ID = os.getenv("DRIVE_IMAGES_FOLDER_ID", "1V4HgnTCRnwVGwrGD968eNdtvQDGGY7wt").strip()
MEDIA_SYNC_SHEET = "Media Sync"
MEDIA_SYNC_COLUMNS = (
    "timestamp", "sku", "requested_filename", "resolved_filename", "drive_file_id",
    "wp_media_id", "wp_media_url", "status", "note",
)


def parse_image_names(value: Any) -> list[str]:
    return [part.strip() for part in re.split(r"[,;\n]+", str(value or "")) if part.strip()]


def list_drive_images(drive_service, folder_id: str = IMAGES_FOLDER_ID) -> dict[str, dict[str, Any]]:
    """Lista toda la carpeta una sola vez; índice case-insensitive por nombre."""
    files: dict[str, dict[str, Any]] = {}
    token = None
    while True:
        response = drive_service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            spaces="drive",
            pageSize=1000,
            pageToken=token,
            fields="nextPageToken,files(id,name,mimeType,size,modifiedTime)",
        ).execute()
        for item in response.get("files", []):
            name = str(item.get("name") or "").strip()
            if name:
                files[name.casefold()] = item
        token = response.get("nextPageToken")
        if not token:
            break
    return files


def fallback_names(sku: str, position: int) -> list[str]:
    sku = str(sku or "").strip()
    if position == 0:
        return [f"{sku}_1_hd.jpg", f"{sku}_1.jpg", f"{sku}_1.png"]
    if position == 1:
        return [f"{sku}_2_uso.jpg", f"{sku}_2.jpg", f"{sku}_2.png"]
    if position == 2:
        return [f"{sku}_3_comercial.jpg", f"{sku}_3.jpg", f"{sku}_3.png"]
    return []


def resolve_product_images(row: dict[str, Any], drive_index: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    sku = str(row.get("sku") or "").strip()
    requested = parse_image_names(row.get("imagenes"))
    resolved = []
    for position, requested_name in enumerate(requested):
        item = drive_index.get(requested_name.casefold())
        method = "exact"
        resolved_name = requested_name
        if item is None:
            for candidate in fallback_names(sku, position):
                item = drive_index.get(candidate.casefold())
                if item:
                    method = "fallback"
                    resolved_name = candidate
                    break
        resolved.append({
            "position": position,
            "requested_filename": requested_name,
            "resolved_filename": resolved_name if item else "",
            "drive_file": item,
            "resolution": method if item else "missing",
        })
    return resolved


def ensure_media_sync_sheet(sheets_service, spreadsheet_id: str) -> int:
    book = sheets_service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets(properties(sheetId,title))",
    ).execute()
    sheets = {s["properties"]["title"]: s["properties"]["sheetId"] for s in book.get("sheets", [])}
    gid = sheets.get(MEDIA_SYNC_SHEET)
    if gid is None:
        response = sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": MEDIA_SYNC_SHEET}}}]},
        ).execute()
        gid = response["replies"][0]["addSheet"]["properties"]["sheetId"]
    sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{MEDIA_SYNC_SHEET}'!A1:I1",
        valueInputOption="RAW",
        body={"values": [list(MEDIA_SYNC_COLUMNS)]},
    ).execute()
    return gid


def read_media_cache(sheets_service, spreadsheet_id: str) -> dict[str, dict[str, Any]]:
    ensure_media_sync_sheet(sheets_service, spreadsheet_id)
    values = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{MEDIA_SYNC_SHEET}'!A:I",
        valueRenderOption="UNFORMATTED_VALUE",
    ).execute().get("values", [])
    if len(values) < 2:
        return {}
    headers = [str(v) for v in values[0]]
    cache = {}
    for raw in values[1:]:
        row = list(raw) + [""] * max(0, len(headers) - len(raw))
        data = dict(zip(headers, row[:len(headers)]))
        file_id = str(data.get("drive_file_id") or "").strip()
        if file_id and str(data.get("wp_media_id") or "").strip():
            cache[file_id] = data
    return cache


def append_media_log(sheets_service, spreadsheet_id: str, values: list[list[Any]]) -> None:
    if not values:
        return
    ensure_media_sync_sheet(sheets_service, spreadsheet_id)
    sheets_service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"'{MEDIA_SYNC_SHEET}'!A:I",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": values},
    ).execute()


def build_image_preview(rows: list[dict[str, Any]], drive_index: dict[str, dict[str, Any]],
                        wc_index: dict[str, dict[str, Any]], duplicate_skus: dict[str, Any],
                        media_cache: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    media_cache = media_cache or {}
    summary = {
        "products": len(rows), "with_images": 0, "without_images": 0,
        "requested_files": 0, "exact_files": 0, "fallback_files": 0,
        "missing_files": 0, "already_uploaded": 0, "ready_files": 0,
        "ready_products": 0, "missing_wc_products": 0, "duplicate_wc_skus": len(duplicate_skus),
    }
    result = []
    for row in rows:
        sku = str(row.get("sku") or "").strip()
        refs = resolve_product_images(row, drive_index)
        if refs:
            summary["with_images"] += 1
        else:
            summary["without_images"] += 1
        summary["requested_files"] += len(refs)
        for ref in refs:
            if ref["resolution"] == "exact":
                summary["exact_files"] += 1
            elif ref["resolution"] == "fallback":
                summary["fallback_files"] += 1
            else:
                summary["missing_files"] += 1
            drive_file = ref.get("drive_file")
            if drive_file and str(drive_file.get("id")) in media_cache:
                summary["already_uploaded"] += 1
            elif drive_file:
                summary["ready_files"] += 1
        wc = wc_index.get(sku)
        duplicate = sku in duplicate_skus
        if wc is None:
            summary["missing_wc_products"] += 1
        all_found = bool(refs) and all(r.get("drive_file") for r in refs)
        ready = all_found and wc is not None and not duplicate
        if ready:
            summary["ready_products"] += 1
        result.append({
            "sku": sku,
            "name": row.get("nombre_producto", ""),
            "images": refs,
            "wc_entity_type": wc.get("_entity_type") if wc else None,
            "wc_id": wc.get("id") if wc else None,
            "parent_id": wc.get("_parent_product_id") if wc else None,
            "duplicate": duplicate,
            "ready": ready,
        })
    return {"summary": summary, "rows": result}


def _download_drive_file(drive_service, file_id: str) -> bytes:
    request = drive_service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request, chunksize=1024 * 1024)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue()


def sync_one_product_images(
    *, row: dict[str, Any], drive_index: dict[str, dict[str, Any]], media_cache: dict[str, dict[str, Any]],
    drive_factory: Callable[[], Any], sheets_service, spreadsheet_id: str,
    wp_client: WordPressMediaClient, wc_client: WooCommerceClient, wc_entity: dict[str, Any],
    max_workers: int = 3,
) -> dict[str, Any]:
    """Sube medios faltantes en paralelo y asigna imágenes al SKU. Requiere ambos write gates."""
    if not wp_client.write_enabled:
        raise RuntimeError("WP_MEDIA_WRITE_ENABLED=false")
    if not wc_client.config.write_enabled:
        raise RuntimeError("WC_WRITE_ENABLED=false")

    sku = str(row.get("sku") or "").strip()
    refs = resolve_product_images(row, drive_index)
    if not refs:
        raise ValueError(f"{sku} no tiene nombres en la columna imagenes.")
    missing = [r["requested_filename"] for r in refs if not r.get("drive_file")]
    if missing:
        raise ValueError(f"Faltan archivos en Drive para {sku}: {', '.join(missing)}")

    media_ids: dict[int, int] = {}
    logs: list[list[Any]] = []

    def upload_ref(ref: dict[str, Any]):
        drive_file = ref["drive_file"]
        file_id = str(drive_file["id"])
        cached = media_cache.get(file_id)
        if cached:
            return ref["position"], int(float(cached["wp_media_id"])), cached.get("wp_media_url", ""), "cache"

        filename = ref["resolved_filename"]
        existing = wp_client.find_media_by_filename(filename)
        if existing:
            return ref["position"], int(existing["id"]), existing.get("source_url", ""), "wordpress_existing"

        drive_service = drive_factory()
        data = _download_drive_file(drive_service, file_id)
        uploaded = wp_client.upload_media(
            filename,
            data,
            mime_type=drive_file.get("mimeType"),
            alt_text=str(row.get("nombre_producto") or ""),
            title=str(row.get("nombre_producto") or sku),
        )
        return ref["position"], int(uploaded["id"]), uploaded.get("source_url", ""), "uploaded"

    workers = max(1, min(max_workers, len(refs)))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="wp-media") as executor:
        futures = {executor.submit(upload_ref, ref): ref for ref in refs}
        for future in as_completed(futures):
            ref = futures[future]
            position, media_id, media_url, status = future.result()
            media_ids[position] = media_id
            df = ref["drive_file"]
            logs.append([
                datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"), sku,
                ref["requested_filename"], ref["resolved_filename"], df["id"], media_id,
                media_url, status, ref["resolution"],
            ])

    ordered_ids = [media_ids[i] for i in sorted(media_ids)]
    entity_type = wc_entity.get("_entity_type")
    if entity_type == "variation":
        # WooCommerce core permite una imagen destacada por variación.
        wc_client.update_variation(int(wc_entity["_parent_product_id"]), int(wc_entity["id"]), {"image": {"id": ordered_ids[0]}})
        assigned = [ordered_ids[0]]
        note = "Variación: se asignó la primera imagen; las demás quedaron en Media Library."
    else:
        wc_client.update_product(int(wc_entity["id"]), {"images": [{"id": mid, "position": pos} for pos, mid in enumerate(ordered_ids)]})
        assigned = ordered_ids
        note = "Producto: imagen principal + galería asignadas."

    append_media_log(sheets_service, spreadsheet_id, logs)
    return {"sku": sku, "uploaded_or_reused": len(ordered_ids), "assigned_media_ids": assigned, "note": note}
