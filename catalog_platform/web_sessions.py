"""Encrypted browser sessions in the existing account table; no schema change."""

import hashlib
import re
import secrets
import time
from threading import RLock

from sqlalchemy import delete, select

from .accounts import put
from .database import configured, transaction
from .models import IntegrationAccount
from .security import member, unseal

_lock = RLock()
_fields = ("email", "creds", "expires_at", "file_namespace")


def _tenant(sid):
    if not isinstance(sid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{32,80}", sid):
        return None
    return "session:" + hashlib.sha256(sid.encode()).hexdigest()


def save(sid, value):
    tenant = _tenant(sid)
    if not configured() or not tenant or not value.get("email") or not value.get("creds"):
        return
    value.setdefault("file_namespace", secrets.token_urlsafe(24))
    data = {key: value[key] for key in _fields if key in value}
    with _lock, transaction() as db:
        put(db, tenant, value["email"], "web_session", data)
    value["_persistent_session"] = True


def revoke(sid):
    tenant = _tenant(sid)
    if configured() and tenant:
        with _lock, transaction() as db:
            db.execute(delete(IntegrationAccount).where(
                IntegrationAccount.tenant_id == tenant,
                IntegrationAccount.provider == "web_session"))


def restore(sid):
    import app as runtime
    from oauth_guard import email_allowed

    tenant = _tenant(sid)
    if not tenant:
        return None
    with _lock:
        cached = runtime.SESSIONS.get(sid)
        if not configured():
            return cached
        # Trusted process sessions predating this change are saved on first use.
        if cached and not cached.get("_persistent_session"):
            save(sid, cached)
            if not cached.get("_persistent_session"):
                return cached  # Historical/test sessions without Google credentials.
        with transaction() as db:
            record = db.scalar(select(IntegrationAccount).where(
                IntegrationAccount.tenant_id == tenant,
                IntegrationAccount.provider == "web_session"))
            data = unseal(record.encrypted_credentials) if record and record.status == "connected" else None
        if (not data or data.get("expires_at", 0) <= time.time()
                or not data.get("creds") or not member(data.get("email", ""))
                or not email_allowed(data.get("email", ""))):
            runtime.SESSIONS.pop(sid, None)
            return None
        if cached:
            return cached  # Keep active draft/job references and refreshed Google tokens.
        value = {key: data[key] for key in _fields if key in data}
        value.update(session_id=sid, _persistent_session=True)
        from .accounts import restore as restore_profile
        restore_profile(value)
        runtime.SESSIONS[sid] = value
        return value
