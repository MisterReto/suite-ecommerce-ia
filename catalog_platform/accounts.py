"""Persist server credentials encrypted, scoped to the authenticated folder/user."""

import os
from sqlalchemy import select
from .models import IntegrationAccount
from .security import seal, unseal


def persist(db, tenant, actor, value):
    if not value.get("creds"):
        raise ValueError("Conecta Google Drive antes de preparar trabajos.")
    data = {
        key: value.get(key)
        for key in ("creds", "gemini_key", "carpeta_raiz_nombre_manual")
    }
    data["carpeta_raiz_id_manual"] = tenant
    record = db.scalar(
        select(IntegrationAccount).where(
            IntegrationAccount.tenant_id == tenant,
            IntegrationAccount.actor == actor,
            IntegrationAccount.provider == "studio",
        )
    )
    encrypted = seal(data)
    if record:
        record.encrypted_credentials = encrypted
        record.status = "connected"
    else:
        db.add(
            IntegrationAccount(
                tenant_id=tenant,
                actor=actor,
                provider="studio",
                encrypted_credentials=encrypted,
            )
        )


def load(db, tenant, actor):
    record = db.scalar(
        select(IntegrationAccount).where(
            IntegrationAccount.tenant_id == tenant,
            IntegrationAccount.actor == actor,
            IntegrationAccount.provider == "studio",
            IntegrationAccount.status == "connected",
        )
    )
    if not record:
        raise ValueError(
            "La conexión del usuario no está disponible. Conecta de nuevo y reintenta."
        )
    return unseal(record.encrypted_credentials)
