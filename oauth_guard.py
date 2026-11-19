"""Bounded, one-use Google OAuth state. Compatible with the production session runtime."""
# Estado OAuth y PKCE de un solo uso, con caducidad y lista de correos autorizados.
# Guía: docs/CODE_GUIDE.md; funciones y objetos: docs/FUNCTION_INDEX.md.
import hashlib
import os
import json
import secrets
import threading
import time

_pending = {}
_lock = threading.Lock()


# The sorted set bounds outstanding authorizations across API replicas. Redis
# expires the encrypted values independently, including abandoned callbacks.
_ISSUE = """
local now = tonumber(redis.call('TIME')[1])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now)
if redis.call('ZCARD', KEYS[1]) >= 500 then return 0 end
if not redis.call('SET', KEYS[2], ARGV[1], 'EX', 600, 'NX') then return 0 end
redis.call('ZADD', KEYS[1], now + 600, KEYS[2])
redis.call('EXPIRE', KEYS[1], 601)
return 1
"""
_CONSUME = """
local verifier = redis.call('GET', KEYS[2])
redis.call('DEL', KEYS[2])
redis.call('ZREM', KEYS[1], KEYS[2])
return verifier
"""


def _redis_keys(state):
    client = os.environ.get("GOOGLE_CLIENT_ID", "").encode()
    prefix = "rincon:oauth:{" + hashlib.sha256(client).hexdigest() + "}:"
    return prefix + "pending", prefix + hashlib.sha256(state.encode()).hexdigest()


def issue_oauth(state, verifier):
    if os.getenv("REDIS_URL") and os.getenv("CREDENTIAL_ENCRYPTION_KEY"):
        from catalog_platform.redis_broker import connection, reachable
        from catalog_platform.security import seal
        if reachable():
            # Choose one store before issuing. An ambiguous Redis write must
            # never create a second consumable copy in the local fallback.
            if not connection().eval(_ISSUE, 2, *_redis_keys(state), seal(verifier)):
                raise RuntimeError("Demasiados accesos pendientes")
            return
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
    if pending and pending[0] > time.time():
        return pending[1]
    if os.getenv("REDIS_URL") and os.getenv("CREDENTIAL_ENCRYPTION_KEY"):
        from catalog_platform.redis_broker import connection
        from catalog_platform.security import unseal
        sealed = connection().eval(_CONSUME, 2, *_redis_keys(state))
        if sealed:
            return unseal(sealed.decode())
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
