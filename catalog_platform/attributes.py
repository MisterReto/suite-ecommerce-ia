"""One variation axis per product; canonical Sheet fields take precedence."""


def single_attribute(attributes, name="", value=None):
    if name and value not in (None, "", []):
        return {name.strip(): value}
    items = {k: v for k, v in (attributes or {}).items()
             if k.strip() and k != "Tipo reconocido" and v not in (None, "", [])}
    for preferred in ("Sabor", "Color", "Variante", "Tamaño"):
        key = next((k for k in items if k.casefold() == preferred.casefold()), None)
        if key:
            return {key: items[key]}
    return dict(list(items.items())[:1])


def image_product(db, product):
    """Keep physical size in image inputs without making it a variation axis."""
    from sqlalchemy import select
    from .catalog import serialize
    from .models import AuditLog
    data = serialize(product)
    size = product.attributes.get("Tamaño", "")
    if not size:
        records = db.scalars(select(AuditLog).where(AuditLog.tenant_id == product.tenant_id,
            AuditLog.product_id == product.id,
            AuditLog.action.in_(["capture.mirrored", "product.updated"]))
            .order_by(AuditLog.created_at.desc()))
        for record in records:
            size = (record.after or {}).get("capture_size") or (record.before or {}).get("attributes", {}).get("Tamaño")
            if size:
                break
    data["size"] = size or ""
    return data
