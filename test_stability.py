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



if __name__ == "__main__":
    unittest.main()
