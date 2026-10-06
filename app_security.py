"""HTTP defenses shared by both public services; never records request bodies."""
from collections import OrderedDict, deque
import html
import io
from PIL import Image
import ipaddress
import os
import time
from threading import Lock
from urllib.parse import urlparse

import bleach
from starlette.requests import Request
from starlette.responses import JSONResponse
from sync_bridge_protocol import STORE_CONTEXT, STORE_KEYS


def clean_html(value):
    return bleach.clean(str(value or ""), tags={"p", "br", "ul", "ol", "li", "strong", "b", "em", "i", "a"},
        attributes={"a": ["href", "title"]}, protocols={"https", "http"}, strip=True)


def validate_service_url(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Las conexiones externas requieren una URL HTTPS sin credenciales ni parámetros.")
    host = parsed.hostname.casefold()
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise ValueError("No se permiten destinos internos.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address and not address.is_global:
        raise ValueError("No se permiten direcciones privadas ni locales.")
    return url



def checked_image_type(filename, data):
    if not filename or any(c in filename for c in '\r\n"\\/'):
        raise ValueError("Nombre de imagen inválido.")
    if len(data) > 12_000_000:
        raise ValueError("La imagen supera el límite de 12 MB.")
    if filename.rsplit(".", 1)[-1].casefold() not in {"jpg", "jpeg", "png", "webp", "gif", "avif"}:
        raise ValueError("Solo se permiten imágenes JPG, PNG, WebP, GIF o AVIF.")
    try:
        with Image.open(io.BytesIO(data)) as image:
            mime = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp", "GIF": "image/gif", "AVIF": "image/avif"}.get(image.format)
            if not mime or image.width * image.height > 24_000_000:
                raise ValueError("Formato o dimensiones de imagen no permitidos.")
            image.verify()
        return mime
    except Exception as exc:
        raise ValueError("La imagen no es válida o supera las dimensiones permitidas.") from exc


def public_error(exc):
    if not isinstance(exc, (ValueError, RuntimeError)):
        return "No se pudo confirmar la operación. Revisa su estado antes de reintentar."
    message = str(exc)
    values = dict(STORE_CONTEXT.get())
    values.update({key: os.getenv(key, "") for key in (*STORE_KEYS, "GOOGLE_CLIENT_SECRET", "SYNC_SERVICE_SHARED_KEY", "CREDENTIAL_ENCRYPTION_KEY", "AI_API_KEY", "GOOGLE_REFRESH_TOKEN", "DATABASE_URL", "REDIS_URL", "LOYVERSE_ACCESS_TOKEN", "GOOGLE_SERVICE_ACCOUNT_JSON")})
    for key, value in values.items():
        if any(part in key for part in ("SECRET", "KEY", "PASSWORD", "TOKEN", "DATABASE_URL", "REDIS_URL", "SERVICE_ACCOUNT")) and isinstance(value, str) and len(value) >= 6:
            message = message.replace(value, "[REDACTED]")
    return html.escape(message[:300])


class WindowLimiter:
    def __init__(self, maximum=4096):
        self.entries = OrderedDict()
        self.lock = Lock()
        self.maximum = maximum

    def allow(self, key, limit, seconds=60):
        now = time.monotonic()
        with self.lock:
            queue = self.entries.pop(key, deque())
            while queue and queue[0] <= now - seconds:
                queue.popleft()
            allowed = len(queue) < limit
            if allowed:
                queue.append(now)
            self.entries[key] = queue
            while len(self.entries) > self.maximum:
                self.entries.popitem(last=False)
            return allowed


class SecurityMiddleware:
    def __init__(self, app, sessions=lambda: {}, expire=None):
        self.app, self.sessions = app, sessions
        self.limiter = WindowLimiter()
        self.busy, self.lock = 0, Lock()
        self.expire = expire or (lambda key: self.sessions().pop(key, None))

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request = Request(scope)
        path, method = request.url.path, request.method
        sid = request.cookies.get("sync_session") or request.cookies.get("session_id")
        session = self.sessions().get(sid) if sid else None
        if session and session.get("expires_at", 0) <= time.time():
            self.expire(sid)
            session = None
        upload = path == "/api/uploads"
        user_file = path.startswith("/api/files/")
        policy = b"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; font-src 'self' data:; img-src 'self' data: blob: https:; connect-src 'self'; worker-src 'self' blob:; frame-src 'self'; frame-ancestors 'self'; object-src 'none'; base-uri 'self'; form-action 'self'"
        original_send = send
        async def secure_send(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend([
                    (b"x-content-type-options", b"nosniff"), (b"x-frame-options", b"SAMEORIGIN"),
                    (b"referrer-policy", b"no-referrer"), (b"strict-transport-security", b"max-age=31536000"),
                    (b"permissions-policy", b"camera=(self), microphone=(), geolocation=()"),
                    (b"content-security-policy", policy),
                ])
                if request.cookies.get("sync_session") or request.cookies.get("session_id") or path in {"/internal/tools", "/sync-handoff/redeem"} or path.startswith(("/session/", "/auth/", "/sync-", "/api/")):
                    headers = [(key, val) for key, val in headers if key.lower() != b"cache-control"]
                    headers.append((b"cache-control", b"no-store"))
                message = dict(message, headers=headers)
            await original_send(message)
        send = secure_send
        external = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
        if external and request.url.netloc != urlparse(external).netloc:
            return await JSONResponse({"error": "Host no autorizado."}, status_code=400)(scope, receive, send)
        # The separate Next.js service proxies to this API on the user's origin.
        # Keep API Host validation above; never trust a caller's forwarded host.
        public = os.getenv("APP_PUBLIC_ORIGIN", "").rstrip("/")
        if public:
            parsed = urlparse(public)
            if (parsed.scheme != "https" or not parsed.netloc or parsed.username
                    or parsed.password or parsed.path or parsed.query or parsed.fragment):
                return await JSONResponse({"error": "Configura APP_PUBLIC_ORIGIN como origen HTTPS."},
                                          status_code=503)(scope, receive, send)
        origin = public or external or str(request.base_url).rstrip("/")
        internal = path in {"/internal/tools", "/sync-handoff/redeem", "/webhooks/woocommerce", "/webhooks/loyverse", "/api/webhooks/woocommerce", "/api/webhooks/loyverse"}
        paid = path == "/api/generate" or path == "/api/platform/generation/jobs" or (
            path.startswith(("/api/images/", "/api/platform/assets/")) and path.endswith(("/correct", "/regenerate")))
        if method == "POST" and paid and session:
            limit = int(os.getenv("GENERATION_REQUESTS_PER_MINUTE", "12"))
            if not self.limiter.allow((sid, "generation"), limit):
                return await JSONResponse({"error": "Demasiadas solicitudes de generación. Revisa los trabajos activos."},
                    status_code=429, headers={"retry-after": "60"})(scope, receive, send)
        if method not in {"GET", "HEAD", "OPTIONS"} and not internal:
            source = request.headers.get("origin")
            referer = request.headers.get("referer", "")
            if source is None and referer:
                parts = urlparse(referer)
                source = f"{parts.scheme}://{parts.netloc}"
            if source != origin:
                return await JSONResponse({"error": "Origen no autorizado."}, status_code=403)(scope, receive, send)
        peer = request.client.host if request.client else "unknown"
        if not self.limiter.allow((peer, "all"), 600) or (
            path in {"/login", "/auth/callback", "/session/start", "/sync-handoff/redeem"}
            and not self.limiter.allow((peer, "auth"), 30, 300)
        ):
            return await JSONResponse({"error": "Demasiadas solicitudes. Intenta en un minuto."}, status_code=429,
                headers={"retry-after": "60"})(scope, receive, send)
        if (upload or user_file) and not session:
            return await JSONResponse({"error": "Conecta Google Drive antes de subir imágenes."}, status_code=401)(scope, receive, send)
        maximum = 12_100_000 if upload else 2_100_000 if path == "/api/platform/import/file" else 2_000_000 if internal else 512_000
        raw = bytearray()
        if method in {"POST", "PUT", "PATCH"}:
            try:
                if int(request.headers.get("content-length", "0")) > maximum:
                    raise ValueError()
                more = True
                while more:
                    event = await receive()
                    if event["type"] == "http.disconnect":
                        return
                    raw.extend(event.get("body", b""))
                    more = event.get("more_body", False)
                    if len(raw) > maximum:
                        raise ValueError()
            except ValueError:
                return await JSONResponse({"error": "Archivo o solicitud demasiado grande."}, status_code=413)(scope, receive, send)
            consumed = False
            async def buffered():
                nonlocal consumed
                if not consumed:
                    consumed = True
                    return {"type": "http.request", "body": bytes(raw), "more_body": False}
                return await receive()
            input_receive = buffered
        else:
            input_receive = receive
        heavy = path in {"/batch-step", "/product-sync-one", "/image-sync-one", "/inventory-count-bulk", "/inventory-movement", "/inventory-review", "/stock-preview-start", "/woocommerce-publish-preview"}
        if heavy:
            with self.lock:
                available = self.busy < 3
                if available:
                    self.busy += 1
            if not available:
                return await JSONResponse({"error": "Hay operaciones en curso. Espera a que terminen."}, status_code=429)(scope, receive, send)
        try:
            await self.app(scope, input_receive, send)
        finally:
            if heavy:
                with self.lock:
                    self.busy -= 1
