import json
import os
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException


def cipher():
    key = os.getenv("CREDENTIAL_ENCRYPTION_KEY", "")
    if not key:
        raise RuntimeError(
            "Configura CREDENTIAL_ENCRYPTION_KEY para almacenar conexiones cifradas."
        )
    try:
        return Fernet(key.encode())
    except ValueError:
        raise RuntimeError(
            "CREDENTIAL_ENCRYPTION_KEY tiene formato inválido."
        ) from None


def seal(data):
    return cipher().encrypt(json.dumps(data, ensure_ascii=False).encode()).decode()


def unseal(data):
    try:
        return json.loads(cipher().decrypt(data.encode()))
    except InvalidToken:
        raise RuntimeError(
            "No se pudo abrir la conexión cifrada; revisa la clave del servidor."
        ) from None


def role_for(email):
    try:
        roles = json.loads(os.getenv("APP_ROLE_MAP", "{}"))
    except ValueError:
        raise RuntimeError("APP_ROLE_MAP debe ser JSON de correos y roles.") from None
    if not isinstance(roles, dict):
        raise RuntimeError("APP_ROLE_MAP debe ser un objeto de correos y roles.")
    roles = {str(key).casefold(): value for key, value in roles.items()}
    fallback = "viewer" if os.getenv("DATABASE_URL") else "editor"
    role = roles.get(email.casefold(), os.getenv("APP_DEFAULT_ROLE", fallback))
    if role not in {"admin", "editor", "viewer"}:
        raise RuntimeError("Rol configurado inválido.")
    return role


def member(email):
    if not os.getenv("DATABASE_URL") and not os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"):
        return True
    try:
        roles = json.loads(os.getenv("APP_ROLE_MAP", "{}"))
    except ValueError:
        return False
    if not isinstance(roles, dict):
        return False
    return email.casefold() in {str(key).casefold() for key in roles}


def require_role(value, *roles):
    if (
        not member(value.get("email", ""))
        or role_for(value.get("email", "")) not in roles
    ):
        raise HTTPException(403, "Tu rol no permite esta operación.")
