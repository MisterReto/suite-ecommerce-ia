"""Read-only resolution of existing Drive images. Naming is unchanged."""
from __future__ import annotations
import os
import re
from typing import Any
IMAGES_FOLDER_ID = os.getenv("DRIVE_IMAGES_FOLDER_ID", "").strip()

def parse_image_names(value: Any) -> list[str]:
    return [part.strip() for part in re.split(r"[,;\n]+", str(value or "")) if part.strip()]


def list_drive_images(drive_service, folder_id: str | None = None) -> dict[str, dict[str, Any]]:
    """Lista la carpeta elegida por el usuario; nunca usa un ID ajeno por defecto."""
    folder_id = str(folder_id or IMAGES_FOLDER_ID or "").strip()
    if not folder_id:
        raise ValueError(
            "No se configuró la carpeta imagenes_generadas para esta sesión."
        )
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
    resolved: list[dict[str, Any]] = []
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
            "optional_legacy": False,
        })

    canonical_three_present = len(resolved) >= 3 and all(r.get("drive_file") for r in resolved[:3])
    if canonical_three_present:
        for ref in resolved[3:]:
            if not ref.get("drive_file"):
                ref["optional_legacy"] = True
                ref["resolution"] = "optional_legacy_missing"
    return resolved
