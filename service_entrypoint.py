"""API entrypoint with optional UI hosting for the compatible deployment."""
# Arranque de FastAPI: selecciona el rol, registra rutas y ordena los controles de sesión y permisos.
# Guía: docs/CODE_GUIDE.md; funciones y objetos: docs/FUNCTION_INDEX.md.
import os
from starlette.routing import Mount
from catalog_platform.render_config import configure_redirect
from catalog_platform.initialize import initialize_empty_database

configure_redirect()
initialize_empty_database()

if os.getenv("SUITE_SERVICE_ROLE", "main").lower() == "sync":
    from sync_service import app as fastapi_app
else:
    from studio_api import app as fastapi_app
    import product_web
    import native_tools
    native_tools.register(fastapi_app)


if os.getenv("SUITE_SERVICE_ROLE", "main").lower() != "sync":
    import loyverse_web
    loyverse_web.register(fastapi_app)
    if os.getenv("SUITE_SERVE_FRONTEND", "true").lower() == "true":
        from frontend_host import register_frontend
        register_frontend(fastapi_app)
    from catalog_platform.api import router as catalog_router
    fastapi_app.include_router(catalog_router)
    from catalog_platform.webhooks import router as webhook_router
    fastapi_app.include_router(webhook_router)


# Informa rol, versión y almacén de sesión sin consultar Drive ni ejecutar generación; no
# sustituye el heartbeat del worker.
@fastapi_app.get("/service-health")
def service_health():
    return {"ok": True, "interface": "nextjs", "backend": "fastapi", "role": os.getenv("SUITE_SERVICE_ROLE", "main"),
            "remote_sync": bool(os.getenv("SYNC_SERVICE_URL")),
            "generation_backend": os.getenv("STUDIO_IMAGE_JOBS", "local"),
            "service_id": os.getenv("RENDER_SERVICE_ID", ""),
            "version": os.getenv("RENDER_GIT_COMMIT", ""),
            "session_backend": "postgresql" if os.getenv("DATABASE_URL") else "memory",
            "store_connected": os.getenv("SUITE_DRIVE_ONLY", "true").lower() == "false"}


_mounts = [r for r in fastapi_app.routes if (isinstance(r, Mount) and r.path in {"", "/"}) or getattr(r,"path",None) == "/{tool_path:path}"]
fastapi_app.router.routes[:] = [r for r in fastapi_app.routes if r not in _mounts] + _mounts

from app_security import SecurityMiddleware
import app as session_runtime
from catalog_platform.rbac import RoleMiddleware
from catalog_platform.web_sessions import restore as restore_browser_session
fastapi_app.add_middleware(RoleMiddleware,sessions=lambda:session_runtime.SESSIONS)
fastapi_app.add_middleware(SecurityMiddleware, sessions=lambda: session_runtime.SESSIONS,
                          expire=getattr(session_runtime, "_eliminar_sesion", None),
                          restore=restore_browser_session)
