import time
import unittest
from unittest.mock import patch, Mock
from loyverse_client import LoyverseClient, LoyverseError
from loyverse_sync import plan_stock


def fixtures():
    rows = [{'sku': 'A', 'nombre_producto': 'Ramen', 'Existencias': 4, 'codigo_barras': '0123456789012'}]
    items = [{'track_stock': True, 'variants': [{'variant_id': 'v', 'sku': 'A', 'barcode': '0123456789012'}]}]
    levels = [{'variant_id': 'v', 'store_id': 's', 'in_stock': 2, 'updated_at': 'now'}]
    return rows, items, levels


class Matching(unittest.TestCase):
    def test_match_and_parent(self):
        rows, items, levels = fixtures()
        rows.append({'sku': 'AFULL', 'tipo': 'variable'})
        result = plan_stock(rows, items, levels, 's')
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]['eligible'])

    def test_wrong_store_missing_and_untracked(self):
        rows, items, levels = fixtures()
        self.assertFalse(plan_stock(rows, items, levels, 'other')[0]['eligible'])
        items[0]['track_stock'] = False
        self.assertFalse(plan_stock(rows, items, levels, 's')[0]['eligible'])
        self.assertEqual(plan_stock(rows, [], [], 's')[0]['status'], 'No existe en Loyverse')

    def test_duplicate_and_conflict(self):
        rows, items, levels = fixtures()
        self.assertFalse(plan_stock(rows * 2, items, levels, 's')[0]['eligible'])
        items[0]['variants'].append({'variant_id': 'other', 'sku': 'B', 'barcode': rows[0]['codigo_barras']})
        self.assertFalse(plan_stock(rows, items, levels, 's')[0]['eligible'])

    def test_barcode_conflict_and_equivalent(self):
        rows, items, levels = fixtures()
        items[0]['variants'][0]['barcode'] = '9999999999999'
        self.assertFalse(plan_stock(rows, items, levels, 's')[0]['eligible'])
        items[0]['variants'][0]['barcode'] = '00123456789012'
        self.assertTrue(plan_stock(rows, items, levels, 's')[0]['eligible'])

    def test_aliases_cannot_write_same_variant(self):
        rows, items, levels = fixtures()
        rows.append(dict(rows[0], sku='B'))
        rows[0]['codigo_barras'] = ''
        self.assertTrue(all(not p['eligible'] for p in plan_stock(rows, items, levels, 's')))

    def test_invalid_quantities(self):
        for val in (None, '', 'nan', 'inf', -1, 10000000):
            rows, items, levels = fixtures()
            rows[0]['Existencias'] = val
            self.assertFalse(plan_stock(rows, items, levels, 's')[0]['eligible'])


class Transport(unittest.TestCase):
    @patch('loyverse_client.requests.request')
    def test_redirect_no_secret_in_error(self, send):
        send.return_value = Mock(status_code=302)
        with self.assertRaises(LoyverseError) as exc:
            LoyverseClient('secret-token').list('stores')
        self.assertNotIn('secret-token', str(exc.exception))
        self.assertFalse(send.call_args.kwargs['allow_redirects'])
        self.assertEqual(send.call_count, 1)

    def test_pagination_and_cycles(self):
        api = LoyverseClient('secret-token')
        with patch.object(api, 'request', side_effect=[{'items': [1], 'cursor': 'next'}, {'items': [2]}]):
            self.assertEqual(api.list('items'), [1, 2])
        with patch.object(api, 'request', return_value={'items': [], 'cursor': 'same'}):
            with self.assertRaises(LoyverseError): api.list('items')


class Workflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ.setdefault('GOOGLE_CLIENT_ID', 'test')
        os.environ.setdefault('GOOGLE_CLIENT_SECRET', 'test')
        os.environ.setdefault('GOOGLE_REDIRECT_URI', 'https://example.com/auth/callback')
        import service_entrypoint
        import loyverse_web
        cls.web = loyverse_web
        cls.app = service_entrypoint.fastapi_app

    def setUp(self):
        self.value = {'expires_at': time.time()+1000, 'loyverse_token': 'secret-token'}
        self.web.runtime.SESSIONS['test-loy'] = self.value
        self.request = Mock(cookies={'session_id': 'test-loy'})
        self.rows = plan_stock(*fixtures(), 's')
        self.value['loyverse_preview'] = {'id': 'p', 'store': 's', 'rows': self.rows, 'expires': time.time()+100}

    def tearDown(self):
        self.web.runtime.SESSIONS.pop('test-loy', None)

    def test_auth_and_csrf(self):
        from fastapi.testclient import TestClient
        c = TestClient(self.app)
        self.assertEqual(c.get('/loyverse').status_code, 401)
        self.assertEqual(c.post('/loyverse/connect', json={'token':'secret-token'}).status_code, 403)

    def test_stale_preview_blocks_write(self):
        with patch.object(self.web, 'compare', return_value=[]), patch.object(self.web, 'client') as api:
            with self.assertRaises(ValueError): self.web.operate(self.request, 'apply', {'id':'p','skus':['A']})
            api.assert_not_called()
        self.assertNotIn('loyverse_preview', self.value)

    def test_one_use_and_confirmed_write(self):
        api = Mock()
        api.list.return_value = fixtures()[2]
        api.set_stock.return_value = {'inventory_levels': [{'variant_id':'v', 'store_id':'s', 'in_stock':4}]}
        with patch.object(self.web, 'compare', return_value=self.rows), patch.object(self.web, 'client', return_value=api):
            result = self.web.operate(self.request, 'apply', {'id':'p','skus':['A']})
            self.assertEqual(result['completed'], ['A'])
            with self.assertRaises(ValueError): self.web.operate(self.request, 'apply', {'id':'p','skus':['A']})
            api.set_stock.assert_called_once_with('v', 's', 4)

    def test_uncertain_write_is_not_retried(self):
        api = Mock()
        api.list.return_value = fixtures()[2]
        api.set_stock.side_effect = LoyverseError('timeout')
        with patch.object(self.web, 'compare', return_value=self.rows), patch.object(self.web, 'client', return_value=api):
            result = self.web.operate(self.request, 'apply', {'id':'p','skus':['A']})
        self.assertEqual(result['uncertain'], 'A')
        self.assertEqual(result['completed'], [])
        api.set_stock.assert_called_once()

    def test_disconnect_and_expiry(self):
        self.web.operate(self.request, 'disconnect', {})
        self.assertNotIn('loyverse_token', self.value)
        self.value['expires_at'] = 0
        with self.assertRaises(PermissionError): self.web.operate(self.request, 'preview', {})
