# Cifrado de conexiones y comprobación de pertenencia/rol del usuario.
# Guía: docs/CODE_GUIDE.md; funciones y objetos: docs/FUNCTION_INDEX.md.
import json
import os
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException


# Valida la clave de cifrado compartida; cambiarla sin migración impediría leer conexiones
# existentes.
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


# Cifra un objeto JSON antes de guardarlo como credenciales.
def seal(data):
    return cipher().encrypt(json.dumps(data, ensure_ascii=False).encode()).decode()


# Descifra y reconstruye una conexión; informa el fallo sin revelar su contenido.
def unseal(data):
    try:
        return json.loads(cipher().decrypt(data.encode()))
    except InvalidToken:
        raise RuntimeError(
            "No se pudo abrir la conexión cifrada; revisa la clave del servidor."
        ) from None


# Resuelve admin, editor o viewer desde la configuración y valida el formato del mapa de
# roles.
def role_for(email):
    from access_policy import role_for as resolve
    return resolve(email)


# Comprueba la pertenencia del correo al catálogo autorizado.
def member(email):
    from access_policy import catalog_member
    return catalog_member(email)


# Rechaza en servidor una operación si el usuario no pertenece al catálogo o carece del rol
# requerido.
def require_role(value, *roles):
    if (
        not member(value.get("email", ""))
        or role_for(value.get("email", "")) not in roles
    ):
        raise HTTPException(403, "Tu rol no permite esta operación.")
