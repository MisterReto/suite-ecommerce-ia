"""WooCommerce -> Google Sheets. No AI, no writes to WooCommerce."""
import base64
import html
import json
import time
from collections import Counter
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

MASTER = "Lista completa"
EXTRA = ["woocommerce_id", "woocommerce_parent_id", "woocommerce_attributes_json"]


class WooReader:
    def __init__(self, url, key, secret):
        parsed = urlsplit(url.strip())
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.query or parsed.fragment:
            raise ValueError("Usa la URL HTTPS de tu tienda, sin credenciales ni parámetros.")
        self.base = url.rstrip("/") + "/wp-json/wc/v3/"
        self.authorization = "Basic " + base64.b64encode(f"{key}:{secret}".encode()).decode()

    def pages(self, endpoint, **params):
        for page in range(1, 1001):
            url = self.base + endpoint + "?" + urlencode(dict(params, page=page, per_page=100))
            for attempt in range(4):
                try:
                    req = Request(url, headers={"Authorization": self.authorization, "Accept": "application/json"})
                    with urlopen(req, timeout=60) as response:
                        rows = json.load(response)
                        total = int(response.headers.get("X-WP-TotalPages", "0"))
                    break
                except HTTPError as exc:
                    if exc.code not in (429, 500, 502, 503, 504) or attempt == 3:
                        raise RuntimeError(f"WooCommerce HTTP {exc.code}. Revisa URL/permisos; no se escribió en Sheets.") from None
                    time.sleep(min(30, 2 ** (attempt + 1)))
                except URLError:
                    if attempt == 3:
                        raise RuntimeError("No se pudo leer WooCommerce; no se escribió en Sheets.") from None
                    time.sleep(2 ** (attempt + 1))
            if not isinstance(rows, list):
                raise RuntimeError("Respuesta WooCommerce inválida; sincronización detenida.")
            yield from rows
            if (total and page >= total) or len(rows) < 100:
                return
        raise RuntimeError("Catálogo supera el límite de paginación; no se importará parcialmente.")


def category_paths(categories):
    index = {c["id"]: c for c in categories}
    result = {}
    for cid in index:
        names, seen, current = [], set(), cid
        while current:
            if current in seen or current not in index:
                raise ValueError("Jerarquía de categorías incompleta o circular.")
            seen.add(current)
            item = index[current]
            names.append(html.unescape(item["name"]))
            current = int(item.get("parent") or 0)
        result[cid] = " > ".join(reversed(names))
    return result


def category_value(items, paths):
    values = [paths[c["id"]] for c in items if c["id"] in paths]
    # Preserve multiple independent paths; omit redundant ancestors.
    return ", ".join(v for v in dict.fromkeys(values)
                     if not any(other.startswith(v + " > ") for other in values))


def record(product, paths, parent=None):
    sku = str(product.get("sku") or "").strip()
    tax = parent if parent is not None else product
    attrs = product.get("attributes") or []
    data = {
        "sku": sku,
        "tipo": "variation" if parent is not None else product.get("type", "simple"),
        "sku_padre": str(parent.get("sku") or "").strip() if parent else "",
        "nombre_producto": html.unescape(product.get("name") or (parent or {}).get("name") or ""),
        "descripcion_larga": product.get("description") or "",
        "categorias": category_value(tax.get("categories") or [], paths),
        "woocommerce_id": str(product["id"]),
        "woocommerce_parent_id": str(parent["id"]) if parent else "",
        "woocommerce_attributes_json": json.dumps(attrs, ensure_ascii=False),
    }
    if parent is None:
        data["descripcion_corta"] = product.get("short_description") or ""
    if product.get("type") != "variable":
        data["precio"] = product.get("regular_price") or ""
        data["Precio descuento"] = product.get("sale_price") or ""
        # None means unmanaged/inherited stock, not zero inventory.
        if product.get("stock_quantity") is not None:
            data["Existencias"] = product["stock_quantity"]
    if "brands" in tax:
        data["Marca"] = ", ".join(html.unescape(b["name"]) for b in tax["brands"])
    data["etiquetas"] = ", ".join(html.unescape(t["name"]) for t in tax.get("tags", []))
    images = [product["image"]] if parent and product.get("image") else product.get("images", [])
    if images:
        data["Web link imagen"] = images[0].get("src", "")
    if parent and attrs:
        data["atributo_nombre"] = attrs[0].get("name", "")
        data["atributo_valor"] = attrs[0].get("option", "")
    # Never overwrite 'imagenes': these are the user's Drive filenames.
    return data


def download_catalog(reader):
    paths = category_paths(list(reader.pages("products/categories", hide_empty="false")))
    records, skipped = [], []
    for product in reader.pages("products"):
        if product.get("type") not in ("simple", "variable"):
            skipped.append({"id": product["id"], "reason": "tipo no compatible"})
            continue
        if product.get("sku"):
            records.append(record(product, paths))
        else:
            skipped.append({"id": product["id"], "reason": "sin SKU"})
        if product.get("type") == "variable":
            for child in reader.pages(f"products/{product['id']}/variations"):
                if child.get("sku"):
                    records.append(record(child, paths, product))
                else:
                    skipped.append({"id": child["id"], "reason": "variación sin SKU"})
    duplicates = [sku for sku, n in Counter(r["sku"] for r in records).items() if n > 1]
    if duplicates:
        raise ValueError(f"SKUs duplicados en WooCommerce: {duplicates[:10]}")
    return records, skipped


def column_letter(index):
    text = ""
    while index:
        index, digit = divmod(index - 1, 26)
        text = chr(65 + digit) + text
    return text


def make_plan(values, formulas, records, add_new=True):
    if not values or "sku" not in values[0] or "categorias" not in values[0]:
        raise ValueError("Lista completa necesita encabezados 'sku' y 'categorias'.")
    headers = list(values[0])
    nonempty = [h for h in headers if h]
    if len(nonempty) != len(set(nonempty)):
        raise ValueError("Hay encabezados duplicados en Lista completa.")
    for name in EXTRA + ["atributo_nombre", "atributo_valor"]:
        if name not in headers:
            headers.append(name)
    sku_col = headers.index("sku")
    index = {}
    for row_num, row in enumerate(values[1:], 2):
        sku = str(row[sku_col]).strip() if len(row) > sku_col else ""
        if not sku:
            continue
        if sku in index:
            raise ValueError(f"SKU duplicado en Sheets: {sku}")
        index[sku] = row_num
    writes, report = [], []
    for col in range(len(values[0]), len(headers)):
        writes.append({"range": f"{column_letter(col+1)}1", "values": [[headers[col]]]})
    next_row = len(values) + 1
    for item in records:
        row_num = index.get(item["sku"])
        new = row_num is None
        if new:
            if not add_new:
                continue
            row_num, next_row = next_row, next_row + 1
        for field, after in item.items():
            if field not in headers:
                continue
            col = headers.index(field)
            before = values[row_num-1][col] if row_num <= len(values) and col < len(values[row_num-1]) else ""
            formula = formulas[row_num-1][col] if row_num <= len(formulas) and col < len(formulas[row_num-1]) else ""
            if isinstance(formula, str) and formula.startswith("="):
                continue
            if str(before) != str(after):
                address = f"{column_letter(col+1)}{row_num}"
                writes.append({"range": address, "values": [[after]]})
                report.append({"sku": item["sku"], "campo": field, "antes": before, "despues": after, "nuevo": new})
    return writes, report, max(len(values), next_row-1), len(headers)


def apply_plan(book, worksheet, baseline, baseline_formulas, writes, row_count, col_count):
    # Re-read before applying: do not overwrite edits made since preview.
    if worksheet.get_all_values(value_render_option="UNFORMATTED_VALUE") != baseline or worksheet.get_all_values(value_render_option="FORMULA") != baseline_formulas:
        raise RuntimeError("La hoja cambió desde la vista previa. Vuelve a generar el plan.")
    if not writes:
        return "Sin cambios."
    backup_title = "Respaldo WC " + time.strftime("%Y%m%d-%H%M%S")
    book.duplicate_sheet(worksheet.id, new_sheet_name=backup_title)
    if row_count > worksheet.row_count or col_count > worksheet.col_count:
        worksheet.resize(rows=max(row_count, worksheet.row_count), cols=max(col_count, worksheet.col_count))
    # One atomic Sheets values request. RAW prevents formula injection from catalog text.
    worksheet.batch_update(writes, value_input_option="RAW")
    actual = worksheet.get_all_values(value_render_option="UNFORMATTED_VALUE")
    for entry in writes:
        import re
        match = re.fullmatch(r"([A-Z]+)([0-9]+)", entry["range"])
        col = 0
        for char in match[1]:
            col = col * 26 + ord(char) - 64
        row = int(match[2])
        value = actual[row-1][col-1] if row <= len(actual) and col <= len(actual[row-1]) else ""
        expected = entry["values"][0][0]
        if str(value) != str(expected):
            raise RuntimeError(f"Verificación pendiente en {entry['range']}. Respaldo: {backup_title}")
    return f"Sincronización verificada. Respaldo: {backup_title}"
