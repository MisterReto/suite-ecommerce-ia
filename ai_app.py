"""Canonical Google Sheets adapters, imported normally by the FastAPI backend."""
from __future__ import annotations
import threading
import pandas as pd
import app as legacy
from catalog_capture import records_from_values, prepare_capture_updates
from inventory_schema import MASTER_COLUMNS, MASTER_SHEET, split_category_path
from sheets_service import SheetsService

_sheets_client = legacy._get_sheets_service


def sheets_for_session(session):
    client = _sheets_client(session)
    return client if isinstance(client, SheetsService) else SheetsService(client)


legacy._get_sheets_service = sheets_for_session


def _clean(value):
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return "" if value is None else value


def _canonical_row(record):
    get = record.get
    raw_kind = str(_clean(get("tipo", "simple")) or "simple").strip().casefold()
    sku = str(_clean(get("sku", "")) or "").strip()
    parent = str(_clean(get("sku_padre", "")) or "").strip()

    aliases = {
        "simple": "simple",
        "variable": "variable",
        "variation": "variation",
        "variación": "variation",
        "variacion": "variation",
        "variante": "variation",
    }
    kind = aliases.get(raw_kind, "variation" if parent else "simple")
    # La interfaz heredada llama "Variable" a una fila hija. Si trae SKU padre,
    # se guarda con el tipo real que WooCommerce espera: variation.
    if sku.upper().endswith("FULL"):
        kind = "variable"
    elif kind == "variable" and parent:
        kind = "variation"
    if kind != "variation":
        parent = ""

    category_path = str(_clean(get("categorias", "")) or "").strip()
    if not category_path:
        cat = str(_clean(get("categoria", "")) or "").strip()
        sub = str(_clean(get("subcategoria", "")) or "").strip()
        category_path = f"{cat} > {sub}" if cat and sub else (cat or sub)

    stock = _clean(get("Existencias", 0))
    try:
        stock = max(0, int(float(stock or 0)))
    except Exception:
        stock = 0

    return [
        parent,
        kind,
        sku,
        _clean(get("nombre_producto", "")),
        _clean(get("Marca", get("marca", ""))),
        _clean(get("descripcion_corta", "")),
        _clean(get("descripcion_larga", "")),
        "" if kind == "variable" else stock,
        category_path,
        _clean(get("etiquetas", "")),
        _clean(get("Web link imagen", "")),
        "" if kind == "variable" else (_clean(get("precio", 0)) or 0),
        "" if kind == "variable" else (_clean(get("Precio descuento", 0)) or 0),
        _clean(get("imagenes", "")),
    ]


def _read_master(sheets_service, spreadsheet_id):
    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{MASTER_SHEET}'",
        valueRenderOption="UNFORMATTED_VALUE",
    ).execute()
    rows = records_from_values(result.get("values", []))
    columns = list(MASTER_COLUMNS) + ["atributo_nombre", "atributo_valor", "codigo_barras"]
    df = pd.DataFrame([{key: row.get(key, "") for key in columns} for row in rows], columns=columns)
    if not df.empty:
        paths = df["categorias"].apply(split_category_path)
        df["categoria"] = paths.apply(lambda x: x[0])
        df["subcategoria"] = paths.apply(lambda x: x[1])
        df["marca"] = df["Marca"]
    else:
        df["categoria"] = pd.Series(dtype=str)
        df["subcategoria"] = pd.Series(dtype=str)
        df["marca"] = pd.Series(dtype=str)
    return df


_CAPTURE_LOCKS = {}
_CAPTURE_LOCKS_GUARD = threading.Lock()


def _append_master_row(session, spreadsheet_id, record):
    """Read fresh, reject duplicates, then write the parent and child atomically."""
    with _CAPTURE_LOCKS_GUARD:
        lock = _CAPTURE_LOCKS.setdefault(spreadsheet_id, threading.RLock())
    with lock:
        sheets = legacy._get_sheets_service(session)
        response = sheets.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"'{MASTER_SHEET}'",
            valueRenderOption="UNFORMATTED_VALUE",
        ).execute()
        updates = prepare_capture_updates(response.get("values", []), record)
        metadata = sheets.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields="sheets(properties(sheetId,title,gridProperties(columnCount)))",
        ).execute()
        for sheet in metadata.get("sheets", []):
            props = sheet.get("properties", {})
            if props.get("title") == MASTER_SHEET and props.get("gridProperties", {}).get("columnCount", 21) < 21:
                sheets.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": [{
                    "updateSheetProperties": {"properties": {"sheetId": props["sheetId"], "gridProperties": {"columnCount": 21}},
                                              "fields": "gridProperties.columnCount"}}]}).execute()
        sheets.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"valueInputOption": "RAW", "data": updates},
        ).execute()
    return spreadsheet_id


def _no_variable_sync(*args, **kwargs):
    return {"sincronizadas": 0, "nuevas": 0, "total": 0, "source": "formula"}


def _no_legacy_format(*args, **kwargs):
    return None


legacy.NOMBRE_HOJA_INVENTARIO = MASTER_SHEET
legacy.COLUMNAS_INVENTARIO = list(MASTER_COLUMNS)
legacy._fila_formato_gabo = _canonical_row
legacy._agregar_fila_google_sheet = _append_master_row
legacy._leer_google_sheet = _read_master
legacy._sincronizar_lista_variable = _no_variable_sync
legacy._aplicar_formato_base = _no_legacy_format
legacy._aplicar_formato_filas = _no_legacy_format
legacy._AUTO_SYNC_AFTER_SAVE = None  # La publicación explícita se delega al servicio de sincronización.

fastapi_app = legacy.fastapi_app
