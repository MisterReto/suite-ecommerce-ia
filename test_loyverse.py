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
            result = self.web.operate(self.request, 'apply', {'id':'p','skus':['A']})
            self.assertIn('cambió', result['error'])
            api.return_value.set_stock.assert_not_called()
            api.return_value.create_item.assert_not_called()
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


class CatalogCreation(unittest.TestCase):
    def plan(self, rows, items=None):
        from loyverse_sync import plan_catalog
        return plan_catalog(rows, items or [], [], 's', [{'id':'s'}, {'id':'other'}])

    def row(self, **kw):
        return dict({'sku':'NEW', 'tipo':'simple', 'nombre_producto':'Nuevo ramen', 'precio':25,
                     'Existencias':8, 'codigo_barras':'0123456789012'}, **kw)

    def test_missing_simple_is_selectable_and_zero_stock_is_explicit(self):
        p=self.plan([self.row()])[0]
        self.assertTrue(p['eligible'])
        self.assertEqual(p['action'],'create')
        self.assertEqual(p['drive'],8)
        self.assertNotIn('stock_after',str(p['payload']))
        v=p['payload']['variants'][0]
        self.assertEqual(v['default_price'],25)
        self.assertEqual(v['barcode'],'0123456789012')
        self.assertEqual({s['store_id']:s['available_for_sale'] for s in v['stores']},{'s':True,'other':False})

    def test_family_created_as_one_item_with_two_variants(self):
        rows=[self.row(sku='PFULL',tipo='variable',precio='',codigo_barras=''),
              self.row(sku='A',sku_padre='PFULL',tipo='variation',atributo_nombre='Sabor',atributo_valor='Uva'),
              self.row(sku='B',sku_padre='PFULL',tipo='variation',atributo_nombre='Sabor',atributo_valor='Fresa',codigo_barras='')]
        p=self.plan(rows)
        self.assertEqual(len(p),1)
        self.assertTrue(p[0]['eligible'])
        self.assertEqual(p[0]['sku'],'PFULL')
        self.assertEqual([v['option1_value'] for v in p[0]['payload']['variants']],['Uva','Fresa'])

    def test_conflicts_and_bad_prices_block_creation(self):
        for row in [self.row(precio=''),self.row(precio='nan'),self.row(codigo_barras=123456789012),self.row(tipo='variation')]:
            self.assertFalse(self.plan([row])[0]['eligible'])
        self.assertFalse(self.plan([self.row()], [{'item_name':'Nuevo ramen','variants':[]}])[0]['eligible'])
        self.assertTrue(all(not p['eligible'] for p in self.plan([self.row(),self.row(sku='B')])))

    def test_missing_parent_blocks_orphan(self):
        p=self.plan([self.row(sku_padre='ABSENT',tipo='variation')])[0]
        self.assertFalse(p['eligible'])
        self.assertIn('padre',p['status'])

    def test_existing_family_not_recreated(self):
        rows=[self.row(sku='PFULL',tipo='variable',precio='',codigo_barras=''),
              self.row(sku='A',sku_padre='PFULL',tipo='variation',atributo_valor='Uva'),
              self.row(sku='B',sku_padre='PFULL',tipo='variation',atributo_valor='Fresa',codigo_barras='')]
        items=[{'item_name':'Old','track_stock':True,'variants':[{'sku':'A','variant_id':'v'}]}]
        result=self.plan(rows,items)
        self.assertTrue(all(not p['eligible'] for p in result))


class CreationWorkflow(Workflow):
    def test_creation_is_confirmed_without_stock_write_and_not_replayed(self):
        row=CatalogCreation().plan([CatalogCreation().row()])[0]
        self.value['loyverse_preview']['rows']=[row]
        api=Mock()
        api.create_item.return_value={'id':'item','variants':[{'sku':'NEW','variant_id':'v'}]}
        with patch.object(self.web,'compare',return_value=[row]),patch.object(self.web,'client',return_value=api):
            result=self.web.operate(self.request,'apply',{'id':'p','skus':['NEW']})
            self.assertEqual(result['created'],['NEW'])
            api.set_stock.assert_not_called()
            with self.assertRaises(ValueError):self.web.operate(self.request,'apply',{'id':'p','skus':['NEW']})
            api.create_item.assert_called_once()

    def test_uncertain_creation_is_not_retried(self):
        row=CatalogCreation().plan([CatalogCreation().row()])[0]
        self.value['loyverse_preview']['rows']=[row]
        api=Mock();api.create_item.side_effect=LoyverseError('timeout')
        with patch.object(self.web,'compare',return_value=[row]),patch.object(self.web,'client',return_value=api):
            result=self.web.operate(self.request,'apply',{'id':'p','skus':['NEW']})
            self.assertEqual(result['uncertain'],'NEW')
            self.assertEqual(result['created'],[])
            api.create_item.assert_called_once()


class UploadExecution(CreationWorkflow):
    def test_batch_reads_full_catalog_once_and_uses_recent_changes_per_item(self):
        first=CatalogCreation().row()
        second=CatalogCreation().row(sku='NEXT', nombre_producto='Nuevo snack', codigo_barras='')
        rows=[first,second]
        from loyverse_sync import plan_catalog
        stores=[{'id':'s'},{'id':'other'}]
        planned=plan_catalog(rows,[],[],'s',stores)
        self.value['loyverse_preview']['rows']=planned
        api=Mock();api.list.return_value=[]
        api.create_item.side_effect=[{'id':'i1','item_name':'Nuevo ramen','variants':[{'sku':'NEW','variant_id':'v1'}]},
                                    {'id':'i2','item_name':'Nuevo snack','variants':[{'sku':'NEXT','variant_id':'v2'}]}]
        def compare(request,value,store,bundle=None,api=None):
            bundle.update(rows=rows,items=[],levels=[],stores=stores)
            return planned
        events=[]
        with patch.object(self.web,'compare',side_effect=compare) as full,patch.object(self.web,'client',return_value=api):
            preview,selected=self.web.consume_preview(self.value,{'id':'p','skus':['NEW','NEXT']})
            result=self.web.execute_upload(self.request,self.value,preview,selected,lambda **event:events.append(event))
        self.assertEqual(result['created'],['NEW','NEXT'])
        full.assert_called_once()
        self.assertEqual(api.list.call_count,2)
        self.assertTrue(all('updated_at_min' in c.kwargs for c in api.list.call_args_list))
        self.assertEqual([e['done'] for e in events if 'done' in e],[1,2])

    def test_incremental_conflict_is_detected_before_post(self):
        raw=CatalogCreation().row()
        from loyverse_sync import plan_catalog
        stores=[{'id':'s'},{'id':'other'}]
        planned=plan_catalog([raw],[],[],'s',stores)
        self.value['loyverse_preview']['rows']=planned
        api=Mock();api.list.return_value=[{'id':'new-conflict','item_name':'Nuevo ramen','variants':[]}]
        def compare(request,value,store,bundle=None,api=None):
            bundle.update(rows=[raw],items=[],levels=[],stores=stores)
            return planned
        with patch.object(self.web,'compare',side_effect=compare),patch.object(self.web,'client',return_value=api):
            result=self.web.operate(self.request,'apply',{'id':'p','skus':['NEW']})
        self.assertIn('catálogo cambió',result['error'])
        self.assertIsNone(result['uncertain'])
        api.create_item.assert_not_called()

    def test_partial_failure_preserves_confirmed_results(self):
        raw=[CatalogCreation().row(),CatalogCreation().row(sku='NEXT',nombre_producto='Nuevo snack',codigo_barras='')]
        from loyverse_sync import plan_catalog
        stores=[{'id':'s'},{'id':'other'}]; planned=plan_catalog(raw,[],[],'s',stores)
        self.value['loyverse_preview']['rows']=planned
        api=Mock();api.list.return_value=[]
        api.create_item.side_effect=[{'id':'i1','item_name':'Nuevo ramen','variants':[{'sku':'NEW','variant_id':'v1'}]},LoyverseError('timeout')]
        def compare(request,value,store,bundle=None,api=None):
            bundle.update(rows=raw,items=[],levels=[],stores=stores);return planned
        with patch.object(self.web,'compare',side_effect=compare),patch.object(self.web,'client',return_value=api):
            result=self.web.operate(self.request,'apply',{'id':'p','skus':['NEW','NEXT']})
        self.assertEqual(result['created'],['NEW'])
        self.assertEqual(result['uncertain'],'NEXT')
        self.assertEqual(result['done'],1)
        self.assertEqual(api.create_item.call_count,2)


class HttpUploads(unittest.TestCase):
    setUpClass = classmethod(Workflow.setUpClass.__func__)
    setUp = Workflow.setUp
    tearDown = Workflow.tearDown

    def test_apply_returns_202_before_work_finishes_and_status_is_session_owned(self):
        import threading
        from fastapi.testclient import TestClient
        import loyverse_jobs
        entered, release = threading.Event(), threading.Event()
        def upload(request, value, preview, selected, progress):
            entered.set()
            progress(current='A', phase='Enviando a Loyverse')
            release.wait(3)
            return {'done':1,'completed':['A'],'created':[],'error':None,'uncertain':None}
        http=TestClient(self.app)
        http.cookies.set('session_id','test-loy')
        try:
            with patch.object(self.web,'execute_upload',side_effect=upload):
                first=http.post('/loyverse/apply',json={'id':'p','skus':['A']},headers={'Origin':'http://testserver'})
                self.assertEqual(first.status_code,202)
                self.assertTrue(entered.wait(1))
                job_id=first.json()['id']
                status=http.get('/loyverse-upload-status',params={'job_id':job_id})
                self.assertEqual(status.status_code,200)
                self.assertEqual(status.json()['job']['current'],'A')
                retry=http.post('/loyverse/apply',json={'id':'p','skus':['A']},headers={'Origin':'http://testserver'})
                self.assertEqual(retry.status_code,202)
                self.assertEqual(retry.json()['id'],job_id)
                self.assertEqual(http.get('/loyverse-upload-status?job_id=unknown').status_code,404)
                outsider=TestClient(self.app)
                self.assertEqual(outsider.get('/loyverse-upload-status',params={'job_id':job_id}).status_code,401)
                release.set()
                for _ in range(100):
                    if loyverse_jobs.status(self.value)['state'] not in loyverse_jobs.ACTIVE_STATES:
                        break
                    threading.Event().wait(.01)
                self.assertEqual(loyverse_jobs.status(self.value)['state'],'done')
        finally:
            release.set()

    def test_invalid_selection_does_not_consume_review(self):
        with self.assertRaises(ValueError):
            self.web.start_upload(self.request,{'id':'p','skus':['not-eligible']})
        self.assertIn('loyverse_preview',self.value)


class Deadlines(unittest.TestCase):
    @patch('loyverse_client.requests.request')
    def test_deadline_expiry_blocks_requests_and_does_not_retry_writes(self, send):
        api=LoyverseClient('secret-token',deadline=time.monotonic()-1)
        with self.assertRaises(LoyverseError):
            api.create_item({'item_name':'New','variants':[]})
        send.assert_not_called()
