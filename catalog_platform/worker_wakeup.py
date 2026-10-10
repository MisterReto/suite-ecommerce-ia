"""Wake a free Render web worker for actual queued work; never keep it alive."""
# Aviso de arranque al worker gratuito mediante su health público, sin credenciales.
# Guía: docs/CODE_GUIDE.md; funciones y objetos: docs/FUNCTION_INDEX.md.

import logging
import os
import re
import threading
import time
from urllib.parse import urlsplit
import requests

log = logging.getLogger("rincon.worker-wakeup")
_lock = threading.Lock()
_pending = False
_last_attempt = 0.0


# Valida el origen HTTPS onrender.com del worker antes de construir la URL de salud.
def health_url():
    origin = os.getenv("IMAGE_WORKER_ORIGIN", "").rstrip("/")
    if not origin:
        return None
    value = urlsplit(origin)
    if (
        value.scheme != "https"
        or not re.fullmatch(r"[a-z0-9][a-z0-9-]*\.onrender\.com", value.netloc)
        or value.path or value.query or value.fragment
    ):
        raise RuntimeError("IMAGE_WORKER_ORIGIN debe ser el origen HTTPS onrender.com del worker.")
    return origin + "/service-health"


# Indica si hay un worker gratuito configurado que pueda recibir el aviso de arranque.
def configured():
    try:
        return bool(health_url()) and os.getenv("GENERATION_QUEUE_BACKEND") == "rq"
    except (ValueError, RuntimeError):
        return False


# Agrupa avisos concurrentes de trabajos confirmados en un hilo de arranque.
def notify():
    """Coalesce cold starts in a daemon; accepted HTTP requests do not wait."""
    global _pending, _last_attempt
    if not configured():
        return False
    with _lock:
        if _pending or time.monotonic() - _last_attempt < 30:
            return False
        _pending = True
        _last_attempt = time.monotonic()
    try:
        threading.Thread(target=_wake, name="image-worker-wakeup", daemon=True).start()
    except RuntimeError:
        with _lock:
            _pending = False
        log.warning("Wake pendiente; el trabajo permanece guardado en SQL.")
        return False
    return True


# Hace una lectura de salud sin cookies ni secretos y con tiempo limitado; no genera ni
# reintenta una escritura.
def _wake():
    global _pending
    try:
        # Public health carries no credentials, job payload, cookies or API keys.
        # Render starts the service before routing the HTTP request to it.
        with requests.get(health_url(), timeout=(5, 90), allow_redirects=False) as response:
            if response.status_code != 200:
                log.warning("Worker pendiente de arranque; el trabajo permanece en SQL.")
    except (requests.RequestException, ValueError, RuntimeError):
        log.warning("No se pudo despertar el worker; el trabajo permanece en SQL.")
    finally:
        with _lock:
            _pending = False
