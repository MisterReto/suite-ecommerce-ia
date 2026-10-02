"""Canonical inventory page: all capabilities share one document."""
from fastapi import Request
from fastapi.responses import HTMLResponse
import inventory_web

app = inventory_web.fastapi_app


@app.get("/inventory-hub", response_class=HTMLResponse)
def inventory_hub(request: Request, q: str = "", sku: str = ""):
    return inventory_web.render_inventory(request, q=q, sku=sku)
