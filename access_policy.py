"""Shared Render access policy for OAuth, catalog, sessions and workers."""
import hashlib
import json
import os
import re

ROLES = {"admin", "editor", "viewer"}


def email_key(email):
    return str(email or "").strip().casefold()


def allowed_emails():
    raw = os.getenv("APP_ALLOWED_EMAILS", "").strip()
    if raw.startswith("["):
        try:
            values = json.loads(raw)
        except ValueError:
            raise RuntimeError("APP_ALLOWED_EMAILS debe ser una lista de correos válida.") from None
        if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
            raise RuntimeError("APP_ALLOWED_EMAILS debe contener correos de texto.")
    else:
        values = re.split(r"[,;\s]+", raw)
    return {email_key(value) for value in values if email_key(value)}


def configured_roles():
    try:
        roles = json.loads(os.getenv("APP_ROLE_MAP", "{}"))
    except ValueError:
        raise RuntimeError("APP_ROLE_MAP debe ser JSON de correos y roles.") from None
    if not isinstance(roles, dict):
        raise RuntimeError("APP_ROLE_MAP debe ser un objeto de correos y roles.")
    result = {}
    for key, value in roles.items():
        key = email_key(key)
        role = str(value).strip().casefold()
        if key in result and result[key] != role:
            raise RuntimeError("APP_ROLE_MAP contiene roles contradictorios para un correo.")
        if key:
            result[key] = role
    return result


def default_role():
    fallback = "viewer" if os.getenv("DATABASE_URL") else "editor"
    role = os.getenv("APP_DEFAULT_ROLE", fallback).strip().casefold()
    if role not in ROLES:
        raise RuntimeError("Rol configurado inválido.")
    return role


def login_allowed(email):
    email = email_key(email)
    if not email:
        return False
    try:
        allowed = allowed_emails()
        if allowed:
            return email in allowed
        if os.getenv("APP_REQUIRE_ALLOWLIST", "false").strip().casefold() == "true":
            return configured_roles().get(email) in ROLES
        return True
    except RuntimeError:
        return False


def catalog_member(email):
    email = email_key(email)
    if not login_allowed(email):
        return False
    if not os.getenv("DATABASE_URL") and not os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"):
        return True
    try:
        roles = configured_roles()
        if email in roles:
            return roles[email] in ROLES
        # An explicitly allowed user is a member even without a per-user role.
        # Their configured default role still controls every write operation.
        return email in allowed_emails() and default_role() in ROLES
    except RuntimeError:
        return False


def role_for(email):
    roles = configured_roles()
    role = roles[email_key(email)] if email_key(email) in roles else default_role()
    if role not in ROLES:
        raise RuntimeError("Rol configurado inválido.")
    return role


def status():
    """Compare services without exposing email addresses or secret values."""
    try:
        allowed, roles, fallback = allowed_emails(), configured_roles(), default_role()
        candidates = allowed or set(roles)
        effective = {email: roles.get(email, fallback) for email in candidates if catalog_member(email)}
        digest = hashlib.sha256(json.dumps(effective, sort_keys=True).encode()).hexdigest()
        return {"configured": True, "members": len(effective),
                "explicit_roles": len(roles), "allowed_without_role": len(allowed - roles.keys()),
                "roles": {role: sum(value == role for value in effective.values()) for role in sorted(ROLES)},
                "default_role": fallback, "fingerprint": digest,
                "dedicated_drive": bool(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"))}
    except RuntimeError as exc:
        return {"configured": False, "message": str(exc)}
