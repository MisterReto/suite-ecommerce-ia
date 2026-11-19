"""Regresiones del consentimiento OAuth sin acceso real a Google."""
import json
import secrets
import time

import pytest
from cryptography.fernet import Fernet

import oauth_guard


@pytest.fixture
def ticket_key(monkeypatch):
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())


def _forget_process_state(state):
    # Simula pérdida de RAM cuando Render reinicia el proceso API.
    with oauth_guard._lock:
        oauth_guard._pending.pop(state, None)


def test_pkce_recovered_from_encrypted_cookie_after_api_restart(ticket_key):
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    ticket = oauth_guard.issue_oauth(state, verifier)
    assert verifier not in ticket
    _forget_process_state(state)
    assert oauth_guard.consume_oauth(state, state, ticket) == verifier


def test_tampered_or_mismatched_oauth_ticket_rejected(ticket_key):
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    ticket = oauth_guard.issue_oauth(state, verifier)
    _forget_process_state(state)
    with pytest.raises(ValueError):
        oauth_guard.consume_oauth(state, secrets.token_urlsafe(32), ticket)
    with pytest.raises(ValueError):
        oauth_guard.consume_oauth(state, state, ticket[:-1] + ("A" if ticket[-1] != "A" else "B"))


def test_expired_oauth_ticket_rejected(ticket_key):
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    from catalog_platform.security import cipher
    expired = cipher().encrypt_at_time(
        json.dumps({"state": state, "verifier": verifier}).encode(),
        int(time.time()) - 701,
    ).decode()
    _forget_process_state(state)
    with pytest.raises(ValueError):
        oauth_guard.consume_oauth(state, state, expired)


def test_normal_oauth_state_still_consumed_once(ticket_key):
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    oauth_guard.issue_oauth(state, verifier)
    assert oauth_guard.consume_oauth(state, state) == verifier
    with pytest.raises(ValueError):
        oauth_guard.consume_oauth(state, state)
