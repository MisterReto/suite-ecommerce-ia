"""Bounded, one-use Google OAuth state. Compatible with the production session runtime."""
# Estado OAuth y PKCE de un solo uso, con caducidad y lista de correos autorizados.
# Guía: docs/CODE_GUIDE.md; funciones y objetos: docs/FUNCTION_INDEX.md.
import os
import json
import secrets
import threading
import time
from cryptography.fernet import InvalidToken

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
    # El ticket PKCE cifrado puede sobrevivir al reinicio de la API. Se mantiene
    # el estado efímero para la ruta habitual y las pruebas de consumo único.
    from catalog_platform.security import seal
    return seal({"state": state, "verifier": verifier})


# Compara cookie y estado, consume el verificador una sola vez y rechaza estados caducados o
# reutilizados.
def consume_oauth(cookie_state, state, ticket=None):
    if not cookie_state or not state or not secrets.compare_digest(cookie_state, state):
        raise ValueError("Estado OAuth inválido")
    with _lock:
        pending = _pending.pop(state, None)
    if pending and pending[0] > time.time():
        return pending[1]

    # El proceso pudo reiniciarse durante el consentimiento de Google. Recupera
    # únicamente un ticket íntegro y no expirado, ligado al state de la cookie.
    # El código de autorización de Google continúa siendo de un solo uso; las
    # cookies se eliminan tras finalizar el callback.
    if ticket:
        from catalog_platform.security import cipher
        try:
            data = json.loads(cipher().decrypt(ticket.encode(), ttl=600))
            if (isinstance(data, dict)
                    and isinstance(data.get("state"), str)
                    and secrets.compare_digest(data["state"], state)
                    and isinstance(data.get("verifier"), str)
                    and data["verifier"]):
                return data["verifier"]
        except (InvalidToken, ValueError, UnicodeError, TypeError):
            pass
    raise ValueError("Estado OAuth expirado o ya usado")


# Comprueba la lista de acceso y, cuando se exige, los correos con rol configurado.
def email_allowed(email):
    allowed = {e.strip().casefold() for e in os.getenv("APP_ALLOWED_EMAILS", "").split(",") if e.strip()}
    if not allowed and os.getenv("APP_REQUIRE_ALLOWLIST", "false").lower() == "true":
        try:
            roles = json.loads(os.getenv("APP_ROLE_MAP", "{}"))
        except ValueError:
            return False
        return isinstance(roles, dict) and email.casefold() in {
            str(key).casefold() for key, role in roles.items() if role in {"admin", "editor", "viewer"}}
    return not allowed or email.casefold() in allowed
