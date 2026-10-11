"""Serve the built Next.js export on the API origin without a Node runtime."""
from pathlib import Path
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles


def register_frontend(app):
    root = Path(__file__).parent / "frontend" / "out"
    if (root / "_next").exists():
        app.mount("/_next", StaticFiles(directory=root / "_next"), name="next-assets")
    if (root / "icons").exists():
        app.mount("/icons", StaticFiles(directory=root / "icons"), name="pwa-icons")

    @app.get("/manifest.webmanifest", include_in_schema=False)
    def manifest():
        return FileResponse(root / "manifest.webmanifest",media_type="application/manifest+json",headers={"Cache-Control":"no-cache"})

    @app.get("/sw.js", include_in_schema=False)
    def service_worker():
        return FileResponse(root / "sw.js",media_type="application/javascript",headers={"Cache-Control":"no-cache","Service-Worker-Allowed":"/"})

    @app.get("/", include_in_schema=False)
    def index():
        if not (root / "index.html").is_file():
            return JSONResponse({"error": "Compila frontend con npm ci y npm run build."}, status_code=503)
        return FileResponse(root / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/logo.png", include_in_schema=False)
    def logo():
        return FileResponse(Path(__file__).parent / "static" / "rincon-logo.png", media_type="image/png")

    @app.get("/studio", include_in_schema=False)
    def studio():
        return RedirectResponse("/#studio", status_code=303)

    @app.get("/logout", include_in_schema=False)
    def old_logout():
        return RedirectResponse("/#settings", status_code=303)
