"""Retired public origins: canonical redirects and the existing signed sync backend.

No Gradio import, OAuth session, page, generation or catalog write is started here.
Existing Render credentials remain in place; a rollback only changes the image.
"""
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse

PUBLIC_ORIGIN = "https://rincon-frontend.onrender.com"
DESTINATIONS = {
    "/inventory-hub": "inventory/count", "/inventory-manager": "inventory/count",
    "/inventory-count": "inventory/count", "/inventory-history": "inventory/count",
    "/inventory-sync": "inventory/count", "/woocommerce-publish-preview": "inventory/count",
    "/woocommerce-image-preview": "more/media", "/woocommerce-batch-sync": "more/publication",
    "/woocommerce-product-sync": "more/publication", "/studio": "generate/capture",
}
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

if os.getenv("SUITE_SERVICE_ROLE", "main").lower() == "sync":
    import sync_service
    # Keep the authenticated internal executor, never its public legacy pages.
    app.post("/internal/tools")(sync_service.tools)


@app.get("/service-health")
def health():
    return {"ok": True, "interface": "redirect", "gradio": False,
            "role": os.getenv("SUITE_SERVICE_ROLE", "main"),
            "version": os.getenv("RENDER_GIT_COMMIT", "")}


@app.api_route("/{path:path}", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
def retired(request: Request, path: str):
    if request.method not in {"GET", "HEAD"}:
        return JSONResponse({"error": "La interfaz antigua se retiró. Abre la aplicación nueva.",
                             "app": PUBLIC_ORIGIN}, status_code=410, headers={"Cache-Control": "no-store"})
    if path.strip("/") in {"login", "logout", "auth/callback", "session/start"}:
        # Do not copy cookies, OAuth codes, state or query strings between domains.
        destination = PUBLIC_ORIGIN + "/login"
    else:
        destination = PUBLIC_ORIGIN + "/#" + DESTINATIONS.get("/" + path.strip("/"), "home")
    return RedirectResponse(destination, status_code=303, headers={"Cache-Control": "no-store"})

