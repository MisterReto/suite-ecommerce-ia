"""Entrypoint de la Suite IA con `Lista completa` como fuente única.

La UI sigue viviendo en app.py, pero este módulo adapta la capa de inventario y
la presentación para:
- no leer/escribir Gabo nueva;
- guardar las 14 columnas canónicas de Lista completa;
- dejar Lista Simple/Lista Variable como vistas FILTER del Sheet;
- publicar automáticamente SOLO el SKU recién guardado (sin lotes);
- aplicar una interfaz limpia, responsive y accesible sin alterar la lógica IA.
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

# ---------------------------------------------------------------------------
# 6) Capa UX / accesibilidad. Solo cambia presentación, no callbacks.
# ---------------------------------------------------------------------------
old_head = """TUTORIAL_HEAD = \"\"\"
<link rel=\"stylesheet\" href=\"/static/tutorial.css?v=2\">
<script defer src=\"/static/tutorial.js?v=2\"></script>
\"\"\""""
new_head = """TUTORIAL_HEAD = \"\"\"
<link rel=\"stylesheet\" href=\"/static/tutorial.css?v=2\">
<link rel=\"stylesheet\" href=\"/static/ui.css?v=1\">
<script defer src=\"/static/tutorial.js?v=3\"></script>
<script defer src=\"/static/accessibility.js?v=2\"></script>
\"\"\""""
_replace_once(old_head, new_head, "assets de interfaz accesible")

_replace_once(
    '    gr.Markdown("# 🛒 Suite Ecommerce (SEO, Precios, IA y Variantes)", elem_id="tour-app-title")',
    '''    gr.HTML("""<header class=\"rda-app-header\">\n      <div class=\"rda-app-brand\">\n        <p class=\"rda-app-eyebrow\">EL RINCÓN DE ASIA · CATÁLOGO</p>\n        <h1 class=\"rda-app-title\">Suite de productos con IA</h1>\n        <p class=\"rda-app-subtitle\">Captura un producto, revisa la información y publícalo sin cambiar de herramienta.</p>\n      </div>\n      <div class=\"rda-flow-badge\" aria-label=\"Flujo principal: escanea, revisa y publica\">📷 Escanea&nbsp; → &nbsp;✏️ Revisa&nbsp; → &nbsp;✅ Publica</div>\n    </header>""", elem_id="tour-app-title")''',
    "encabezado principal",
)

old_tutorial_button = '''    btn_tutorial = gr.Button(
        "🧭 VER TUTORIAL GUIADO",
        variant="primary",
        size="lg",
        elem_id="tour-launcher",
    )'''
new_tutorial_button = '''    btn_tutorial = gr.Button(
        "❔ Ver guía de uso",
        variant="secondary",
        size="sm",
        elem_id="tour-launcher",
    )'''
_replace_once(old_tutorial_button, new_tutorial_button, "botón de ayuda")

# La tarea principal abre por defecto; Configuración queda disponible como ajuste.
_replace_once("    with gr.Tabs():", "    with gr.Tabs(selected=1):", "pestaña inicial")
_replace_once('        with gr.Tab("⚙️ Configuración"):', '        with gr.Tab("⚙️ Ajustes"):', "nombre tab ajustes")

old_product_start = '''        with gr.Tab("1. Ingreso y Edición de Productos"):
            estado = gr.Textbox(label="Consola de Sistema", interactive=False, lines=4)'''
new_product_start = '''        with gr.Tab("＋ Nuevo producto"):
            gr.HTML("""<div class=\"rda-workflow\" aria-label=\"Pasos para publicar un producto\">\n              <div class=\"rda-step\"><span class=\"rda-step-num\">1</span><div><strong>Captura</strong><span>Fotos del producto</span></div></div>\n              <div class=\"rda-step\"><span class=\"rda-step-num\">2</span><div><strong>Revisa</strong><span>Datos, precio y clasificación</span></div></div>\n              <div class=\"rda-step\"><span class=\"rda-step-num\">3</span><div><strong>Genera</strong><span>Imágenes para e-commerce</span></div></div>\n              <div class=\"rda-step\"><span class=\"rda-step-num\">4</span><div><strong>Publica</strong><span>Sheets + WooCommerce</span></div></div>\n            </div>""")
            estado = gr.Textbox(label="Estado del proceso", interactive=False, lines=3, elem_id="process-status")'''
_replace_once(old_product_start, new_product_start, "inicio de nuevo producto")

_replace_once('                    gr.Markdown("### 1. Imágenes y Análisis")', '                    gr.Markdown("### 📷 Captura del producto")', "título captura")
_replace_once('                    gr.Markdown("### 2. Clasificación, Textos y Precio")', '                    gr.Markdown("### ✏️ Información del producto")', "título información")
_replace_once('                    gr.Markdown("### 3. Estudio Fotográfico IA (Formato Cuadrado)")', '                    gr.Markdown("### ✨ Imágenes para la tienda")', "título imágenes")
_replace_once('                        "🔍 Analizar Producto (SEO + Info + Precio)",', '                        "✨ Analizar producto con IA",', "botón analizar")
_replace_once('                "💾 APROBAR Y GUARDAR EN MI INVENTARIO (Google Sheets)",', '                "✅ Guardar y publicar producto",', "botón guardar")
_replace_once('        with gr.Tab("2. Variantes de Presentación (Google Lens IA)"):', '        with gr.Tab("🔎 Buscar variantes"):', "nombre tab variantes")


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
