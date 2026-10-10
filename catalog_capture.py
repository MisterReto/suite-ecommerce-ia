"""Local product identity and atomic parent/variation append planning."""
from decimal import Decimal
from os.path import commonprefix
import re
import unicodedata

from inventory_schema import MASTER_COLUMNS, MASTER_SHEET, is_variable_parent, normalize_product_row

BARCODE_COLUMN = 20  # U; A:N and S:T retain their current meaning.


def text(value):
    if value is None or str(value).casefold() in {"nan", "none"}:
        return ""
    return str(value).strip()


def normalized(value):
    value = unicodedata.normalize("NFKD", text(value).casefold())
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in value if not unicodedata.combining(c))).strip()


def barcode(value):
    code = re.sub(r"[\s-]", "", text(value))
    if not code:
        return ""
    if not re.fullmatch(r"(?:[0-9]{8}|[0-9]{12,14})", code):
        raise ValueError("Usa un EAN/UPC/GTIN de 8, 12, 13 o 14 dígitos, conservando los ceros iniciales.")
    total = sum(int(digit) * (3 if index % 2 == 0 else 1)
                for index, digit in enumerate(reversed(code[:-1])))
    if int(code[-1]) != (-total) % 10:
        raise ValueError("El dígito de control del código de barras no es válido. Revisa la lectura.")
    return code


def barcode_key(value):
    try:
        return barcode(value).zfill(14) if text(value) else ""
    except ValueError:
        return ""  # Old malformed catalog values never establish identity.


def record_barcode(row):
    """Read legacy numeric SKUs too, without treating a parent mask as a GTIN."""
    if is_variable_parent(row):
        return ""
    for value in (row.get("codigo_barras"), row.get("sku")):
        try:
            code = barcode(value)
            if code:
                return code
        except ValueError:
            continue
    return ""


MEASURE = re.compile(r"(?i)(\d+(?:[.,]\d+)?)\s*(kg|ml|mg|g|l|oz|pz|pzas?|piezas?)\b")


def family_name(name):
    return re.sub(r"\s+", " ", MEASURE.sub("", text(name))).strip(" -(),")


def presentation(value):
    match = MEASURE.search(text(value))
    if not match:
        return normalized(value)
    amount = Decimal(match[1].replace(",", "."))
    unit = match[2].lower()
    factor, unit = {"kg": (1000, "g"), "mg": (Decimal("0.001"), "g"),
                    "l": (1000, "ml")}.get(unit, (1, unit))
    if unit.startswith("pz") or unit.startswith("pieza"):
        unit = "pz"
    return f"{(amount * factor).normalize()}{unit}"


def same_brand(first, second):
    return bool(normalized(first)) and normalized(first) == normalized(second)


VARIANT_WORDS = {"fresa", "chocolate", "vainilla", "matcha", "platano", "banana", "mango",
                 "uva", "melon", "coco", "limon", "durazno", "original", "picante",
                 "strawberry", "vanilla", "rojo", "azul", "verde", "negro", "blanco"}
GENERIC_WORDS = {"de", "con", "para", "el", "la", "un", "una", "sabor", "color", "g", "ml",
                 "producto", "bebida", "dulce", "snack", "salsa", "paquete", "botella"}


def family_label(name):
    words = family_name(name).split()
    return " ".join(word for word in words if normalized(word) not in VARIANT_WORDS).strip()


def family_score(name, brand, row):
    if not same_brand(brand, row.get("Marca", row.get("marca", ""))):
        return 0.0
    exclude = set(normalized(brand).split()) | VARIANT_WORDS | GENERIC_WORDS
    wanted = set(normalized(family_name(name)).split()) - exclude
    candidate = set(normalized(family_name(row.get("nombre_producto"))).split()) - exclude
    if not wanted or not candidate:
        return 0.0
    return len(wanted & candidate) / min(len(wanted), len(candidate))


def find_duplicate(rows, candidate):
    code = barcode_key(record_barcode(candidate))
    sku = text(candidate.get("sku")).casefold()
    if code:
        match = next((r for r in rows if barcode_key(record_barcode(r)) == code), None)
        if match:
            return match, "código de barras"
    if sku:
        match = next((r for r in rows if text(r.get("sku")).casefold() == sku), None)
        if match:
            return match, "SKU"
    name = normalized(candidate.get("nombre_producto"))
    brand = candidate.get("Marca", candidate.get("marca", ""))
    value = text(candidate.get("atributo_valor")) or text(candidate.get("gramaje"))
    size = presentation(value or candidate.get("nombre_producto"))
    for row in rows:
        if is_variable_parent(row):
            continue
        row_code = barcode_key(record_barcode(row))
        if code and code == row_code:
            return row, "código de barras"
        # The same option under the same parent cannot be created twice.
        if (text(candidate.get("sku_padre")) and text(candidate.get("sku_padre")).casefold() == text(row.get("sku_padre")).casefold()
                and normalized(candidate.get("atributo_nombre")) == normalized(row.get("atributo_nombre"))
                and value and presentation(value) == presentation(row.get("atributo_valor"))):
            return row, "atributo de la variación"
        if not same_brand(brand, row.get("Marca", row.get("marca", ""))):
            continue
        if code and row_code and code != row_code:
            continue  # Different valid GTINs need a review, not a name-based block.
        row_size = presentation(row.get("atributo_valor") or row.get("nombre_producto"))
        same_name = name and name == normalized(row.get("nombre_producto"))
        same_family = normalized(family_name(candidate.get("nombre_producto"))) == normalized(family_name(row.get("nombre_producto")))
        if (same_name or (same_family and size and size == row_size)) and (not value or not text(row.get("atributo_valor")) or size == row_size):
            return row, "nombre, marca y presentación"
    return None, ""


def review_product(rows, candidate):
    duplicate, reason = find_duplicate(rows, candidate)
    parents = [r for r in rows if is_variable_parent(r)]
    parents.sort(key=lambda r: (-family_score(candidate.get("nombre_producto"), candidate.get("Marca"), r), normalized(r.get("nombre_producto"))))
    suggested = next((text(r.get("sku")) for r in parents
                      if family_score(candidate.get("nombre_producto"), candidate.get("Marca"), r) >= 0.8), "")
    if duplicate:
        message = f"⛔ Ya existe: {text(duplicate.get('sku'))} · {text(duplicate.get('nombre_producto'))}. Coincidencia por {reason}."
        if text(duplicate.get("sku_padre")):
            message += f" Es una variación del padre {text(duplicate.get('sku_padre'))}; no crees otra copia."
        return {"status": "duplicate", "case": "existing", "message": message, "parents": parents,
                "suggested": text(duplicate.get("sku_padre")) or suggested, "duplicate": duplicate,
                "reason": reason, "candidates": [], "recommendation": "Abrir o actualizar la ficha existente; no crear una copia."}
    if suggested:
        children = [r for r in rows if text(r.get("sku_padre")) == suggested]
        return {"status": "possible_variation", "case": "existing_parent", "message": f"🔎 Posible variación nueva de {suggested}. Compara sabor, tamaño o versión y elige ese padre si pertenece a la misma familia.", "parents": parents, "suggested": suggested,
                "candidates": children, "recommendation": "Utilizar el padre existente después de revisar los atributos."}
    related = [r for r in rows if not is_variable_parent(r) and family_score(candidate.get("nombre_producto"), candidate.get("Marca"), r) >= 0.8]
    message = "🔎 Hay productos similares de la misma marca; revisa si cambia la presentación. Todavía no hay un padre coincidente." if related else "✅ Sin coincidencia exacta registrada. Puedes capturar un producto nuevo; revisa también los padres disponibles."
    return {"status": "review" if related else "new", "case": "new_family" if related else "simple",
            "message": message, "parents": parents, "suggested": "", "candidates": related,
            "family_name": family_label(candidate.get("nombre_producto")),
            "recommendation": "Revisar una familia nueva con estas presentaciones." if related else "Guardar como simple; no hay evidencia de una familia registrada."}


def next_parent_sku(name, brand, rows, code=""):
    own_code = barcode(code)
    related = [record_barcode(r) for r in rows
               if family_score(name, brand, r) >= 0.8 and record_barcode(r)]
    base = own_code or next(iter(related), "")
    if base:
        # UPC/EAN representations of the same GTIN are one product, not variants.
        codes = {barcode_key(c) for c in [base, *related]}
        shared = commonprefix(sorted(codes))[14 - len(base):] if len(codes) > 1 else base[:6]
        if not shared:
            raise ValueError("Las variantes no comparten un prefijo de código de barras. Revisa el SKU padre antes de crear la familia.")
        shared = shared[:len(base) - 1]
        masked = shared + "x" * (len(base) - len(shared))
        if any(text(r.get("sku")).casefold() == masked.casefold() for r in rows):
            raise ValueError(f"El SKU padre {masked} ya existe. Revisa y elige su familia; no se unirán productos automáticamente.")
        return masked
    # No readable barcode: retain the established brand/name parent convention.
    prefix = (re.sub(r"[^A-Z0-9]", "", text(brand).upper())[:3].ljust(3, "X")
              + re.sub(r"[^A-Z0-9]", "", family_name(name).upper())[:3].ljust(3, "X"))
    used = {text(r.get("sku")).casefold() for r in rows}
    for index in range(10000):
        sku = prefix + (str(index) if index else "") + "FULL"
        if sku.casefold() not in used:
            return sku
    raise ValueError("No pude proponer un SKU padre libre. Captúralo manualmente.")


def records_from_values(values):
    rows = []
    for number, raw in enumerate(values[1:], 2):
        padded = list(raw[:21]) + [""] * max(0, 21 - len(raw))
        if any(text(v) for v in padded[:14]):
            record = dict(zip(MASTER_COLUMNS, padded[:14]))
            record.update(atributo_nombre=padded[18], atributo_valor=padded[19], codigo_barras=padded[20], _row=number)
            rows.append(record)
    return rows


def prepare_capture_updates(values, record):
    """Plan one values.batchUpdate: parent and child succeed in the same request."""
    rows = records_from_values(values)
    record = dict(record)
    record["codigo_barras"] = barcode(record.get("codigo_barras"))
    for key in ("sku", "sku_padre"):
        if key == "sku_padre" and not text(record.get(key)):
            continue
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", text(record.get(key))):
            raise ValueError("SKU inválido: usa letras, números, guion o guion bajo.")
    duplicate, reason = find_duplicate(rows, record)
    if duplicate:
        raise ValueError(f"El producto ya existe como {text(duplicate.get('sku'))} ({reason}). No se guardó una copia.")
    canonical = normalize_product_row(record)
    if text(record.get("sku_padre")) and canonical["tipo"] != "variation":
        raise ValueError("La variación necesita un SKU propio; el sufijo FULL está reservado al padre.")
    updates = []
    if not values:
        updates.append({"range": f"'{MASTER_SHEET}'!A1:N1", "values": [list(MASTER_COLUMNS)]})
    next_row = max((r["_row"] for r in rows), default=1) + 1
    new_parent = record.get("_new_parent")
    if new_parent:
        parent = normalize_product_row(new_parent)
        if not text(parent.get("nombre_producto")) or not is_variable_parent(parent) or parent["sku"] != canonical["sku_padre"]:
            raise ValueError("Revisa nombre y SKU del nuevo producto padre.")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", parent["sku"]) or parent["sku"].casefold() == canonical["sku"].casefold():
            raise ValueError("El padre necesita un SKU válido distinto al de la variación.")
        if any(text(r.get("sku")).casefold() == parent["sku"].casefold() for r in rows):
            raise ValueError("El SKU padre ya existe. Elígelo en Padres existentes.")
        if any(is_variable_parent(r) and normalized(r.get("nombre_producto")) == normalized(parent["nombre_producto"])
               and same_brand(r.get("Marca"), parent.get("Marca")) for r in rows):
            raise ValueError("Ya existe un padre con ese nombre y marca. Elígelo en Padres existentes.")
        parent["_row"] = next_row
        rows.append(parent)
        next_row += 1
    if canonical["tipo"] == "variation":
        parents = [r for r in rows if text(r.get("sku")).casefold() == canonical["sku_padre"].casefold() and is_variable_parent(r)]
        if len(parents) != 1:
            raise ValueError("Elige un único padre existente o crea uno nuevo para esta variación.")
        parent = parents[0]
        if text(parent.get("Marca")) and text(canonical.get("Marca")) and not same_brand(parent["Marca"], canonical["Marca"]):
            raise ValueError("La marca de la variación no coincide con la marca del padre seleccionado.")
        canonical["sku_padre"] = parent["sku"]
        attribute = text(record.get("atributo_nombre")) or "Tamaño"
        value = text(record.get("atributo_valor")) or text(record.get("gramaje"))
        if not value:
            raise ValueError("Captura el valor de la variación: sabor, tamaño, versión o cantidad.")
        if text(parent.get("atributo_nombre")) and normalized(parent["atributo_nombre"]) != normalized(attribute):
            raise ValueError(f"El padre usa el atributo {parent['atributo_nombre']}; selecciona ese atributo.")
        attribute = text(parent.get("atributo_nombre")) or attribute
        options = [v.strip() for v in text(parent.get("atributo_valor")).split(",") if v.strip()]
        for child in rows:
            if text(child.get("sku_padre")) == parent["sku"] and text(child.get("atributo_valor")):
                options.append(text(child["atributo_valor"]))
        options.append(value)
        options = list(dict((presentation(v), v) for v in options).values())
        parent["atributo_nombre"], parent["atributo_valor"] = attribute, ", ".join(options)
        canonical["atributo_nombre"], canonical["atributo_valor"] = attribute, value
        cover = text(record.get("_parent_cover"))
        images = [v.strip() for v in text(parent.get("imagenes")).split(",") if v.strip()]
        if cover:
            parent["imagenes"] = ",".join(dict.fromkeys([cover] + images))
        if new_parent:
            physical = [parent.get(k, "") for k in MASTER_COLUMNS] + ["", "", "", "", attribute, parent["atributo_valor"], ""]
            updates.append({"range": f"'{MASTER_SHEET}'!A{parent['_row']}:U{parent['_row']}", "values": [physical]})
        else:
            updates.append({"range": f"'{MASTER_SHEET}'!S{parent['_row']}:T{parent['_row']}", "values": [[attribute, parent["atributo_valor"]]]})
            if cover:
                updates.append({"range": f"'{MASTER_SHEET}'!N{parent['_row']}", "values": [[parent["imagenes"]]]})
    elif new_parent:
        raise ValueError("Un padre nuevo solo se crea al guardar una variación.")
    physical = [canonical.get(k, "") for k in MASTER_COLUMNS] + ["", "", "", "", canonical.get("atributo_nombre", ""), canonical.get("atributo_valor", ""), record["codigo_barras"]]
    updates.append({"range": f"'{MASTER_SHEET}'!A{next_row}:U{next_row}", "values": [physical]})
    headers = list(values[0]) if values else []
    headers += [""] * max(0, 21 - len(headers))
    if text(headers[20]) not in {"", "codigo_barras"}:
        raise ValueError("La columna U ya contiene otro campo; no se modificó el inventario.")
    updates.append({"range": f"'{MASTER_SHEET}'!S1:U1", "values": [["atributo_nombre", "atributo_valor", "codigo_barras"]]})
    return updates
