"""Integration tests for signed delegation; no Google or store API calls."""
import asyncio
import json
import os
import secrets
import sys
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ['SUITE_SERVICE_ROLE'] = 'sync'
os.environ['SUITE_DRIVE_ONLY'] = 'false'
os.environ['SYNC_SERVICE_SHARED_KEY'] = 'integration-test-shared-key-32-characters'

import httpx
from fastapi import Request
import sync_gateway
import sync_service
from sync_bridge_protocol import signature, setting

KEY = os.environ['SYNC_SERVICE_SHARED_KEY']
CONTEXT = {
    'access_token': 'temporary-test-token', 'root_folder_id': 'root-test',
    'images_folder_id': 'images-test', 'spreadsheet_id': 'sheet-test',
    'store': {'WC_URL': 'https://store.example', 'WC_WRITE_ENABLED': 'true',
              'WC_CONSUMER_KEY': 'test-key', 'WC_CONSUMER_SECRET': 'test-secret'},
}

def signed(path='/woocommerce-product-sync', method='GET', payload='', timestamp=None):
    body = json.dumps({'method': method, 'path': path, 'query': '', 'body': payload, 'context': CONTEXT}).encode()
    ts, nonce = str(timestamp or int(time.time())), secrets.token_urlsafe(24)
    headers = {'x-suite-time': ts, 'x-suite-nonce': nonce, 'x-suite-signature': signature(body, ts, nonce, KEY)}
    return body, headers

class SplitServicesTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=sync_service.app), base_url='http://worker')

    async def asyncTearDown(self):
        await self.client.aclose()
        self.assertFalse(sync_service.runtime.SESSIONS)

    async def test_worker_reuses_page_without_ai_runtime(self):
        body, headers = signed()
        response = await self.client.post('/internal/tools', content=body, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Sincronizar producto completo', response.text)
        self.assertIn('Escritura habilitada', response.text)
        self.assertNotIn(CONTEXT['access_token'], response.text)
        self.assertNotIn('test-secret', response.text)
        self.assertTrue(all(name not in sys.modules for name in ('gradio', 'ai_app', 'pandas', 'google.genai')))

    async def test_reject_unsigned_tampered_expired_replayed_and_unknown_route(self):
        self.assertEqual((await self.client.post('/internal/tools', json={})).status_code, 401)
        body, headers = signed()
        self.assertEqual((await self.client.post('/internal/tools', content=body + b' ', headers=headers)).status_code, 401)
        self.assertEqual((await self.client.post('/internal/tools', content=body, headers=headers)).status_code, 200)
        self.assertEqual((await self.client.post('/internal/tools', content=body, headers=headers)).status_code, 409)
        body, headers = signed(timestamp=int(time.time())-121)
        self.assertEqual((await self.client.post('/internal/tools', content=body, headers=headers)).status_code, 401)
        body, headers = signed('/login')
        self.assertEqual((await self.client.post('/internal/tools', content=body, headers=headers)).status_code, 400)

    async def test_post_uses_request_scoped_google_and_store_context(self):
        def fake_sync(session, sku, include_images):
            self.assertEqual(session['access_token'], CONTEXT['access_token'])
            self.assertEqual(session['spreadsheet_id'], 'sheet-test')
            self.assertEqual(setting('WC_CONSUMER_SECRET'), 'test-secret')
            return {'sku': sku, 'backend_verified': True, 'executor': 'second-service'}
        body, headers = signed('/product-sync-one', 'POST', json.dumps({'sku': 'PANKO', 'include_images': False}))
        with patch('product_web._full_sync', fake_sync):
            response = await self.client.post('/internal/tools', content=body, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['result']['executor'], 'second-service')
        self.assertEqual(setting('WC_CONSUMER_SECRET'), os.getenv('WC_CONSUMER_SECRET', ''))

    async def test_gateway_delegates_and_does_not_expose_oauth_or_gemini_secrets(self):
        original_client = httpx.AsyncClient
        async def remote(request):
            envelope = json.loads(request.content)
            self.assertNotIn('refresh_token', envelope['context'])
            self.assertNotIn('api_key', envelope['context'])
            async with original_client(transport=httpx.ASGITransport(app=sync_service.app), base_url='http://worker') as client:
                return await client.post('/internal/tools', content=request.content, headers=request.headers)
        def client_factory(*args, **kwargs):
            if 'transport' not in kwargs:
                kwargs['transport'] = httpx.MockTransport(remote)
            return original_client(*args, **kwargs)
        session = {'creds': {'token': 'temporary-test-token', 'refresh_token': 'never-transfer', 'client_secret': 'never-transfer'}, 'api_key': 'never-transfer'}
        legacy = SimpleNamespace(SESSIONS={'ui-session': session},
            _get_drive_service=lambda s: None, _preparar_estructura=lambda d,s: ('root-test', 'images-test', 'sheet-test', None))
        scope = {'type': 'http', 'method': 'GET', 'path': '/woocommerce-product-sync', 'scheme': 'https',
                 'server': ('main.example',443), 'query_string': b'', 'headers': [(b'cookie',b'session_id=ui-session')]}
        async def receive(): return {'type':'http.request','body':b'','more_body':False}
        request = Request(scope, receive)
        with patch.dict(os.environ, {'SYNC_SERVICE_URL':'https://worker.example', 'WC_WRITE_ENABLED':'true'}), patch('httpx.AsyncClient', client_factory):
            response = await sync_gateway.forward_tool(request, legacy)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['x-suite-executor'], 'sync-service')

if __name__ == '__main__':
    unittest.main()
