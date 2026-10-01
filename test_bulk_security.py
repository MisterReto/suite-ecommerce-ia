"""Concurrency and security regressions; no external requests or store writes."""
import ast
import asyncio
import copy
import json
import io
import os
import secrets
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch, Mock

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from app_security import SecurityMiddleware, WindowLimiter, clean_html, validate_service_url, checked_image_type
from PIL import Image
from bulk_product_upload import ensure_entity, next_wave, plan_skus, publish_created, run_wave
from inventory_operations import inventory_summary, register_movement, stock_integer
from inventory_bulk import register_initial_counts
from inventory_schema import normalize_product_row
from sync_bridge_protocol import STORE_CONTEXT
from woocommerce_product_sync import sync_complete_product

PARENT = {"sku": "PANKOFULL", "tipo": "variable", "nombre_producto": "Panko", "sku_padre": ""}
CHILD = {"sku": "PANK500", "tipo": "variation", "sku_padre": "PANKOFULL", "atributo_nombre": "Presentación", "atributo_valor": "500 g"}


class FakeWC:
    def __init__(self):
        self.rows, self.calls = {}, []
        self.config = NS(write_enabled=True, base_url="https://store.example")
    def request(self, method, endpoint, *, params=None, payload=None):
        self.calls.append((method, endpoint, copy.deepcopy(payload)))
        if method == "GET":
            return [copy.deepcopy(self.rows[params["sku"]])] if params["sku"] in self.rows else []
        item = dict(copy.deepcopy(payload), id=len(self.rows) + 1)
        self.rows[item["sku"]] = item
        return copy.deepcopy(item)
    def find_product_by_sku(self, sku):
        return copy.deepcopy(self.rows.get(sku))
    def list_all_variations(self, parent):
        return [copy.deepcopy(r) for r in self.rows.values() if "type" not in r]
    def update_product(self, product_id, payload):
        self.calls.append(("PUT", f"products/{product_id}", copy.deepcopy(payload)))
        row = next(r for r in self.rows.values() if r["id"] == product_id)
        row.update(payload)
        return copy.deepcopy(row)
    def update_variation(self, parent, product_id, payload):
        return self.update_product(product_id, payload)
    def get_product(self, product_id):
        return copy.deepcopy(next(r for r in self.rows.values() if r["id"] == product_id))
    def get_variation(self, parent, product_id):
        return self.get_product(product_id)


class UploadTests(unittest.TestCase):
    def test_threads_overlap_are_bounded_and_keep_tenant_context(self):
        barrier, lock = threading.Barrier(2), threading.Lock()
        active, maximum = 0, 0
        context = STORE_CONTEXT.set({"WC_CONSUMER_KEY": "tenant-one"})
        def job(item):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            barrier.wait(timeout=2)
            value = STORE_CONTEXT.get()["WC_CONSUMER_KEY"]
            STORE_CONTEXT.set({"WC_CONSUMER_KEY": "changed-in-thread"})
            with lock:
                active -= 1
            return value
        try:
            with patch.dict(os.environ, {"BULK_MAX_WORKERS": "2"}):
                self.assertEqual(run_wave(range(4), job, 20), ["tenant-one"] * 4)
            self.assertEqual(maximum, 2)
            self.assertEqual(STORE_CONTEXT.get()["WC_CONSUMER_KEY"], "tenant-one")
        finally:
            STORE_CONTEXT.reset(context)

    def test_parent_dependency_and_siblings_are_serial(self):
        child2 = dict(CHILD, sku="PANK1000", atributo_valor="1 kg")
        rows = [PARENT, CHILD, child2, {"sku": "SOY", "tipo": "simple"}]
        skus = plan_skus(rows, [CHILD["sku"], child2["sku"], "SOY"])
        index = {r["sku"]: r for r in rows}
        items = [{"sku": sku, "status": "pending"} for sku in skus]
        self.assertEqual([i["sku"] for i in next_wave(items, index, 2)], [PARENT["sku"]])
        items[0]["status"] = "success"
        wave = next_wave(items, index, 2)
        self.assertEqual(len(wave), 2)
        self.assertEqual(sum(i["sku"].startswith("PANK") for i in wave), 1)
        with self.assertRaises(ValueError):
            plan_skus([CHILD], [CHILD["sku"]])

    def test_creation_retry_finds_existing_and_publishes_owned_draft(self):
        wc = FakeWC()
        row = dict(PARENT, Existencias="", precio="")
        entity, created = ensure_entity(wc, row, [row, CHILD])
        self.assertTrue(created)
        self.assertFalse(entity["manage_stock"])
        self.assertNotIn("regular_price", entity)
        self.assertNotIn("stock_quantity", entity)
        self.assertEqual(entity["status"], "draft")
        resumed, created = ensure_entity(wc, row, [row, CHILD])
        self.assertFalse(created)
        publish_created(wc, resumed, created)
        self.assertEqual(wc.rows[row["sku"]]["status"], "publish")
        self.assertEqual(sum(c[0] == "POST" for c in wc.calls), 1)
        publish_created(wc, {"id": 999, "status": "draft"}, False)

    def test_variation_uses_global_attribute_id_and_correct_parent(self):
        wc = FakeWC()
        wc.rows[PARENT["sku"]] = {"sku": PARENT["sku"], "id": 55, "type": "variable",
            "attributes": [{"id": 7, "name": "Presentación", "options": ["500 g"]}]}
        entity, _ = ensure_entity(wc, CHILD, [PARENT, CHILD])
        self.assertEqual(wc.calls[-1][1], "products/55/variations")
        self.assertEqual(entity["attributes"], [{"id": 7, "option": "500 g"}])
        ensure_entity(wc, CHILD, [PARENT, CHILD])
        self.assertEqual(sum(c[0] == "POST" for c in wc.calls), 1)

    def test_sync_without_stock_preserves_remote_stock_and_sanitizes_text(self):
        wc = FakeWC()
        wc.rows["SOY"] = {"id": 1, "sku": "SOY", "type": "simple", "stock_quantity": 17,
            "manage_stock": True, "stock_status": "instock"}
        row = normalize_product_row({"sku": "SOY", "tipo": "simple", "nombre_producto": "Soya",
            "precio": 50, "Existencias": 0, "descripcion_larga": '<p onclick="steal()">Soya</p><img src=x onerror=steal()>'})
        tax = {"category_ids": [], "tag_ids": [], "brand_ids": [], "warnings": []}
        with patch("woocommerce_product_sync.resolve_taxonomies", return_value=tax):
            result = sync_complete_product(row=row, wc_client=wc, wc_entity=dict(wc.rows["SOY"], _entity_type="product"), include_stock=False)
        self.assertTrue(result["backend_verified"])
        self.assertEqual(wc.rows["SOY"]["stock_quantity"], 17)
        self.assertNotIn("onclick", wc.rows["SOY"]["description"])
        self.assertNotIn("stock_status", wc.calls[0][2])

    def test_parent_counts_and_movements_rejected_before_writes(self):
        row = normalize_product_row(PARENT)
        with patch("inventory_operations.read_inventory", return_value=[row]), patch("inventory_operations._sheet_map") as write:
            with self.assertRaisesRegex(ValueError, "FULL"):
                register_movement(None, "test", sku=PARENT["sku"], movement_type="Entrada", quantity=1)
            write.assert_not_called()
        with patch("inventory_bulk.read_inventory", return_value=[row]), patch("inventory_bulk._sheet_map") as write:
            with self.assertRaisesRegex(ValueError, "FULL"):
                register_initial_counts(None, "test", [{"sku": PARENT["sku"], "stock": 1}])
            write.assert_not_called()
        self.assertEqual(inventory_summary([row])["products"], 0)

    def test_fractional_nonfinite_and_excessive_counts_rejected(self):
        for value in [True, -1, "1.5", "NaN", "Infinity", "1e40", None]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                stock_integer(value)
        self.assertEqual(stock_integer("12.0"), 12)


class SecurityTests(unittest.IsolatedAsyncioTestCase):
    def build_app(self, sessions=None):
        app = FastAPI()
        @app.api_route("/probe", methods=["GET", "POST"])
        async def probe(request: Request):
            return {"size": len(await request.body())}
        @app.post("/gradio_api/upload")
        async def upload():
            return {"ok": True}
        app.add_middleware(SecurityMiddleware, sessions=lambda: sessions or {})
        return app

    async def test_cross_site_missing_origin_and_forged_host_blocked(self):
        with patch.dict(os.environ, {"RENDER_EXTERNAL_URL": "https://suite.example"}):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.build_app()), base_url="https://suite.example") as c:
                self.assertEqual((await c.post("/probe")).status_code, 403)
                self.assertEqual((await c.post("/probe", headers={"origin": "https://suite.example.attacker.test"})).status_code, 403)
                self.assertEqual((await c.get("/probe", headers={"host": "attacker.test"})).status_code, 400)
                r = await c.post("/probe", headers={"origin": "https://suite.example"}, content="ok")
                self.assertEqual(r.status_code, 200)
                self.assertIn("frame-ancestors 'self'", r.headers["content-security-policy"])
                self.assertEqual(r.headers["x-content-type-options"], "nosniff")
                self.assertIn("camera=(self)", r.headers["permissions-policy"])

    async def test_chunked_body_limit_and_unauthenticated_upload(self):
        async def chunks():
            yield b"x" * 300_000
            yield b"x" * 300_000
        with patch.dict(os.environ, {"RENDER_EXTERNAL_URL": "https://suite.example"}):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.build_app()), base_url="https://suite.example", headers={"origin": "https://suite.example"}) as c:
                self.assertEqual((await c.post("/probe", content=chunks())).status_code, 413)
                self.assertEqual((await c.post("/gradio_api/upload", content=b"image")).status_code, 401)

    async def test_session_cache_disabled(self):
        with patch.dict(os.environ, {"RENDER_EXTERNAL_URL": "https://suite.example"}):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.build_app({"sid": {"email": "test"}})), base_url="https://suite.example", cookies={"session_id": "sid"}) as c:
                self.assertEqual((await c.get("/probe")).headers["cache-control"], "no-store")

    def test_rate_limiter_bounded_and_html_urls_safe(self):
        limiter = WindowLimiter(maximum=2)
        self.assertTrue(limiter.allow("a", 1))
        self.assertFalse(limiter.allow("a", 1))
        limiter.allow("b", 1)
        limiter.allow("c", 1)
        self.assertEqual(len(limiter.entries), 2)
        for url in ["http://store.test", "https://127.0.0.1", "https://10.1.1.1", "https://localhost", "https://secret@store.test", "https://store.test?token=x"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_service_url(url)
        self.assertEqual(validate_service_url("https://store.example/shop"), "https://store.example/shop")
        safe = clean_html('<svg onload=steal()></svg><a href="javascript:steal()">link</a><b>ok</b>')
        self.assertNotIn("javascript", safe)
        self.assertNotIn("onload", safe)
        self.assertIn("<b>ok</b>", safe)

    def test_oauth_state_rejected_before_token_exchange(self):
        tree = ast.parse(Path("app.py").read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "auth_callback")
        fn.decorator_list = []
        flow = Mock()
        scope = {"secrets": secrets, "FastAPIRequest": Request, "PlainTextResponse": PlainTextResponse, "Flow": flow}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "oauth-test", "exec"), scope)
        for cookie, state in [("expected", "wrong"), ("", "expected")]:
            result = scope["auth_callback"](NS(query_params={"state": state, "code": "unused"}, cookies={"oauth_state": cookie}))
            self.assertEqual(result.status_code, 400)
        flow.from_client_config.assert_not_called()

    def test_image_content_and_header_injection_rejected(self):
        buffer = io.BytesIO()
        Image.new("RGB", (2, 2), "red").save(buffer, "PNG")
        self.assertEqual(checked_image_type("product.png", buffer.getvalue()), "image/png")
        for filename, data in [("x.php", buffer.getvalue()), ("x.svg", b"<svg onload='steal()'/>"),
            ('x.png\r\nInjected: header', buffer.getvalue()), ("fake.jpg", b"executable"), ("large.png", b"x" * 12_000_001)]:
            with self.subTest(filename=filename), self.assertRaises(ValueError):
                checked_image_type(filename, data)

    def test_drive_download_stops_when_size_limit_crossed(self):
        from woocommerce_image_sync import _download_drive_file
        class Download:
            def __init__(self, buffer, request, chunksize):
                self.buffer = buffer
            def next_chunk(self):
                self.buffer.write(b"x" * 1_000_000)
                return None, False
        with patch("woocommerce_image_sync.MediaIoBaseDownload", Download):
            with self.assertRaisesRegex(ValueError, "12 MB"):
                _download_drive_file(Mock(), "fake-file")


class ToolIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Lightweight worker runtime; no Gradio, Google or WordPress startup.
        import sync_service
        import batch_web_v2
        cls.batch = batch_web_v2

    def test_batch_joins_two_threads_with_separate_clients(self):
        batch = self.batch
        rows = [{"sku": s, "tipo": "simple", "Existencias": 3} for s in ("A", "B")]
        items = [{"sku": r["sku"], "status": "pending", "_sheet_row": i + 2,
            "include_images": "FALSE", "include_stock": "FALSE", "workers": 2} for i, r in enumerate(rows)]
        barrier, clients, values = threading.Barrier(2), [], []
        def client_factory():
            client = Mock(config=NS(write_enabled=True))
            clients.append(client)
            return client
        def sync(**kwargs):
            barrier.wait(timeout=2)
            values.append(STORE_CONTEXT.get()["WC_CONSUMER_KEY"])
            self.assertFalse(kwargs["include_stock"])
            return {"backend_verified": True}
        token = STORE_CONTEXT.set({"WC_CONSUMER_KEY": "integration-tenant"})
        try:
            with patch.object(batch.media_web, "_direct_inventory_context", return_value=("test", rows, Mock())), \
                patch.object(batch, "read_batch", return_value=items), \
                patch.object(batch.legacy_app, "_get_sheets_service", side_effect=lambda s: Mock()), \
                patch.object(batch, "WooCommerceClient", side_effect=client_factory), \
                patch.object(batch, "ensure_entity", return_value=({"id": 1}, False)), \
                patch.object(batch, "sync_complete_product", side_effect=sync), \
                patch.object(batch, "update_batch_item") as writes:
                result = batch._process_one({}, "test-batch")
            self.assertEqual(len(result["results"]), 2)
            self.assertTrue(all(r["status"] == "success" for r in result["results"]))
            self.assertIsNot(clients[0], clients[1])
            self.assertEqual(values, ["integration-tenant"] * 2)
            self.assertEqual(sum(c.kwargs["status"] == "success" for c in writes.call_args_list), 2)
        finally:
            STORE_CONTEXT.reset(token)

    def test_failed_parent_blocks_child_without_store_write(self):
        batch = self.batch
        items = [{"sku": PARENT["sku"], "status": "error", "_sheet_row": 2, "include_images": False},
            {"sku": CHILD["sku"], "status": "pending", "_sheet_row": 3}]
        with patch.object(batch.media_web, "_direct_inventory_context", return_value=("test", [PARENT, CHILD], Mock())), \
            patch.object(batch, "read_batch", return_value=items), \
            patch.object(batch.legacy_app, "_get_sheets_service", return_value=Mock()), \
            patch.object(batch, "WooCommerceClient"), \
            patch.object(batch, "ensure_entity") as create, \
            patch.object(batch, "update_batch_item"):
            result = batch._process_one({}, "test-batch")
        self.assertEqual(result["results"][0]["status"], "error")
        create.assert_not_called()

    def test_hub_loads_inventory_only_and_boolean_options_are_strict(self):
        from inventory_hub import inventory_hub
        with patch("inventory_hub.inventory_web._session", return_value={"email": "test"}):
            body = inventory_hub(Mock()).body.decode()
        self.assertEqual(body.count("<iframe"), 1)
        self.assertIn('src="/inventory-manager"', body)
        self.assertNotIn('src="/woocommerce-publish-preview"', body)
        self.assertIn('data-page="/inventory-count"', body)
        with self.assertRaises(ValueError):
            self.batch._option_bool({"include_stock": "false"}, "include_stock", False)


if __name__ == "__main__":
    unittest.main()
