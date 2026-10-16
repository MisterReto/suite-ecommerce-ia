"""Write catalog form edits to the existing, tenant-owned operational Sheet.

Only named product cells are written. Image references, unknown columns and the
formula-driven Simple/Variable/CSV tabs are preserved.
"""
from sqlalchemy import select

from catalog_taxonomy import read_inventory
from drive_service import DriveService
from inventory_schema import MASTER_SHEET, MASTER_COLUMNS, join_category_path
from sheets_service import SheetsService, column_name
from .models import Product, AuditLog


def save_to_drive(value, product, previous_sku, parent_sku):
    from studio_api import runtime
    client, sheet, _ = read_inventory(runtime, value)
    root = value["platform_tenant"]
    if not sheet or not DriveService(client, root).owns(sheet):
        raise ValueError("No se encontró inventario_completo en la carpeta autorizada.")
    service = SheetsService(runtime._get_sheets_service(value), sheet)
    props = next((item["properties"] for item in service.metadata().get("sheets", [])
                  if item["properties"]["title"] == MASTER_SHEET), None)
    if not props:
        raise ValueError("No se encontró Lista completa; no se creó otra hoja.")
    count = props.get("gridProperties", {}).get("rowCount", 0)
    if not 1 <= count <= 10000:
        raise ValueError("La hoja excede el límite de lectura segura para editar.")
    grid = service.read_range(f"A1:U{count}")
    headers = [str(item).strip() for item in grid[0]] if grid else []
    if headers[:14] != list(MASTER_COLUMNS):
        raise ValueError("Las columnas de Lista completa cambiaron; no se sobrescribió la hoja.")
    rows = [{name: row[i] if i < len(row) else "" for i, name in enumerate(headers) if name}
            for row in grid[1:]]
    matches = [i + 2 for i, row in enumerate(rows) if str(row.get("sku", "")).strip().casefold() == previous_sku.casefold()]
    if not matches and previous_sku != product.sku:
        # The prior request may have reached Drive before its acknowledgment was lost.
        matches = [i + 2 for i, row in enumerate(rows) if str(row.get("sku", "")).strip().casefold() == product.sku.casefold()]
    if len(matches) > 1:
        raise ValueError("El SKU está duplicado en Drive; corrige la duplicación antes de editar.")
    target = matches[0] if matches else max((i + 2 for i, row in enumerate(rows) if row.get("sku")), default=1) + 1
    if any(i + 2 != target and str(row.get("sku", "")).strip().casefold() == product.sku.casefold()
           for i, row in enumerate(rows)):
        raise ValueError("El nuevo SKU ya existe en Drive; no se guardó una copia.")
    if target > count:
        raise ValueError("Agrega una fila vacía a Lista completa antes de guardar.")
    if not matches and target - 2 < len(rows) and any(rows[target - 2].values()):
        raise ValueError("La siguiente fila contiene datos sin SKU; revísala antes de guardar.")
    if parent_sku:
        parents = [row for row in rows if str(row.get("sku", "")).strip() == parent_sku
                   and str(row.get("tipo", "")).casefold() == "variable" and not row.get("sku_padre")]
        if len(parents) != 1:
            raise ValueError("Guarda primero el padre en Drive usando su SKU.")
    fields = dict(sku=product.sku, sku_padre=parent_sku, tipo=product.product_type,
                  nombre_producto=product.name, Marca=product.brand,
                  descripcion_corta=product.short_description, descripcion_larga=product.long_description,
                  Existencias="" if product.product_type == "variable" else product.stock,
                  precio="" if product.product_type == "variable" or product.price is None else product.price,
                  categorias=join_category_path(product.category, product.subcategory), etiquetas=", ".join(product.tags or []),
                  codigo_barras=product.barcode or "")
    # These extension columns are established by capture; never overwrite another
    # header in a reserved position or rebuild an entire row from a partial form.
    additions = []
    if fields["codigo_barras"] and "codigo_barras" not in headers:
        headers += [""] * max(0, 21 - len(headers))
        if headers[20] not in {"", "codigo_barras"}:
            raise ValueError("La columna de código de barras está ocupada por otro campo.")
        headers[20] = "codigo_barras"
        additions.append({"range": f"'{MASTER_SHEET}'!U1", "values": [["codigo_barras"]]})
    attrs = product.attributes or {}
    variation = [(key, val) for key, val in attrs.items() if isinstance(val, (str, list))
                 and key not in {"Tipo reconocido", "Variante"}]
    if variation:
        key, val = variation[0]
        fields.update(atributo_nombre=key, atributo_valor=", ".join(val) if isinstance(val, list) else val)
    changes = additions + [{"range": f"'{MASTER_SHEET}'!{column_name(headers.index(key) + 1)}{target}", "values": [[item]]}
                           for key, item in fields.items() if key in headers]
    # Parent SKU renames also update the family references in the same request.
    if previous_sku != product.sku and product.product_type == "variable":
        changes += [{"range": f"'{MASTER_SHEET}'!A{i + 2}", "values": [[product.sku]]}
                    for i, row in enumerate(rows) if row.get("sku_padre") == previous_sku]
    service.spreadsheets().values().batchUpdate(spreadsheetId=sheet,
        body={"valueInputOption": "RAW", "data": changes}).execute()
    confirmed = service.read_range(f"A{target}:U{target}")
    confirmed = confirmed[0] if confirmed else []
    for key, expected in fields.items():
        if key not in headers:
            continue
        index = headers.index(key)
        actual = confirmed[index] if index < len(confirmed) else ""
        if actual != (expected if expected is not None else ""):
            raise ValueError("Drive no confirmó todos los cambios. Revisa la fila antes de reintentar.")
    value.pop("capture_snapshot", None)
    return {"drive_saved": True, "message": "Producto guardado en el catálogo y en Drive."}


def parent_fields(db, tenant, data):
    fields = data.model_dump(exclude={"version", "parent_sku", "sync_drive"})
    if data.parent_sku is not None:
        fields["parent_id"] = None
        if data.product_type == "variation":
            from sqlalchemy import func
            parents = list(db.scalars(select(Product).where(Product.tenant_id == tenant,
                func.lower(Product.sku) == data.parent_sku.strip().lower(),
                Product.status.not_in(["deleted", "archived"]))))
            if len(parents) != 1 or parents[0].product_type != "variable":
                raise ValueError("No se encontró un padre variable activo con ese SKU en tu catálogo.")
            fields["parent_id"] = parents[0].id
    return fields


def product_view(db, product):
    from .catalog import serialize
    parent = db.scalar(select(Product).where(Product.id == product.parent_id,
        Product.tenant_id == product.tenant_id)) if product.parent_id else None
    return {**serialize(product), "parent_sku": parent.sku if parent else ""}


def drive_result(db, value, data, product, previous_sku):
    if not data.sync_drive:
        return {}
    from .catalog import audit
    from app_security import public_error
    pending = db.scalar(select(AuditLog).where(AuditLog.tenant_id == product.tenant_id,
        AuditLog.product_id == product.id, AuditLog.action == "product.drive_saved")
        .order_by(AuditLog.created_at.desc()).limit(1))
    if pending and pending.result == "failed":
        previous_sku = pending.after.get("source_sku", previous_sku)
    parent_sku = product_view(db, product)["parent_sku"]
    try:
        result = save_to_drive(value, product, previous_sku, parent_sku)
    except Exception as exc:
        # SQL was saved. A retry uses the new version and performs a cell upsert,
        # never another stock movement or a duplicate product append.
        result = {"drive_saved": False, "message": "Los cambios se guardaron en el catálogo, pero Drive quedó pendiente. " + public_error(exc) + " Vuelve a guardar para reintentar."}
    audit(db, product.tenant_id, value["email"], "product.drive_saved", product.id,
          after={**result, "source_sku": previous_sku}, result="completed" if result["drive_saved"] else "failed")
    return result
