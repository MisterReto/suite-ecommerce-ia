"""Network isolation regressions; no external calls or credentials."""
import ast
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from store_connection import drive_only, require_store_connection

ROOT = Path(__file__).parent

def request_method(filename, class_name, name):
    tree = ast.parse((ROOT / filename).read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), fn], type_ignores=[])
    scope = {'require_store_connection': require_store_connection, 'WooCommerceError': RuntimeError, 'WordPressMediaError': RuntimeError}
    exec(compile(ast.fix_missing_locations(module), filename, 'exec'), scope)
    return scope[name]

class StoreIsolationTests(unittest.TestCase):
    def test_default_and_invalid_configuration_fail_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(drive_only())
        with patch.dict(os.environ, {'SUITE_DRIVE_ONLY': 'typo'}):
            self.assertTrue(drive_only())

    def test_all_store_requests_block_before_network_even_with_write_enabled(self):
        cases = [('woocommerce_client.py', 'WooCommerceClient', 'request'), ('wordpress_media.py', 'WordPressMediaClient', '_request')]
        with patch.dict(os.environ, {'SUITE_DRIVE_ONLY': 'true'}):
            for filename, cls, name in cases:
                fn = request_method(filename, cls, name)
                client = SimpleNamespace(session=Mock(), config=SimpleNamespace(write_enabled=True), write_enabled=True)
                for method in ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']:
                    with self.subTest(client=cls, method=method):
                        with self.assertRaisesRegex(RuntimeError, 'solo Drive'):
                            fn(client, method, 'products')
                client.session.request.assert_not_called()

    def test_wordpress_writes_require_flag_even_without_require_write_argument(self):
        fn = request_method('wordpress_media.py', 'WordPressMediaClient', '_request')
        client = SimpleNamespace(write_enabled=False, session=Mock())
        with patch.dict(os.environ, {'SUITE_DRIVE_ONLY': 'false'}):
            for method in ['POST', 'PUT', 'PATCH', 'DELETE']:
                with self.assertRaisesRegex(RuntimeError, 'deshabilitada'):
                    fn(client, method, 'media')
        client.session.request.assert_not_called()

if __name__ == '__main__':
    unittest.main()
