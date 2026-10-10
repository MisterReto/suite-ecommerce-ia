"""Enforce read-only roles on API and existing administrative tools, server-side."""
# Middleware de permisos de lectura/escritura para API y herramientas compatibles.
# Guía: docs/CODE_GUIDE.md; funciones y objetos: docs/FUNCTION_INDEX.md.

from starlette.requests import Request
from starlette.responses import JSONResponse
from .security import role_for, member


# Aplica permisos a solicitudes HTTP; ocultar un botón en React no reemplaza este control.
class RoleMiddleware:
    # Recibe la aplicación y el acceso al almacén de sesiones.
    def __init__(self, app, sessions):
        self.app, self.sessions = app, sessions

    # Rechaza cuentas no autorizadas y escrituras de usuarios viewer, conservando las rutas
    # públicas definidas.
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request = Request(scope)
        sid = request.cookies.get("session_id") or request.cookies.get("sync_session")
        value = self.sessions().get(sid)
        public = request.url.path in {
            "/",
            "/login",
            "/logout",
            "/auth/callback",
            "/api/session",
            "/api/platform/status",
            "/logo.png",
            "/sw.js",
            "/manifest.webmanifest",
        } or request.url.path.startswith(("/_next/", "/icons/", "/webhooks/", "/api/webhooks/"))
        if (
            value
            and not value.get("role")
            and not member(value.get("email", ""))
            and not public
        ):
            return await JSONResponse(
                {
                    "error": "Tu cuenta no está autorizada. El administrador debe añadirla a APP_ROLE_MAP."
                },
                status_code=403,
            )(scope, receive, send)
        if request.method not in {
            "GET",
            "HEAD",
            "OPTIONS",
        } and request.url.path not in {
            "/logout",
            "/sync-handoff/redeem",
            "/internal/tools",
            "/webhooks/woocommerce",
            "/webhooks/loyverse",
            "/api/webhooks/woocommerce",
            "/api/webhooks/loyverse",
            "/api/uploads",
            "/api/platform/barcode",
        }:
            if (
                value
                and (value.get("role") or role_for(value.get("email", ""))) == "viewer"
            ):
                return await JSONResponse(
                    {"error": "Tu rol permite solo lectura."}, status_code=403
                )(scope, receive, send)
        return await self.app(scope, receive, send)
