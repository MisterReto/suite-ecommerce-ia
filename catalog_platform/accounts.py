"""Persist server credentials encrypted, scoped to the authenticated folder/user."""
# Conexiones Drive cifradas y preferencias personales; Gemini se configura en el servidor.
# Guía: docs/CODE_GUIDE.md; funciones y objetos: docs/FUNCTION_INDEX.md.

import hashlib
from sqlalchemy import select, func
from .models import IntegrationAccount
from .security import seal, unseal


# Busca una conexión por tenant, correo normalizado y proveedor.
def account(db, tenant, actor, provider):
    return db.scalar(select(IntegrationAccount).where(
        IntegrationAccount.tenant_id == tenant,
        func.lower(IntegrationAccount.actor) == actor.casefold(),
        IntegrationAccount.provider == provider))


# Serializa la actualización de conexión y cifra sus datos antes de almacenarlos.
def put(db, tenant, actor, provider, data, status="connected"):
    from .queue import request_lock
    request_lock(db, tenant, "credential:" + actor.casefold() + ":" + provider)
    record = account(db, tenant, actor, provider)
    if not record:
        record = IntegrationAccount(tenant_id=tenant, actor=actor.casefold(), provider=provider)
        db.add(record)
    record.encrypted_credentials, record.status = seal(data), status
    return record


# Devuelve únicamente la clave Gemini personal de una conexión vigente del usuario.
def gemini_for(db, tenant, actor):
    record = account(db, tenant, actor, "gemini")
    if not record or record.status != "connected":
        return None
    return unseal(record.encrypted_credentials).get("api_key")


# Deriva una clave estable de preferencias personales a partir del correo normalizado.
def profile_tenant(actor):
    return "user:" + hashlib.sha256(actor.casefold().encode()).hexdigest()


# Guarda la clave personal en la carpeta seleccionada y conserva esa carpeta en el perfil.
def save_gemini(db, tenant, actor, key, folder_name=""):
    if not tenant or not actor:
        raise ValueError("Selecciona tu tienda y conecta tu cuenta antes de guardar Gemini.")
    put(db, tenant, actor, "gemini", {"api_key": key})
    save_profile(db, tenant, actor, folder_name)


# Persiste la carpeta elegida por el usuario para restaurarla en una sesión posterior.
def save_profile(db, tenant, actor, folder_name=""):
    put(db, profile_tenant(actor), actor, "studio_profile",
        {"folder_id": tenant, "folder_name": folder_name})


# Marca la conexión como desconectada; un snapshot antiguo no debe recuperar una clave
# eliminada.
def delete_gemini(db, tenant, actor):
    # Keep a tombstone so old session snapshots never revive a deleted key.
    put(db, tenant, actor, "gemini", {}, "disconnected")


# Recupera la carpeta personal y aplica exclusivamente el secreto actual del servidor.
def restore(value):
    """Ignore personal credentials and stale snapshots, including after a rotation."""
    from .database import configured, transaction
    from .security import member
    from .gemini_config import apply_server_key
    allowed = member(value.get("email", ""))
    apply_server_key(value, allowed=allowed)
    if not configured():
        return
    actor = value.get("email", "")
    if not actor or not allowed:
        return
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


# Guarda las credenciales Drive cifradas para que el worker pueda actuar sin el navegador.
def persist(db, tenant, actor, value):
    if not value.get("creds"):
        raise ValueError("Conecta Google Drive antes de preparar trabajos.")
    data = {
        key: value.get(key)
        for key in ("creds", "carpeta_raiz_nombre_manual")
    }
    data["carpeta_raiz_id_manual"] = tenant
    put(db, tenant, actor, "studio", data)


# Reconstruye la conexión del actor para un trabajo; excluye claves globales presentes en
# snapshots antiguos.
def load(db, tenant, actor):
    record = account(db, tenant, actor, "studio")
    if not record or record.status != "connected":
        raise ValueError(
            "La conexión del usuario no está disponible. Conecta de nuevo y reintenta."
        )
    snapshot = unseal(record.encrypted_credentials)
    data = {key: snapshot[key] for key in ("creds", "carpeta_raiz_id_manual", "carpeta_raiz_nombre_manual") if key in snapshot}
    from .gemini_config import apply_server_key
    from .security import member
    apply_server_key(data, allowed=member(actor))
    return data
