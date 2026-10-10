"""Persist server credentials encrypted, scoped to the authenticated folder/user."""

import hashlib
import os
from sqlalchemy import select, func
from .models import IntegrationAccount
from .security import seal, unseal


def account(db, tenant, actor, provider):
    return db.scalar(select(IntegrationAccount).where(
        IntegrationAccount.tenant_id == tenant,
        func.lower(IntegrationAccount.actor) == actor.casefold(),
        IntegrationAccount.provider == provider))


def put(db, tenant, actor, provider, data, status="connected"):
    from .queue import request_lock
    request_lock(db, tenant, "credential:" + actor.casefold() + ":" + provider)
    record = account(db, tenant, actor, provider)
    if not record:
        record = IntegrationAccount(tenant_id=tenant, actor=actor.casefold(), provider=provider)
        db.add(record)
    record.encrypted_credentials, record.status = seal(data), status
    return record


def gemini_for(db, tenant, actor):
    record = account(db, tenant, actor, "gemini")
    if not record or record.status != "connected":
        return None
    return unseal(record.encrypted_credentials).get("api_key")


def profile_tenant(actor):
    return "user:" + hashlib.sha256(actor.casefold().encode()).hexdigest()


def save_gemini(db, tenant, actor, key, folder_name=""):
    if not tenant or not actor:
        raise ValueError("Selecciona tu tienda y conecta tu cuenta antes de guardar Gemini.")
    put(db, tenant, actor, "gemini", {"api_key": key})
    save_profile(db, tenant, actor, folder_name)


def save_profile(db, tenant, actor, folder_name=""):
    put(db, profile_tenant(actor), actor, "studio_profile",
        {"folder_id": tenant, "folder_name": folder_name})


def delete_gemini(db, tenant, actor):
    # Keep a tombstone so old session snapshots never revive a deleted key.
    put(db, tenant, actor, "gemini", {}, "disconnected")


def restore(value):
    """Resolve a personal key on every request. No environment-key fallback."""
    from .database import configured, transaction
    from .security import member
    if not configured():
        return  # Compatibility with the historical session-only service.
    actor = value.get("email", "")
    if not actor or not member(actor):
        value.pop("gemini_key", None)
        value["gemini_source"] = "not_configured"
        return
    key = None
    with transaction() as db:
        root = value.get("platform_tenant") or value.get("carpeta_raiz_id_manual")
        if not root:
            profile = account(db, profile_tenant(actor), actor, "studio_profile")
            if profile and profile.status == "connected":
                preferences = unseal(profile.encrypted_credentials)
                root = preferences.get("folder_id")
                if root:
                    value["carpeta_raiz_id_manual"] = root
                    value["carpeta_raiz_nombre_manual"] = preferences.get("folder_name", "")
        root = root or os.getenv("GOOGLE_DRIVE_FOLDER_ID")
        if root:
            key = gemini_for(db, root, actor)
    # Requests and the analysis thread share this dictionary. A slow refresh
    # must not remove a valid key while an already authorized operation reads it.
    if key:
        value.update(gemini_key=key, gemini_source="user_settings")
    else:
        value.pop("gemini_key", None)
        value["gemini_source"] = "not_configured"


def persist(db, tenant, actor, value):
    if not value.get("creds"):
        raise ValueError("Conecta Google Drive antes de preparar trabajos.")
    data = {
        key: value.get(key)
        for key in ("creds", "carpeta_raiz_nombre_manual")
    }
    data["carpeta_raiz_id_manual"] = tenant
    put(db, tenant, actor, "studio", data)


def load(db, tenant, actor):
    record = account(db, tenant, actor, "studio")
    if not record or record.status != "connected":
        raise ValueError(
            "La conexión del usuario no está disponible. Conecta de nuevo y reintenta."
        )
    data = unseal(record.encrypted_credentials)
    data.pop("gemini_key", None)  # Old snapshots may contain a global Render key.
    key = gemini_for(db, tenant, actor)
    if key:
        data.update(gemini_key=key, gemini_source="user_settings")
    return data
