"""Single variation axis through capture, catalog edits, Sheets and review."""
from catalog_platform.database import transaction
from catalog_platform.imports import normalize
from catalog_platform.models import Product
from test_catalog_platform import setup, create, ORIGIN
from test_functional_parity import capture_store, start
from test_product_edit import drive_edit
from test_studio_api import wait


def test_catalog_rejects_multiple_attributes_without_writing(setup):
    client, *_ = setup
    product = create(client, attributes={"Sabor": "Chocolate"})
    response = client.put('/api/platform/products/' + product['id'], json={**product,
        'attributes': {'Sabor': 'Chocolate', 'Tamaño': '40 g'}}, headers=ORIGIN)
    assert response.status_code == 422 and 'un solo atributo' in response.text
    assert client.get('/api/platform/products/' + product['id']).json()['product']['attributes'] == {'Sabor': 'Chocolate'}


def test_sheet_canonical_attribute_wins_over_legacy_ai_metadata():
    rows, errors = normalize([dict(sku='RAMEN', nombre_producto='Maruchan', tipo='simple',
        attributes={'Tipo reconocido': 'Ramen', 'Tamaño': '85 g', 'Sabor': 'Anterior'},
        atributo_nombre='Sabor', atributo_valor='Camarón, Limón y Habanero')])
    assert not errors
    assert rows[0]['attributes'] == {'Sabor': 'Camarón, Limón y Habanero'}


def test_edit_replaces_and_clears_canonical_attribute_cells(drive_edit):
    client, _, sheet = drive_edit
    product = create(client, attributes={'Sabor': 'Chocolate'})
    for attrs in ({'Color': 'Rojo'}, {}):
        response = client.put('/api/platform/products/' + product['id'], json={**product,
            'attributes': attrs, 'sync_drive': True}, headers=ORIGIN)
        assert response.status_code == 200 and response.json()['drive_saved'], response.text
        product = response.json()['product']
        assert sheet.rows[1][18:20] == list(next(iter(attrs.items()), ('', '')))


def test_variant_uses_parent_axis_and_one_value(setup):
    client, *_ = setup
    parent = create(client, sku='RAMENFULL', product_type='variable', attributes={'Sabor': ['Camarón']})
    invalid = client.post('/api/platform/products', json={'sku': 'RAMEN', 'name': 'Ramen',
        'product_type': 'variation', 'parent_sku': parent['sku'], 'attributes': {'Tamaño': '85 g'}}, headers=ORIGIN)
    assert invalid.status_code == 422 and 'Sabor' in invalid.text
    invalid = client.post('/api/platform/products', json={'sku': 'RAMEN', 'name': 'Ramen',
        'product_type': 'variation', 'parent_sku': parent['sku'], 'attributes': {'Sabor': ['Camarón', 'Pollo']}}, headers=ORIGIN)
    assert invalid.status_code == 422 and 'un solo valor' in invalid.text


def test_capture_ignores_extra_attributes_and_keeps_compound_flavor(capture_store):
    client, value, _, values, *_ = capture_store
    p = start(client, kind='Variable', product_type='Ramen', attributes={'Tamaño':'85 g', 'Sabor':'Anterior'})
    proposed = client.get('/api/parents').json()
    flavor = 'Camarón, Limón y Habanero'
    p.update(parent_sku=proposed['parent_sku'], parent_name=proposed['parent_name'], attribute_value=flavor)
    response = client.put('/api/draft', json=p, headers=ORIGIN)
    assert response.json()['draft']['product']['attributes'] == {'Sabor': flavor}
    cover = wait(client, client.post('/api/family-cover', headers=ORIGIN))
    assert cover['job']['status'] == 'completed', cover
    saved = wait(client, client.post('/api/save', json={'confirm': True}, headers=ORIGIN))
    assert saved['job']['status'] == 'completed' and saved['draft']['sync_status'] == 'synced', saved
    with transaction() as db:
        child = db.get(Product, saved['draft']['master_product_id'])
        assert child.attributes == {'Sabor': flavor}
        assert db.get(Product, child.parent_id).attributes == {'Sabor': [flavor]}
        from catalog_platform.attributes import image_product
        assert image_product(db, child)['size'] == '40 g'
