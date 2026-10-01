"""One image, two independent Render processes selected by role."""
import os
from starlette.routing import Mount

if os.getenv("SUITE_SERVICE_ROLE", "main").lower() == "sync":
    from sync_service import app as fastapi_app
else:
    from product_web_ai import fastapi_app


@fastapi_app.get("/service-health")
def service_health():
    return {"ok": True, "role": os.getenv("SUITE_SERVICE_ROLE", "main"),
            "remote_sync": bool(os.getenv("SYNC_SERVICE_URL")),
            "sync_url": os.getenv("SYNC_SERVICE_URL", ""),
            "service_id": os.getenv("RENDER_SERVICE_ID", ""),
            "version": os.getenv("RENDER_GIT_COMMIT", ""),
            "store_connected": os.getenv("SUITE_DRIVE_ONLY", "true").lower() == "false"}


_mounts = [r for r in fastapi_app.routes if isinstance(r, Mount) and r.path in {"", "/"}]
fastapi_app.router.routes[:] = [r for r in fastapi_app.routes if r not in _mounts] + _mounts
