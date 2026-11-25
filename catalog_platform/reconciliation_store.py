"""Authenticated, bounded WooCommerce reads for a complete reconciliation snapshot."""
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .reconciliation_index import norm

PAGE = 50
LIMIT = 20000
FIELDS = "id,parent_id,sku,global_unique_id,status,type,variations"


def pages(engine, endpoint, check):
    expected = None
    last = 0
    page = 1
    while True:
        check()
        response = engine.ns["wc_session"].get(engine.ns["WC_API"] + "/" + endpoint,
            params={"context":"edit","status":"any","per_page":PAGE,"page":page,"orderby":"id",
                    "order":"asc","_fields":FIELDS}, timeout=(8,30))
        items = engine.ns["comprobar_respuesta"](response,endpoint)
        try:
            total = int(response.headers["X-WP-Total"])
            count = int(response.headers["X-WP-TotalPages"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("WooCommerce omitió los totales de paginación.") from None
        if (total < 0 or total > LIMIT or count != (total+PAGE-1)//PAGE
            or expected not in (None,total) or not isinstance(items,list)
            or len(items) != min(PAGE,max(0,total-(page-1)*PAGE))):
            raise ValueError("El catálogo cambió o la página está incompleta.")
        expected = total
        for item in items:
            if (not isinstance(item,dict) or type(item.get("id")) is not int
                or item["id"] <= last or not isinstance(item.get("sku"),str)
                or not item.get("status")):
                raise ValueError("WooCommerce devolvió registros incompletos o repetidos.")
            last = item["id"]
            yield item
        if page >= count:
            return
        page += 1


def snapshot(engine, index, check):
    engine.ns["wc_session"].mount("https://",HTTPAdapter(max_retries=Retry(
        total=3,backoff_factor=0.5,status_forcelist=[429,500,502,503,504],
        allowed_methods=["GET"],respect_retry_after_header=False)))
    total = 0
    def add(item, kind, parent):
        nonlocal total
        total += 1
        if total > LIMIT or not kind or item.get("parent_id",0) != parent:
            raise ValueError("La jerarquía o el tamaño del catálogo impide una comparación completa.")
        index.db.execute("INSERT INTO remote VALUES(?,?,?,?,?,?,?)",(item["id"],norm(item["sku"]),
            norm(item.get("global_unique_id")),kind,parent,item["status"],item["sku"]))
    for item in pages(engine,"products",check):
        add(item,item.get("type"),0)
        if item["type"] == "variable":
            expected = item.get("variations")
            if not isinstance(expected,list) or len(expected)>LIMIT or len(set(expected))!=len(expected):
                raise ValueError("La familia no incluyó una lista completa de variantes.")
            children = set(expected)
            for child in pages(engine,f"products/{item['id']}/variations",check):
                if child.get("parent_id") != item["id"] or child["id"] not in children:
                    raise ValueError("Las variantes devueltas no corresponden a la familia.")
                children.remove(child["id"])
                add(child,"variation",item["id"])
            if children:
                raise ValueError("WooCommerce omitió variantes de una familia.")
    return total
