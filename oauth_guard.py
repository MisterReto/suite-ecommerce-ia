"""Bounded, one-use Google OAuth state. Compatible with the production session runtime."""
# Estado OAuth y PKCE de un solo uso, con caducidad y lista de correos autorizados.
# Guía: docs/CODE_GUIDE.md; funciones y objetos: docs/FUNCTION_INDEX.md.
import secrets
import threading
import time

_pending = {}
_lock = threading.Lock()


# Registra estado y verificador PKCE durante diez minutos, con límite de solicitudes
# pendientes; el registro es local al proceso API.
def issue_oauth(state, verifier):
    with _lock:
        now = time.time()
        for key in list(_pending):
            if _pending[key][0] <= now:
                del _pending[key]
        if len(_pending) >= 500:
            raise RuntimeError("Demasiados accesos pendientes")
        _pending[state] = (now + 600, verifier)


# Compara cookie y estado, consume el verificador una sola vez y rechaza estados caducados o
# reutilizados.
def consume_oauth(cookie_state, state):
    if not cookie_state or not state or not secrets.compare_digest(cookie_state, state):
        raise ValueError("Estado OAuth inválido")
    with _lock:
        pending = _pending.pop(state, None)
    if not pending or pending[0] <= time.time():
        raise ValueError("Estado OAuth expirado o ya usado")
    return pending[1]


# Comprueba la lista de acceso y, cuando se exige, los correos con rol configurado.
def email_allowed(email):
    from access_policy import login_allowed
    return login_allowed(email)
