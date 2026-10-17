"""Multiple authorized Google accounts, durable sessions and worker permissions."""
import json
import secrets
import time

import pytest
from access_policy import catalog_member, login_allowed, role_for, status
from test_catalog_platform import setup, create, reference, enqueue, fake_provider, ORIGIN
from catalog_platform import accounts, worker, web_sessions
from catalog_platform.database import transaction
import studio_api as studio


@pytest.mark.parametrize('allowed', [
    ' owner@example.test, STAFF@example.test ',
    'owner@example.test;staff@example.test',
    'owner@example.test\nstaff@example.test',
    '["owner@example.test", "staff@example.test"]',
])
def test_explicitly_allowed_users_are_members_without_duplicating_roles(monkeypatch, allowed):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://test-unused')
    monkeypatch.setenv('APP_REQUIRE_ALLOWLIST', 'true')
    monkeypatch.setenv('APP_ALLOWED_EMAILS', allowed)
    monkeypatch.setenv('APP_ROLE_MAP', '{" owner@EXAMPLE.test ":" Admin "}')
    monkeypatch.setenv('APP_DEFAULT_ROLE', 'viewer')
    assert login_allowed(' STAFF@example.test ') and catalog_member('staff@example.test')
    assert role_for('staff@example.test') == 'viewer'
    assert role_for('OWNER@example.test') == 'admin'
    assert not catalog_member('stranger@example.test')
    assert not catalog_member('')
    report = status()
    assert report['members'] == 2 and report['allowed_without_role'] == 1
    assert '@' not in json.dumps(report)


def test_allowlist_revocation_and_invalid_role_remain_closed(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://test-unused')
    monkeypatch.setenv('APP_ALLOWED_EMAILS', 'staff@example.test')
    monkeypatch.setenv('APP_ROLE_MAP', '{"owner@example.test":"admin","staff@example.test":"bad-role"}')
    monkeypatch.setenv('APP_DEFAULT_ROLE', 'editor')
    assert not catalog_member('owner@example.test')
    assert not catalog_member('staff@example.test')
    monkeypatch.setenv('APP_ALLOWED_EMAILS', '')
    monkeypatch.setenv('APP_REQUIRE_ALLOWLIST', 'true')
    assert catalog_member('owner@example.test')
    assert not login_allowed('staff@example.test')


def test_two_additional_accounts_can_use_catalog_worker_and_recover_sessions(setup, monkeypatch):
    client, owner, _ = setup
    emails = ['staff-one@example.test', 'staff-two@example.test']
    monkeypatch.setenv('APP_ALLOWED_EMAILS', '\n'.join([owner['email'], *emails]))
    monkeypatch.setenv('APP_ROLE_MAP', json.dumps({owner['email']:'admin'}))
    monkeypatch.setenv('APP_DEFAULT_ROLE', 'editor')
    maker, _ = fake_provider(monkeypatch)
    sessions = []
    try:
        for index, email in enumerate(emails):
            sid = secrets.token_urlsafe(24)
            sessions.append(sid)
            value = {'session_id':sid, 'email':email, 'expires_at':time.time()+600,
                'creds':{'token':'test-token-'+str(index),'refresh_token':'test-refresh-'+str(index)},
                'file_namespace':secrets.token_urlsafe(24),'platform_tenant':owner['platform_tenant'],
                'carpeta_raiz_id_manual':owner['platform_tenant']}
            studio.runtime.SESSIONS[sid] = value
            with transaction() as db:
                accounts.save_profile(db, owner['platform_tenant'], email)
            client.cookies.clear()
            client.cookies.set('session_id',sid)
            session = client.get('/api/session')
            assert session.status_code == 200 and session.json()['gemini_configured'], session.text
            assert client.get('/api/platform/products').status_code == 200
            product = create(client, sku='STAFF'+str(index))
            reference(client, product)
            job, _ = enqueue(client, value, product, slots=['1_hd'])
            worker.execute_job(job['id'])
            response = client.get('/api/platform/jobs')
            assert response.status_code == 200, response.text
            result = next(item for item in response.json()['items'] if item['id'] == job['id'])
            assert result['status'] == 'completed', result
            studio.runtime.SESSIONS.pop(sid)
            restored = client.get('/api/session')
            assert restored.status_code == 200 and restored.json()['email'] == email, restored.text
            assert restored.json()['gemini_configured']
            assert studio.runtime.SESSIONS[sid]['creds']['token'] == 'test-token-'+str(index)
        assert maker.call_count == 2
    finally:
        for sid in sessions:
            studio.runtime._eliminar_sesion(sid)


def test_allowlisted_viewer_can_read_but_cannot_gain_edit_or_admin_rights(setup, monkeypatch):
    client, value, _ = setup
    email = 'read-only@example.test'
    monkeypatch.setenv('APP_ALLOWED_EMAILS', value['email']+','+email)
    monkeypatch.setenv('APP_DEFAULT_ROLE', 'viewer')
    value['email'] = email
    assert client.get('/api/platform/products').status_code == 200
    assert client.post('/api/platform/products', json={'sku':'DENIED','name':'Denied'},headers=ORIGIN).status_code == 403
    assert client.post('/api/settings',json={'folder':'another-folder'},headers=ORIGIN).status_code == 403
