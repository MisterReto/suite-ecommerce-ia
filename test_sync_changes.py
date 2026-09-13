import ast
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from woo_to_sheets_colab import make_plan, record, category_paths


class SyncTests(unittest.TestCase):
    def test_import_preserves_formulas_and_drive_images(self):
        values = [["sku", "categorias", "imagenes", "precio"], ["A", "Old", "A_1.png", "10"]]
        formulas = [values[0], ["A", "Old", "A_1.png", "=5*2"]]
        writes, report, _, _ = make_plan(values, formulas, [
            {"sku": "A", "categorias": "Bebidas > Jugos y Sodas", "precio": "20"},
            {"sku": "B", "categorias": "Dulces"},
        ])
        addresses = [w["range"] for w in writes]
        self.assertIn("B2", addresses)
        self.assertNotIn("C2", addresses)
        self.assertNotIn("D2", addresses)
        self.assertIn("A3", addresses)

    def test_duplicate_sheet_sku_aborts(self):
        rows = [["sku", "categorias"], ["A", ""], ["A", ""]]
        with self.assertRaises(ValueError):
            make_plan(rows, rows, [])

    def test_variation_inherits_category_but_not_stock(self):
        paths = category_paths([{"id": 1, "name": "Bebidas", "parent": 0}, {"id": 2, "name": "Jugos y Sodas", "parent": 1}])
        parent = {"id": 10, "name": "Soda", "sku": "", "categories": [{"id": 1}, {"id": 2}]}
        child = {"id": 11, "sku": "SODA", "stock_quantity": None, "attributes": [{"name": "Sabor", "option": "Fresa"}]}
        result = record(child, paths, parent)
        self.assertEqual(result["categorias"], "Bebidas > Jugos y Sodas")
        self.assertEqual(result["woocommerce_parent_id"], "10")
        self.assertNotIn("Existencias", result)
        self.assertEqual(result["atributo_valor"], "Fresa")
        self.assertNotIn("imagenes", result)

    def test_direct_sku_avoids_catalog(self):
        # Compile the actual method, without importing network dependencies.
        module = ast.parse(Path(__file__).with_name("woocommerce_client.py").read_text())
        cls = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == "WooCommerceClient")
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "find_entity_by_sku")
        scope = {"Any": object, "WooCommerceError": RuntimeError}
        exec(compile(ast.Module(body=[method], type_ignores=[]), "method", "exec"), scope)
        class Client:
            def request(self, *a, **k):
                return [{"id": 2, "sku": "TEST", "type": "variation", "parent_id": 1}]
            def _slim(self, row, kind, parent):
                return dict(row, _entity_type=kind, _parent_product_id=parent)
            def catalog_by_sku(self, **k):
                raise AssertionError("Full catalog must not be loaded")
        result = scope["find_entity_by_sku"](Client(), "TEST")
        self.assertEqual(result["_parent_product_id"], 1)
        self.assertEqual(result["_entity_type"], "variation")


if __name__ == "__main__":
    unittest.main()
