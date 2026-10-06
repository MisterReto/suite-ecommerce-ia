"""API entrypoint with optional UI hosting for the compatible deployment."""
import os
from starlette.routing import Mount

if os.getenv("SUITE_SERVICE_ROLE", "main").lower() == "sync":
    from sync_service import app as fastapi_app
else:
    from studio_api import app as fastapi_app
    import product_web


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


@fastapi_app.get("/service-health")
def service_health():
    return {"ok": True, "interface": "nextjs", "backend": "fastapi", "role": os.getenv("SUITE_SERVICE_ROLE", "main"),
            "remote_sync": bool(os.getenv("SYNC_SERVICE_URL")),
            "sync_url": os.getenv("SYNC_SERVICE_URL", ""),
            "service_id": os.getenv("RENDER_SERVICE_ID", ""),
            "version": os.getenv("RENDER_GIT_COMMIT", ""),
            "store_connected": os.getenv("SUITE_DRIVE_ONLY", "true").lower() == "false"}


_mounts = [r for r in fastapi_app.routes if (isinstance(r, Mount) and r.path in {"", "/"}) or getattr(r,"path",None) == "/{tool_path:path}"]
fastapi_app.router.routes[:] = [r for r in fastapi_app.routes if r not in _mounts] + _mounts

from app_security import SecurityMiddleware
import app as session_runtime
from catalog_platform.rbac import RoleMiddleware
fastapi_app.add_middleware(RoleMiddleware,sessions=lambda:session_runtime.SESSIONS)
fastapi_app.add_middleware(SecurityMiddleware, sessions=lambda: session_runtime.SESSIONS,
                          expire=getattr(session_runtime, "_eliminar_sesion", None))
