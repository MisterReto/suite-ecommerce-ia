"""Entrypoint de la Suite IA con `Lista completa` como fuente única.

La UI sigue viviendo en app.py, pero este módulo adapta únicamente la capa de
inventario para:
- no leer/escribir Gabo nueva;
- guardar las 14 columnas canónicas de Lista completa;
- dejar Lista Simple/Lista Variable como vistas FILTER del Sheet;
- publicar automáticamente SOLO el SKU recién guardado (sin lotes).
"""
from __future__ import annotations

from pathlib import Path
import sys
import types

import pandas as pd

from inventory_schema import MASTER_COLUMNS, MASTER_SHEET, split_category_path


APP_PATH = Path(__file__).with_name("app.py")
source = APP_PATH.read_text(encoding="utf-8")


def _replace_once(old: str, new: str, label: str) -> None:
    global source
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"No pude preparar la Suite IA: esperaba 1 coincidencia para {label}, encontré {count}."
        )
    source = source.replace(old, new, 1)


# 1) La hoja operativa es Lista completa.
_replace_once(
    'NOMBRE_HOJA_INVENTARIO = "Gabo nueva"',
    'NOMBRE_HOJA_INVENTARIO = "Lista completa"',
    "hoja maestra",
)

# 2) Orden físico exacto de Lista completa.
old_columns = """COLUMNAS_INVENTARIO = [
    'sku_padre', 'tipo', 'sku', 'nombre_producto',
    'descripcion_corta', 'descripcion_larga', 'Existencias',
    'categoria', 'subcategoria', 'etiquetas', 'Web link imagen',
    'precio', 'Precio descuento', 'imagenes'
]"""
new_columns = """COLUMNAS_INVENTARIO = [
    'sku_padre', 'tipo', 'sku', 'nombre_producto', 'Marca',
    'descripcion_corta', 'descripcion_larga', 'Existencias', 'categorias',
    'etiquetas', 'Web link imagen', 'precio', 'Precio descuento', 'imagenes'
]"""
_replace_once(old_columns, new_columns, "columnas canónicas")

# 3) Persistir Marca, que el callback original recibía pero no guardaba.
_replace_once(
    "            'nombre_producto': nombre,\n            'descripcion_corta': desc_corta,",
    "            'nombre_producto': nombre,\n            'Marca': marca,\n            'descripcion_corta': desc_corta,",
    "persistencia de Marca",
)

# 4) Nuevos productos arrancan en 0 y categoría queda en una sola columna.
_replace_once(
    "            'Existencias': 1,\n            'categoria': cat,\n            'subcategoria': subcat,",
    "            'Existencias': 0,\n            'categoria': cat,\n            'subcategoria': subcat,\n            'categorias': f'{cat} > {subcat}' if cat and subcat else (cat or subcat or ''),",
    "stock inicial y ruta de categoría",
)

# 5) Después de guardar la fila, dispara únicamente ese SKU hacia WooCommerce.
old_save_tail = """        _agregar_fila_google_sheet(sesion, spreadsheet_id, nueva_fila)
        url_sheet = f\"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit\"
        return (
            f\"💾 ¡Guardado en Google Sheets! El producto {sku} está en la pestaña \"
            f\"'{NOMBRE_HOJA_INVENTARIO}'.\\n{url_sheet}\"
        )"""
new_save_tail = """        _agregar_fila_google_sheet(sesion, spreadsheet_id, nueva_fila)
        url_sheet = f\"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit\"
        sync_text = \"\"
        hook = globals().get('_AUTO_SYNC_AFTER_SAVE')
        if hook:
            try:
                resultado_sync = hook(sesion, sku)
                accion = resultado_sync.get('action', 'updated') if isinstance(resultado_sync, dict) else 'updated'
                enlace = resultado_sync.get('permalink', '') if isinstance(resultado_sync, dict) else ''
                verbo = 'creado' if accion == 'created' else 'actualizado'
                sync_text = f\"\\n\\n✅ WooCommerce: producto {verbo} automáticamente.\"
                if enlace:
                    sync_text += f\"\\n{enlace}\"
            except Exception as sync_exc:
                sync_text = (
                    \"\\n\\n⚠️ La fila SÍ quedó guardada en Lista completa, pero no pude publicar ese SKU en WooCommerce: \"
                    f\"{sync_exc}\"
                )
        return (
            f\"💾 ¡Guardado en Google Sheets! El producto {sku} está en la pestaña \"
            f\"'{NOMBRE_HOJA_INVENTARIO}'.\\n{url_sheet}{sync_text}\"
        )"""
_replace_once(old_save_tail, new_save_tail, "publicación individual después de guardar")


# Ejecutamos app.py en un módulo independiente; no modificamos el archivo original.
legacy = types.ModuleType("rincon_ai_runtime")
legacy.__file__ = str(APP_PATH)
legacy.__package__ = ""
sys.modules[legacy.__name__] = legacy
exec(compile(source, str(APP_PATH), "exec"), legacy.__dict__)


# ---------------------------------------------------------------------------
# Adaptadores canónicos. Los callbacks de app.py resuelven estos nombres en
# tiempo de ejecución, por lo que no hay que reconstruir la UI de Gradio.
# ---------------------------------------------------------------------------
def _clean(value):
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return "" if value is None else value


def _canonical_row(record):
    get = record.get
    kind = str(_clean(get("tipo", "Simple")) or "Simple").strip()
    sku = str(_clean(get("sku", "")) or "").strip()
    parent = str(_clean(get("sku_padre", "")) or "").strip()
    if kind.casefold() != "variable":
        parent = sku

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
        stock,
        category_path,
        _clean(get("etiquetas", "")),
        _clean(get("Web link imagen", "")),
        _clean(get("precio", 0)) or 0,
        _clean(get("Precio descuento", 0)) or 0,
        _clean(get("imagenes", "")),
    ]


def _read_master(sheets_service, spreadsheet_id):
    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{MASTER_SHEET}'!A:N",
        valueRenderOption="UNFORMATTED_VALUE",
    ).execute()
    values = result.get("values", [])
    rows = []
    for raw in values[1:]:
        row = list(raw[: len(MASTER_COLUMNS)])
        row.extend([""] * (len(MASTER_COLUMNS) - len(row)))
        rows.append(row)
    df = pd.DataFrame(rows, columns=list(MASTER_COLUMNS))

    # Alias solo en memoria para dropdowns/detección heredados.
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


def _no_variable_sync(*args, **kwargs):
    return {"sincronizadas": 0, "nuevas": 0, "total": 0, "source": "formula"}


def _no_legacy_format(*args, **kwargs):
    return None


def _auto_sync_after_save(session, sku):
    from single_product_auto import sync_saved_sku
    return sync_saved_sku(session, sku)


legacy.NOMBRE_HOJA_INVENTARIO = MASTER_SHEET
legacy.COLUMNAS_INVENTARIO = list(MASTER_COLUMNS)
legacy._fila_formato_gabo = _canonical_row
legacy._leer_google_sheet = _read_master
legacy._sincronizar_lista_variable = _no_variable_sync
legacy._aplicar_formato_base = _no_legacy_format
legacy._aplicar_formato_filas = _no_legacy_format
legacy._AUTO_SYNC_AFTER_SAVE = _auto_sync_after_save

fastapi_app = legacy.fastapi_app
