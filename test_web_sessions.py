"""Browser session recovery across API restarts; providers and data are synthetic."""
import json
import secrets
import time
from unittest.mock import Mock

from sqlalchemy import select

from test_catalog_platform import setup, ORIGIN
import studio_api as studio
from catalog_platform.database import transaction
from catalog_platform.models import IntegrationAccount
from catalog_platform.security import seal, unseal
from catalog_platform import web_sessions


def record(sid):
    with transaction() as db:
        return db.scalar(select(IntegrationAccount).where(
            IntegrationAccount.tenant_id == web_sessions._tenant(sid),
            IntegrationAccount.provider == "web_session"))


def test_oauth_session_survives_restart_and_preserves_secure_cookie(setup, monkeypatch):
    client, value, _ = setup
    runtime = studio.runtime
    state = secrets.token_urlsafe(24)
    from oauth_guard import issue_oauth
    issue_oauth(state, "one-use-test-verifier")
    flow = Mock()
    credentials = {"token": "test-google-token", "refresh_token": "test-refresh-token"}
    flow.credentials.to_json.return_value = json.dumps(credentials)
    monkeypatch.setattr(runtime.Flow, "from_client_config", Mock(return_value=flow))
    service = Mock()
    service.userinfo.return_value.get.return_value.execute.return_value = {
        "email": value["email"], "verified_email": True}
    monkeypatch.setattr(runtime, "build", Mock(return_value=service))
    client.cookies.set("oauth_state", state)
    callback = client.get("/auth/callback", params={"state": state, "code": "test-code"}, follow_redirects=False)
    assert callback.status_code == 307
    sid = next(c.value for c in client.cookies.jar if c.name == "session_id" and c.value != value["session_id"])
    header = next(h for h in callback.headers.get_list("set-cookie") if h.startswith("session_id="))
    assert all(flag in header for flag in ("HttpOnly", "Secure", "SameSite=lax", "Max-Age=28800", "Path=/"))
    saved = record(sid)
    assert sid not in saved.tenant_id
    assert "test-google-token" not in saved.encrypted_credentials
    assert "gemini_key" not in unseal(saved.encrypted_credentials)
    expires = runtime.SESSIONS[sid]["expires_at"]
    namespace = runtime.SESSIONS[sid]["file_namespace"]
    runtime.SESSIONS.pop(sid)  # A cold process has no cached browser sessions.
    client.cookies.clear()
    client.cookies.set("session_id", sid)
    restored = client.get("/api/session")
    assert restored.status_code == 200, restored.text
    assert restored.json()["authenticated"] is True
    assert restored.json()["gemini_configured"] is True
    assert runtime.SESSIONS[sid]["expires_at"] == expires
    assert runtime.SESSIONS[sid]["file_namespace"] == namespace
    assert runtime.SESSIONS[sid]["creds"] == credentials
    assert not any(secret in restored.text for secret in ("test-google-token", "test-refresh-token", sid))
    flow.fetch_token.assert_called_once_with(code="test-code")
    client.cookies.set("oauth_state", state)
    assert client.get("/auth/callback", params={"state": state, "code": "test-code"}, follow_redirects=False).status_code == 500
    flow.fetch_token.assert_called_once_with(code="test-code")
    runtime._eliminar_sesion(sid)


def test_logout_revokes_persistent_and_cached_sessions(setup):
    client, value, _ = setup
    sid = value["session_id"]
    assert client.get("/api/session").json()["authenticated"] is True
    stale_replica = dict(studio.runtime.SESSIONS[sid])
    assert record(sid)
    response = client.post("/logout", headers=ORIGIN, follow_redirects=False)
    assert response.status_code == 303
    assert record(sid) is None
    # Even another process with a cached copy must observe the revocation.
    studio.runtime.SESSIONS[sid] = stale_replica
    client.cookies.set("session_id", sid)
    assert client.get("/api/session").json()["authenticated"] is False
    assert sid not in studio.runtime.SESSIONS


def test_expired_or_tampered_cookie_does_not_restore_session(setup):
    client, value, _ = setup
    sid = value["session_id"]
    web_sessions.save(sid, value)
    with transaction() as db:
        saved = db.scalar(select(IntegrationAccount).where(IntegrationAccount.tenant_id == web_sessions._tenant(sid)))
        data = unseal(saved.encrypted_credentials)
        data["expires_at"] = time.time() - 1
        saved.encrypted_credentials = seal(data)
    studio.runtime.SESSIONS.pop(sid)
    assert client.get("/api/session").json()["authenticated"] is False
    client.cookies.set("session_id", secrets.token_urlsafe(24))
    assert client.get("/api/session").json()["authenticated"] is False
    client.cookies.set("session_id", "invalid-cookie")
    assert client.get("/api/session").json()["authenticated"] is False


def test_changed_allowlist_invalidates_existing_session(setup, monkeypatch):
    client, value, _ = setup
    web_sessions.save(value["session_id"], value)
    monkeypatch.setenv("APP_ALLOWED_EMAILS", "someone-else@example.test")
    assert client.get("/api/session").json()["authenticated"] is False


def test_recovery_uses_current_folder_and_personal_key(setup):
    client, value, _ = setup
    sid = value["session_id"]
    web_sessions.save(sid, value)
    from catalog_platform.accounts import save_gemini
    with transaction() as db:
        save_gemini(db, "another-test-folder", value["email"], "new-personal-test-key", "Nueva tienda")
    studio.runtime.SESSIONS.pop(sid)
    restored = client.get("/api/session")
    assert restored.status_code == 200, restored.text
    assert restored.json()["folder_id"] == "another-test-folder"
    assert restored.json()["folder"] == "Nueva tienda"
    assert studio.runtime.SESSIONS[sid]["gemini_key"] == "new-personal-test-key"
    assert "new-personal-test-key" not in restored.text


def test_transient_restore_error_is_503_without_logging_out(setup, monkeypatch):
    client, value, _ = setup
    web_sessions.save(value["session_id"], value)
    studio.runtime.SESSIONS.pop(value["session_id"])
    original = web_sessions.transaction
    monkeypatch.setattr(web_sessions, "transaction", Mock(side_effect=RuntimeError("private-db-password")))
    unavailable = client.get("/api/session")
    assert unavailable.status_code == 503
    assert unavailable.headers["cache-control"] == "no-store"
    assert "private-db-password" not in unavailable.text
    assert not unavailable.headers.get("set-cookie")
    # Readiness must be independent of session storage during a DB outage.
    assert client.get("/service-health").json()["ok"] is True
    monkeypatch.setattr(web_sessions, "transaction", original)
    assert client.get("/api/session").json()["authenticated"] is True


def test_restoration_precedes_upload_security_and_keeps_csrf(setup):
    client, value, _ = setup
    from test_studio_api import upload
    web_sessions.save(value["session_id"], value)
    studio.runtime.SESSIONS.pop(value["session_id"])
    assert upload(client)
    studio.runtime.SESSIONS.pop(value["session_id"])
    forbidden = client.post("/api/uploads", headers={"Origin": "https://untrusted.example"})
    assert forbidden.status_code == 403
    assert value["session_id"] not in studio.runtime.SESSIONS
