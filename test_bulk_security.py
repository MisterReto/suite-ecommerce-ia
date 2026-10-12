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
from inventory_operations import inventory_summary, register_movement, stock_integer
from inventory_bulk import register_initial_counts
from inventory_schema import normalize_product_row

PARENT = {"sku": "PANKOFULL", "tipo": "variable", "nombre_producto": "Panko", "sku_padre": ""}
CHILD = {"sku": "PANK500", "tipo": "variation", "sku_padre": "PANKOFULL", "atributo_nombre": "Presentación", "atributo_valor": "500 g"}




class UploadTests(unittest.TestCase):





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
        @app.post("/api/uploads")
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
                self.assertEqual((await c.post("/api/uploads", content=b"image")).status_code, 401)

    async def test_session_cache_disabled(self):
        with patch.dict(os.environ, {"RENDER_EXTERNAL_URL": "https://suite.example"}):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.build_app({"sid": {"email": "test"}})), base_url="https://suite.example", cookies={"session_id": "sid"}) as c:
                self.assertEqual((await c.get("/probe")).headers["cache-control"], "no-store")

    async def test_no_eval_in_main_or_worker_documents(self):
        with patch.dict(os.environ, {"RENDER_EXTERNAL_URL": "https://suite.example", "SUITE_SERVICE_ROLE": "main"}):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.build_app()), base_url="https://suite.example") as c:
                self.assertNotIn("'unsafe-eval'", (await c.get("/")).headers["content-security-policy"])
                self.assertNotIn("'unsafe-eval'", (await c.get("/probe")).headers["content-security-policy"])
                with patch.dict(os.environ, {"SUITE_SERVICE_ROLE": "sync"}):
                    self.assertNotIn("'unsafe-eval'", (await c.get("/")).headers["content-security-policy"])

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





if __name__ == "__main__":
    unittest.main()
