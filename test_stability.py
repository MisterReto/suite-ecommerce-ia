"""Focused regressions; no live API calls or paid generations."""
import ast
import base64
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
from PIL import Image, ImageDraw
from inventory_schema import is_variable_parent
from app_security import clean_html

ROOT = Path(__file__).parent

def functions(filename, names, scope):
    tree = ast.parse((ROOT / filename).read_text())
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
    for node in nodes:
        node.decorator_list = []
    exec(compile(ast.Module(body=nodes, type_ignores=[]), filename, "exec"), scope)
    return scope

class Stability(unittest.TestCase):
    def test_canonical_adapter_no_longer_rewrites_source_or_imports_gradio(self):
        source = (ROOT / "app.py").read_text()
        adapter = (ROOT / "ai_app.py").read_text()
        for filename in ("app.py", "ai_app.py", "product_capture.py", "studio_api.py"):
            tree = ast.parse((ROOT / filename).read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertFalse(any(n.name == "gradio" for n in node.names))
                elif isinstance(node, ast.ImportFrom):
                    self.assertNotEqual(node.module, "gradio")
        self.assertNotIn('_replace_once', adapter)
        self.assertNotIn('exec(', adapter)
        self.assertIn('from studio_api import app as fastapi_app', (ROOT / "service_entrypoint.py").read_text())
        self.assertIn('legacy._AUTO_SYNC_AFTER_SAVE = None', (ROOT / "ai_app.py").read_text())
        self.assertIn('fastapi_app.mount("/suite-static"', source)
        self.assertNotIn('fastapi_app.mount("/static"', source)

    def test_blank_image_rejected(self):
        scope = functions("app.py", {"_validacion_local_imagen"}, {"Image": Image})
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "image.png")
            Image.new("RGB", (1024, 1024), "white").save(path)
            self.assertTrue(scope["_validacion_local_imagen"](path))
            img = Image.new("RGB", (1024, 1024), "white")
            ImageDraw.Draw(img).rectangle((200, 200, 800, 800), fill="red")
            img.save(path)
            self.assertEqual(scope["_validacion_local_imagen"](path), [])

    def test_thought_image_not_used(self):
        scope = functions("app.py", {"_extraer_imagen_bytes"}, {"base64": base64})
        parts = [
            NS(thought=True, inline_data=NS(mime_type="image/png", data=b"thought")),
            NS(thought=False, inline_data=NS(mime_type="image/png", data=base64.b64encode(b"final").decode())),
        ]
        response = NS(candidates=[NS(content=NS(parts=parts))])
        self.assertEqual(scope["_extraer_imagen_bytes"](response), b"final")

    def test_parent_stock_is_information(self):
        scope = functions("woocommerce_publish_preview.py", {"build_stock_publish_preview"},
                          {"Any": object, "WooCommerceClient": object, "is_variable_parent": is_variable_parent, "inspect_out_of_stock_visibility": lambda c: {}})
        client = NS(catalog_by_sku=lambda **kw: ({}, {}))
        result = scope["build_stock_publish_preview"]([{"sku": "PARENT", "tipo": "variable", "sku_padre": "", "Existencias": ""}], client)
        self.assertIsNone(result["rows"][0]["stock_to_publish"])
        self.assertEqual(result["summary"]["missing"], 0)

    def test_parent_payload_does_not_zero_children(self):
        scope = functions("woocommerce_product_sync.py",
            {"sync_complete_product", "_text", "_money", "_pricing_and_stock"},
            {"Any": object, "WooCommerceClient": object, "is_variable_parent": is_variable_parent, "clean_html": clean_html,
             "resolve_taxonomies": lambda c, r: {"category_ids": [], "tag_ids": [], "brand_ids": [], "warnings": []}})
        class Client:
            config = NS(write_enabled=True)
            def update_product(self, pid, payload):
                self.payload = payload
                return dict(payload, id=pid, sku="PARENT", type="variable")
        client = Client()
        result = scope["sync_complete_product"](row={"sku": "PARENT", "nombre_producto": "Cover"},
            wc_client=client, wc_entity={"id": 1, "type": "variable"}, verify_get=False)
        self.assertFalse(client.payload["manage_stock"])
        self.assertNotIn("stock_quantity", client.payload)
        self.assertNotIn("regular_price", client.payload)
        self.assertTrue(result["backend_verified"])

if __name__ == "__main__":
    unittest.main()
