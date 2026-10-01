"""Parent cover and direct service handoff regressions; no live API calls."""
import json
import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from fastapi import FastAPI, Request
from inventory_schema import normalize_product_row, is_variable_parent
from woocommerce_inventory import compare_product
import sync_gateway
import sync_service


class ParentTests(unittest.TestCase):
    def test_full_parent_has_no_commercial_stock_and_price(self):
        row = normalize_product_row({"sku": "PANKFULL", "tipo": "variable", "sku_padre": "PANKFULL",
            "precio": 99, "Precio descuento": 80, "Existencias": 20, "nombre_producto": "Panko"})
        self.assertTrue(is_variable_parent(row))
        self.assertEqual(row["tipo"], "variable")
        self.assertEqual(row["sku_padre"], "")
        self.assertEqual([row[k] for k in ("precio", "Precio descuento", "Existencias")], ["", "", ""])
        preview = compare_product(row, {"id": 1, "type": "variable", "name": "Panko", "price": "110",
            "manage_stock": False, "stock_quantity": None})
        self.assertEqual(preview.status, "variable_parent")
        self.assertEqual(preview.changes, ())
        self.assertIsNone(preview.inventory_price)
        self.assertIsNone(preview.inventory_stock)

    def test_variation_keeps_own_stock_and_price(self):
        row = normalize_product_row({"sku": "PANK500", "tipo": "variation", "sku_padre": "PANKFULL",
            "precio": 85, "Existencias": 4})
        self.assertFalse(is_variable_parent(row))
        self.assertEqual(row["precio"], 85)
        self.assertEqual(row["Existencias"], 4)


class DirectServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_health_precedes_worker_catchall(self):
        with patch.dict(os.environ, {"SUITE_SERVICE_ROLE": "sync"}):
            import service_entrypoint
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=service_entrypoint.fastapi_app), base_url="https://worker.example") as client:
                response = await client.get('/service-health')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['role'], 'sync')

    async def test_direct_worker_session_and_write_context(self):
        key = "direct-service-test-key-32-characters"
        main = FastAPI()
        legacy = SimpleNamespace(SESSIONS={"main-cookie": {"creds": {"token": "temporary-token"}}})
        sync_gateway.install_handoff_routes(main, legacy)
        context = {"access_token": "temporary-token", "spreadsheet_id": "sheet-test",
            "root_folder_id": "root-test", "images_folder_id": "images-test",
            "store": {"WC_WRITE_ENABLED": "true", "WC_CONSUMER_SECRET": "private-store-key"}}
        original_client = httpx.AsyncClient
        async def redeem(request):
            async with original_client(transport=httpx.ASGITransport(app=main), base_url="https://main.example") as client:
                return await client.post('/sync-handoff/redeem', content=request.content, headers=request.headers)
        def factory(*a, **kw):
            kw.setdefault('transport', httpx.MockTransport(redeem))
            return original_client(*a, **kw)
        with patch.dict(os.environ, {"SYNC_SERVICE_URL": "https://worker.example", "MAIN_SERVICE_URL": "https://main.example",
            "SYNC_SERVICE_SHARED_KEY": key}), patch('sync_gateway._worker_context', return_value=context):
            async with original_client(transport=httpx.ASGITransport(app=main), base_url="https://main.example") as client:
                client.cookies.set("session_id", "main-cookie")
                response = await client.get('/sync-launch?path=/woocommerce-product-sync')
                self.assertEqual(response.status_code, 303)
                ticket_url = response.headers['location']
                self.assertNotIn('temporary-token', ticket_url)
            async with original_client(transport=httpx.ASGITransport(app=sync_service.app), base_url="https://worker.example") as client:
                with patch('httpx.AsyncClient', factory):
                    response = await client.get(ticket_url)
                self.assertEqual(response.status_code, 303)
                self.assertIn('HttpOnly', response.headers['set-cookie'])
                page = await client.get(response.headers['location'])
                self.assertEqual(page.status_code, 200)
                self.assertEqual(page.headers['x-suite-executor'], 'sync-service')
                self.assertIn('Suite e-commerce', page.text)
                self.assertIn('segundo servicio', page.text)
                self.assertNotIn('private-store-key', page.text)
                def fake_sync(session, sku, include_images):
                    from sync_bridge_protocol import setting
                    self.assertEqual(setting('WC_CONSUMER_SECRET'), 'private-store-key')
                    self.assertEqual(session['access_token'], 'temporary-token')
                    return {"backend_verified": True}
                with patch('product_web._full_sync', fake_sync):
                    result = await client.post('/product-sync-one', json={"sku": "PANK500", "include_images": False},
                        headers={"origin": "https://worker.example"})
                    self.assertEqual(result.status_code, 200)
                    self.assertEqual((await client.post('/product-sync-one', json={})).status_code, 403)
                sid = client.cookies.get('sync_session')
                sync_service.runtime.SESSIONS.pop(sid, None)
                with patch('httpx.AsyncClient', factory):
                    replay = await client.get(ticket_url)
                self.assertEqual(replay.status_code, 401)

    async def test_main_tool_posts_are_disabled_and_gets_redirect(self):
        with patch.dict(os.environ, {"SYNC_SERVICE_URL": "https://worker.example"}):
            for method in ('GET', 'POST'):
                request = Request({"type": "http", "method": method, "path": "/woocommerce-product-sync",
                    "scheme": "https", "server": ("main.example", 443), "query_string": b'', "headers": []})
                response = sync_gateway.redirect_tool(request)
                self.assertEqual(response.status_code, 307 if method == 'GET' else 409)


if __name__ == '__main__':
    unittest.main()
