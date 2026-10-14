"""Classification choices from the connected Drive inventory; no writes."""
# Lectura de categorías, subcategorías y etiquetas del inventario conectado; no escribe ni crea archivos.
# Guía: docs/CODE_GUIDE.md; funciones y objetos: docs/FUNCTION_INDEX.md.
from catalog_capture import text
from inventory_schema import split_category_path
import os
import re
from googleapiclient.errors import HttpError


# Descubre y lee el inventario existente dentro de la carpeta autorizada; evita el adaptador
# que crea/sincroniza hojas.
def read_inventory(runtime, value):
    """Discover an existing inventory without the create/synchronize adapter."""
    service = runtime._get_drive_service(value)
    root = value.get("carpeta_raiz_id_manual") or value.get("platform_tenant") or os.getenv("GOOGLE_DRIVE_FOLDER_ID")
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
        return service, None, []
    if not re.fullmatch(r"[A-Za-z0-9_-]+", root):
        raise ValueError("Carpeta Drive inválida.")
    from drive_service import DriveService
    boundary = DriveService(service, root)
    sheet = os.getenv("GOOGLE_SHEET_ID")
    configured_sheet = bool(sheet)
    try:
        owns_configured = boundary.owns(sheet) if sheet else False
    except HttpError as error:
        if error.resp.status not in {403, 404}:
            raise
        owns_configured = False
    if sheet and not owns_configured:
        sheet = None
        configured_sheet = False
    sheet = sheet or runtime._buscar_archivo(
        service, runtime.NOMBRE_GOOGLE_SHEET, root, "application/vnd.google-apps.spreadsheet")
    if not sheet:
        return service, None, []
    if configured_sheet and boundary.metadata(sheet).get("mimeType") != "application/vnd.google-apps.spreadsheet":
        raise ValueError("La hoja no pertenece a la carpeta autorizada.")
    rows = runtime._leer_google_sheet(runtime._get_sheets_service(value), sheet).to_dict("records")
    return service, sheet, rows


def read_rows(runtime, value):
    return read_inventory(runtime, value)[2]


# Extrae categoría/subcategoría tanto del camino combinado como de columnas históricas.
def classification(row):
    category, subcategory = split_category_path(text(row.get("categorias")))
    return category or text(row.get("categoria")), subcategory or text(row.get("subcategoria"))


# Construye opciones únicas de Drive, conserva ortografía y relaciona subcategorías con su
# categoría; defaults solo para datos ausentes.
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
