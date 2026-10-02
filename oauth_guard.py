"""Bounded, one-use Google OAuth state. Compatible with the production session runtime."""
import os
import secrets
import threading
import time

_pending = {}
_lock = threading.Lock()


def issue_oauth(state, verifier):
    with _lock:
        now = time.time()
        for key in list(_pending):
            if _pending[key][0] <= now:
                del _pending[key]
        if len(_pending) >= 500:
            raise RuntimeError("Demasiados accesos pendientes")
        _pending[state] = (now + 600, verifier)


def consume_oauth(cookie_state, state):
    if not cookie_state or not state or not secrets.compare_digest(cookie_state, state):
        raise ValueError("Estado OAuth inválido")
    with _lock:
        pending = _pending.pop(state, None)
    if not pending or pending[0] <= time.time():
        raise ValueError("Estado OAuth expirado o ya usado")
    return pending[1]


def email_allowed(email):
    allowed = {e.strip().casefold() for e in os.getenv("APP_ALLOWED_EMAILS", "").split(",") if e.strip()}
    return not allowed or email.casefold() in allowed
