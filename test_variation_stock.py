"""Own, inherited and unknown stock are distinct; no live WooCommerce calls."""
import unittest

from woocommerce_client import WooCommerceClient, WooCommerceConfig
from woocommerce_inventory import compare_product
from woocommerce_stock import attach_parent_stock, stock_reading
from woocommerce_publish_preview import build_stock_publish_preview

PARENT = {"id": 10, "sku": "PFULL", "type": "variable", "manage_stock": True, "stock_quantity": 7}
CHILD = {"id": 11, "sku": "P500", "manage_stock": False, "stock_quantity": None, "stock_status": "instock", "price": "10"}
INVENTORY = {"sku": "P500", "tipo": "variation", "sku_padre": "PFULL", "precio": 10, "Existencias": 2}


class VariationStock(unittest.TestCase):
    def test_inherited_quantity_is_shown_as_shared(self):
        product = attach_parent_stock(CHILD, PARENT)
        reading = stock_reading(product)
        self.assertEqual(reading["quantity"], 7)
        self.assertTrue(reading["inherited"])
        self.assertEqual(reading["parent_sku"], "PFULL")
        preview = compare_product(INVENTORY, product)
        self.assertEqual(preview.woocommerce_stock, 7)
        self.assertEqual(preview.status, "stock_inherited")
        self.assertNotIn("stock", preview.changes)

    def test_parent_literal_is_not_unmanaged(self):
        reading = stock_reading(dict(CHILD, manage_stock="parent", stock_quantity=4))
        self.assertEqual(reading["quantity"], 4)
        self.assertTrue(reading["managed"])
        self.assertEqual(reading["source"], "parent")

    def test_own_stock_wins_over_parent(self):
        reading = stock_reading(attach_parent_stock(dict(CHILD, manage_stock=True, stock_quantity=3), PARENT))
        self.assertEqual(reading["quantity"], 3)
        self.assertFalse(reading["inherited"])

    def test_unknown_stock_is_never_invented_as_zero(self):
        reading = stock_reading(attach_parent_stock(CHILD, dict(PARENT, manage_stock=False)))
        self.assertIsNone(reading["quantity"])
        self.assertEqual(reading["source"], "availability")
        self.assertEqual(reading["availability"], "instock")

    def test_catalog_reads_variation_and_parent_once(self):
        client = WooCommerceClient(WooCommerceConfig("https://store.example",cache_ttl=0))
        client.list_products_catalog = lambda **kwargs: [PARENT]
        client.list_all_variations_catalog = lambda parent: [CHILD]
        index, duplicates = client.catalog_by_sku()
        self.assertEqual(stock_reading(index['P500'])["quantity"], 7)
        self.assertEqual(index['P500']['_parent_product_id'], 10)
        self.assertFalse(duplicates)

    def test_shared_stock_cannot_be_published_as_each_childs_stock(self):
        client = WooCommerceClient(WooCommerceConfig("https://store.example",cache_ttl=0))
        client.get_setting = lambda *args: {"value": "no"}
        product = attach_parent_stock(dict(CHILD,_entity_type="variation"), PARENT)
        result = build_stock_publish_preview([INVENTORY], client, catalog=({"P500":product},{}))
        self.assertEqual(result['rows'][0]['status'], 'shared_parent_stock')
        self.assertIsNone(result['rows'][0]['stock_to_publish'])


if __name__ == '__main__':
    unittest.main()
