"""Single-process session and OAuth state lifecycle for the internal suite."""
import os
import secrets
import shutil
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

LOCK = threading.RLock()
SESSIONS = {}
OAUTH_STATES = {}
SESSION_TTL = 8 * 3600
WORK_ROOT = Path(tempfile.mkdtemp(prefix="ecommerce-private-"))


def drop_session(sid):
    with LOCK:
        session = SESSIONS.pop(sid, None)
    if session and session.get("workdir"):
        shutil.rmtree(session["workdir"], ignore_errors=True)


def get_session(sid):
    now = time.time()
    with LOCK:
        for key, value in list(SESSIONS.items()):
            if value.get("expires_at", 0) <= now:
                drop_session(key)
        return SESSIONS.get(sid)


def create_session(sid, **values):
    get_session(None)
    with LOCK:
        if len(SESSIONS) >= 200:
            raise RuntimeError("Capacidad de sesiones agotada")
        SESSIONS[sid] = dict(values, session_id=sid, expires_at=time.time() + SESSION_TTL,
                             workdir=tempfile.mkdtemp(dir=WORK_ROOT))


def session_path(session, suffix=".jpg"):
    if get_session(session.get("session_id")) is not session:
        raise ValueError("Sesión expirada")
    return str(Path(session["workdir"]) / (secrets.token_hex(16) + suffix))


def owned_paths(session, paths):
    root = Path(session["workdir"]).resolve()
    if not isinstance(paths, (list, tuple)):
        paths = [paths]
    result = []
    for path in paths:
        resolved = Path(path).resolve()
        if not resolved.is_relative_to(root) or not resolved.is_file():
            raise ValueError("Referencia ajena a la sesión")
        result.append(str(resolved))
    return result


def register_file(session, path):
    resolved = str(Path(path).resolve())
    with LOCK:
        session.setdefault("allowed_files", set()).add(resolved)
    return resolved


def file_allowed(session, path):
    if not session or not isinstance(path, str) or "://" in path:
        return False
    try:
        return str(Path(path).resolve()) in session.get("allowed_files", set())
    except (ValueError, OSError):
        return False


def validate_file_data(session, value):
    if isinstance(value, dict):
        # Gradio can fill in missing FileData metadata during validation.
        if "path" in value:
            if not file_allowed(session, value.get("path")):
                raise ValueError("Archivo ajeno a la sesión")
        for item in value.values():
            validate_file_data(session, item)
    elif isinstance(value, list):
        for item in value:
            validate_file_data(session, item)


def bind_queue_session(session, session_hash):
    if not isinstance(session_hash, str) or not 1 <= len(session_hash) <= 128:
        raise ValueError("Identificador inválido")
    with LOCK:
        for other in SESSIONS.values():
            if other is not session and session_hash in other.get("queue_hashes", set()):
                raise ValueError("Cola ajena a la sesión")
        hashes = session.setdefault("queue_hashes", set())
        if len(hashes) >= 100 and session_hash not in hashes:
            raise ValueError("Demasiadas pestañas")
        hashes.add(session_hash)


def issue_oauth(state, verifier):
    with LOCK:
        now = time.time()
        for key in list(OAUTH_STATES):
            if OAUTH_STATES[key][0] <= now:
                del OAUTH_STATES[key]
        if len(OAUTH_STATES) >= 500:
            raise RuntimeError("Demasiados inicios de sesión pendientes")
        OAUTH_STATES[state] = (now + 600, verifier)


def consume_oauth(cookie_state, query_state):
    if not cookie_state or not query_state or not secrets.compare_digest(cookie_state, query_state):
        raise ValueError("Estado OAuth inválido")
    with LOCK:
        pending = OAUTH_STATES.pop(cookie_state, None)
    if not pending or pending[0] <= time.time():
        raise ValueError("Estado OAuth expirado o ya usado")
    return pending[1]


def email_allowed(email, setting="APP_ALLOWED_EMAILS", *, default=True):
    allowed = {x.strip().lower() for x in os.getenv(setting, "").split(",") if x.strip()}
    return email.lower() in allowed if allowed else default


def same_origin(headers, expected):
    if headers.get("sec-fetch-site") == "cross-site":
        return False
    origin = headers.get("origin")
    if not origin:
        return False
    return origin == expected


def public_origin(callback):
    parsed = urlsplit(callback)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise RuntimeError("GOOGLE_REDIRECT_URI debe usar HTTPS sin credenciales")
    return f"https://{parsed.netloc}"
