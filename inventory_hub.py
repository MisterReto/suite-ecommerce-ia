"""One inventory tool. Preview never loads until explicitly selected."""
from fastapi import Request
from fastapi.responses import HTMLResponse
import inventory_web

app = inventory_web.fastapi_app


@app.get("/inventory-hub", response_class=HTMLResponse)
def inventory_hub(request: Request):
    if not inventory_web._session(request):
        return HTMLResponse("<h2>Conecta Google Drive desde la Suite.</h2><a href='/'>Volver</a>", status_code=401)
    return HTMLResponse("""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Suite e-commerce</title>
<link rel="icon" href="/suite-static/rincon-logo.png"><style>
*{box-sizing:border-box}body{margin:0;font:16px system-ui;background:#f7f8fb;color:#172033}
header{padding:16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}header img{width:40px;height:40px}
h1{font-size:24px;margin:0;flex:1}a,button{min-height:44px;padding:10px 14px;border-radius:10px;border:1px solid #cbd5e1;background:white;color:#172033;text-decoration:none;font:inherit;cursor:pointer}
nav{display:flex;gap:8px;flex-wrap:wrap;padding:0 16px 12px}button[aria-selected=true]{background:#172033;color:white}
p{margin:0 16px 12px;font-size:14px}iframe{border:0;width:100%;height:calc(100svh - 195px);min-height:520px;background:white}
@media(max-width:600px){h1{font-size:20px}nav button{flex:1}iframe{height:calc(100svh - 265px)}}
</style></head><body><header><img src="/suite-static/rincon-logo.png" alt="El Rincón de Asia"><h1>Inventario y stock</h1><a href="/">← Suite</a><a href="/woocommerce-batch-sync">Subida masiva</a></header>
<nav role="tablist" aria-label="Gestión de inventario"><button role="tab" aria-selected="true" data-page="/inventory-manager">Inventario</button><button role="tab" aria-selected="false" data-page="/inventory-count">Conteo inicial</button><button role="tab" aria-selected="false" data-page="/woocommerce-publish-preview">Preview stock</button></nav>
<p>El conteo se guarda en Drive. El preview se ejecuta al solicitarlo; publicar en WooCommerce es una acción aparte. Guarda los cambios antes de cambiar de pestaña.</p>
<iframe id="inventory-view" title="Inventario" src="/inventory-manager"></iframe>
<script src="/suite-static/inventory-hub.js"></script></body></html>""")
