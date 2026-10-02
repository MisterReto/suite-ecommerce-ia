"""Read WooCommerce stock without mistaking parent inheritance for no stock."""


def enabled(value):
    return value is True or str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


def attach_parent_stock(variation, parent):
    result = dict(variation)
    inherited = str(result.get("manage_stock") or "").casefold() == "parent"
    inherited = inherited or (not enabled(result.get("manage_stock")) and enabled(parent.get("manage_stock")))
    if inherited:
        result["_stock_inherited"] = True
        result["_stock_parent_sku"] = parent.get("sku", "")
        if parent.get("stock_quantity") is not None:
            result["_effective_stock_quantity"] = parent["stock_quantity"]
        else:
            result["_effective_stock_quantity"] = result.get("stock_quantity")
    return result


def stock_reading(product):
    inherited = bool(product.get("_stock_inherited")) or str(product.get("manage_stock") or "").casefold() == "parent"
    amount = product.get("_effective_stock_quantity", product.get("stock_quantity"))
    try:
        amount = int(amount) if amount is not None and amount != "" else None
    except (TypeError, ValueError):
        amount = None
    return {"quantity": amount, "source": "parent" if inherited else "own" if enabled(product.get("manage_stock")) else "availability",
            "managed": inherited or enabled(product.get("manage_stock")), "inherited": inherited,
            "parent_sku": product.get("_stock_parent_sku", ""), "availability": product.get("stock_status")}
