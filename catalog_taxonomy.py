"""Classification choices from the connected Drive inventory; no writes."""
from catalog_capture import text
from inventory_schema import split_category_path
import os
import re


def read_rows(runtime, value):
    """Discover an existing inventory without the create/synchronize adapter."""
    service = runtime._get_drive_service(value)
    root = value.get("platform_tenant") or value.get("carpeta_raiz_id_manual") or os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    if not root:
        name = runtime.NOMBRE_CARPETA_RAIZ.replace("\\", "\\\\").replace("'", "\\'")
        folders = service.files().list(
            q=f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
            fields="files(id)", pageSize=100, supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute().get("files", [])
        if len(folders) > 1:
            raise ValueError("Selecciona la carpeta del proyecto por ID.")
        root = folders[0]["id"] if folders else None
    if not root:
        return []
    if not re.fullmatch(r"[A-Za-z0-9_-]+", root):
        raise ValueError("Carpeta Drive inválida.")
    sheet = os.getenv("GOOGLE_SHEET_ID") or runtime._buscar_archivo(
        service, runtime.NOMBRE_GOOGLE_SHEET, root, "application/vnd.google-apps.spreadsheet")
    if not sheet:
        return []
    if os.getenv("GOOGLE_SHEET_ID"):
        from drive_service import DriveService
        boundary = DriveService(service, root)
        if not boundary.owns(sheet) or boundary.metadata(sheet).get("mimeType") != "application/vnd.google-apps.spreadsheet":
            raise ValueError("La hoja no pertenece a la carpeta autorizada.")
    return runtime._leer_google_sheet(runtime._get_sheets_service(value), sheet).to_dict("records")


def classification(row):
    category, subcategory = split_category_path(text(row.get("categorias")))
    return category or text(row.get("categoria")), subcategory or text(row.get("subcategoria"))


def choices_from_rows(rows, default_categories=(), default_subcategories=()):
    categories, subcategories, tags = set(), {}, set()
    for row in rows:
        category, subcategory = classification(row)
        if category:
            categories.add(category)
        if subcategory:
            subcategories.setdefault(category, set()).add(subcategory)
        tags.update(tag.strip() for tag in text(row.get("etiquetas")).split(",") if tag.strip())
    has_existing = bool(categories or subcategories or tags)
    if not categories:
        categories.update(default_categories)
    if not subcategories and not has_existing:
        subcategories[""] = set(default_subcategories)
    return {"source": "drive" if has_existing else "defaults",
            "categories": sorted(categories, key=str.casefold),
            "subcategories": {key: sorted(values, key=str.casefold) for key, values in subcategories.items()},
            "tags": sorted(tags, key=str.casefold)}
