"""Single inventory UI and manual read-only review; no live API calls."""
import unittest
import os
from unittest.mock import Mock, patch
from types import SimpleNamespace
from threading import Lock
import httpx
import sync_service
import inventory_web
import publication_web
from inventory_schema import normalize_product_row
from sync_bridge_protocol import TOOL_PATHS

PARENT = normalize_product_row({'sku':'PANKOFULL','tipo':'variable','nombre_producto':'Panko','Existencias':'','precio':''})
CHILD = normalize_product_row({'sku':'PANK500','tipo':'variation','sku_padre':'PANKOFULL','nombre_producto':'Panko 500 g','Existencias':5,'precio':40})

class InventoryPage(unittest.TestCase):
    def test_one_catalog_counts_full_parent_disabled_and_escaped_text(self):
        row=dict(CHILD, nombre_producto='<img onerror=bad()>')
        with patch('inventory_web._context', return_value=({'email':'test@example.com'},'sheet',Mock())), \
             patch('inventory_web.read_inventory', return_value=[PARENT,row]), \
             patch('inventory_web.counted_initial_skus', return_value={'PANK500'}), \
             patch('publication_web.WooCommerceClient') as wc:
            response=inventory_web.render_inventory(Mock())
        self.assertEqual(response.status_code,200)
        html=response.body.decode()
        self.assertNotIn('<iframe',html)
        self.assertNotIn('<img onerror',html)
        self.assertIn('&lt;img onerror=bad()&gt;',html)
        self.assertIn("data-sku='PANKOFULL' disabled",html)
        self.assertNotIn("class='bulk-stock' data-sku='PANKOFULL'",html)
        self.assertNotIn("data-sku='PANK500' checked",html)
        self.assertIn('✅ Ya contado',html)
        self.assertIn('inventory.js',html)
        wc.assert_not_called()

    def test_login_required(self):
        with patch('inventory_web._context', side_effect=PermissionError('Conecta Drive')):
            self.assertEqual(inventory_web.render_inventory(Mock()).status_code,401)

    def test_review_downloads_catalog_once_without_any_write(self):
        client=Mock()
        client.catalog_by_sku.return_value=({'PANK500':{'id':8,'type':'variation','_entity_type':'variation','stock_quantity':5,'manage_stock':True,'regular_price':'40','name':'Panko 500 g'}},{})
        client.get_setting.return_value={'id':'woocommerce_hide_out_of_stock_items','value':'no'}
        with patch('inventory_web._session',return_value={'email':'test'}), \
             patch('inventory_web.integration_server._read_master_inventory',return_value=('sheet',[PARENT,CHILD])), \
             patch('publication_web.WooCommerceClient',return_value=client):
            response=publication_web.inventory_review(Mock())
        self.assertTrue(response['ok'])
        client.catalog_by_sku.assert_called_once_with(include_variations=True,force_refresh=True)
        self.assertEqual(set(call[0] for call in client.method_calls),{'catalog_by_sku','get_setting'})
        self.assertTrue(response['visibility']['known'])
        self.assertIsNone(response['rows'][0]['inventory_stock'])
        self.assertIsNone(response['rows'][0]['inventory_price'])
        self.assertEqual(response['rows'][1]['status'],'in_sync')
        self.assertEqual(response['rows'][0]['stock_preview']['status'],'blocked_variable_parent')

    def test_review_requires_session_and_serializes_explicit_scans(self):
        with patch('inventory_web._session',return_value=None),patch('publication_web.WooCommerceClient') as wc:
            self.assertEqual(publication_web.inventory_review(Mock()).status_code,401)
            wc.assert_not_called()
        lock=Lock();lock.acquire()
        with patch('publication_web._PREVIEW_LOCK',lock),patch('inventory_web._session',return_value={'email':'test'}):
            self.assertEqual(publication_web.inventory_review(Mock()).status_code,429)
        lock.release()
        with patch('inventory_web._session',return_value={'email':'test'}), \
             patch('inventory_web.integration_server._read_master_inventory',side_effect=RuntimeError('Read failed')):
            self.assertEqual(publication_web.inventory_review(Mock()).status_code,502)
            self.assertFalse(publication_web._PREVIEW_LOCK.locked())

    def test_history_uses_sku_without_website_requests(self):
        with patch('inventory_web._context',return_value=({},'sheet',Mock())),patch('inventory_web.read_movements',return_value=[{'sku':'PANK500'}]) as history:
            result=inventory_web.inventory_history(Mock(),sku='PANK500')
            self.assertEqual(result['rows'],[{'sku':'PANK500'}])
            self.assertEqual(history.call_args.args[2],'PANK500')
        self.assertIn('/inventory-history',TOOL_PATHS)
        self.assertIn('/inventory-review',TOOL_PATHS)

class LegacyLinks(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.env = patch.dict(os.environ, {'SUITE_DRIVE_ONLY':'false', 'SUITE_SERVICE_ROLE':'sync', 'SYNC_SERVICE_URL':''})
        self.env.start()

    async def asyncTearDown(self):
        self.env.stop()

    async def test_old_pages_redirect_on_worker_and_keep_query(self):
        sid='unified-test-session'
        import time
        sync_service.runtime.SESSIONS[sid]={'expires_at':time.time()+60,'store':{}}
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=sync_service.app),base_url='https://worker.example',cookies={'sync_session':sid}) as client:
                for path,target in [('/inventory-manager?sku=PANK500','/inventory-hub?q=&sku=PANK500'),('/inventory-count?q=Panko','/inventory-hub?q=Panko#catalog'),('/inventory-sync','/inventory-hub#review'),('/woocommerce-publish-preview','/inventory-hub#review'),('/woocommerce-product-sync','/woocommerce-batch-sync')]:
                    response=await client.get(path)
                    self.assertEqual(response.status_code,303)
                    self.assertEqual(response.headers['location'],target)
                    self.assertEqual(response.headers['x-suite-executor'],'sync-service')
        finally:
            sync_service.runtime.SESSIONS.pop(sid,None)

if __name__=='__main__':
    unittest.main()

