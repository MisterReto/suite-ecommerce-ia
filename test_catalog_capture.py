"""Identity, barcode and transactional family capture regressions."""
import unittest

from catalog_capture import (barcode, barcode_key, find_duplicate, next_parent_sku,
                             prepare_capture_updates, presentation, review_product)
from inventory_schema import MASTER_COLUMNS

PARENT = {"sku": "PANKFULL", "tipo": "variable", "nombre_producto": "Panko", "Marca": "Brand",
          "atributo_nombre": "Tamaño", "atributo_valor": "500 g", "imagenes": "old.jpg"}
CHILD = {"sku": "PANK500", "tipo": "variation", "sku_padre": "PANKFULL", "nombre_producto": "Panko 500 g",
         "Marca": "Brand", "atributo_nombre": "Tamaño", "atributo_valor": "500 g", "codigo_barras": "036000291452"}


def values(*rows):
    return [list(MASTER_COLUMNS) + ["", "", "", "", "atributo_nombre", "atributo_valor", "codigo_barras"]] + [
        [r.get(k, "") for k in MASTER_COLUMNS] + ["", "", "", "", r.get("atributo_nombre", ""), r.get("atributo_valor", ""), r.get("codigo_barras", "")] for r in rows]


class Identity(unittest.TestCase):
    def test_barcode_preserves_leading_zero_and_equivalent_formats(self):
        self.assertEqual(barcode("036000291452"), "036000291452")
        self.assertEqual(barcode_key("036000291452"), barcode_key("0036000291452"))
        for bad in ("036000291453", "1234", "9999999999999999", "1e+12"):
            with self.assertRaises(ValueError):
                barcode(bad)

    def test_barcode_duplicate_even_with_a_different_sku(self):
        row, reason = find_duplicate([CHILD], dict(CHILD, sku="NEW", codigo_barras="0036000291452"))
        self.assertEqual(row["sku"], "PANK500")
        self.assertEqual(reason, "código de barras")

    def test_same_option_cannot_be_inserted_twice(self):
        row, reason = find_duplicate([CHILD], dict(CHILD, sku="NEW", codigo_barras="", atributo_valor="0.5 kg"))
        self.assertEqual(reason, "atributo de la variación")
        self.assertEqual(presentation("0.5 kg"), presentation("500 g"))

    def test_new_size_is_a_possible_variation_not_duplicate(self):
        candidate = dict(CHILD, sku="PANK1000", nombre_producto="Panko 1 kg", atributo_valor="1 kg", codigo_barras="")
        result = review_product([PARENT, CHILD], candidate)
        self.assertEqual(result["status"], "possible_variation")
        self.assertEqual(result["suggested"], "PANKFULL")

    def test_other_brands_do_not_get_recommended_as_parents(self):
        result = review_product([PARENT], {"sku": "OTHER", "nombre_producto": "Panko 1 kg", "Marca": "Other"})
        self.assertEqual(result["suggested"], "")
        self.assertEqual(len(result["parents"]), 1)

    def test_no_barcode_same_product_in_other_units_is_still_duplicate(self):
        row, reason = find_duplicate([dict(CHILD, codigo_barras="")],
            {"sku": "NEW", "nombre_producto": "Panko 0.5 kg", "Marca": "Brand", "gramaje": "500 g"})
        self.assertEqual(row["sku"], "PANK500")

    def test_parent_sku_collision_gets_a_new_suffix(self):
        first = next_parent_sku("Panko 1 kg", "Brand", [])
        second = next_parent_sku("Panko 500 g", "Brand", [{"sku": first}])
        self.assertNotEqual(first, second)
        self.assertTrue(second.endswith("FULL"))


class AppendPlanning(unittest.TestCase):
    def test_new_parent_and_child_are_in_one_atomic_plan(self):
        record = dict(CHILD, _new_parent=PARENT, _parent_cover="PANKFULL_portada.jpg")
        updates = prepare_capture_updates(values(), record)
        parent = next(x["values"][0] for x in updates if "A2:U2" in x["range"])
        child = next(x["values"][0] for x in updates if "A3:U3" in x["range"])
        self.assertEqual(parent[1], "variable")
        self.assertEqual([parent[7], parent[11], parent[12]], ["", "", ""])
        self.assertEqual(child[1], "variation")
        self.assertEqual(child[0], "PANKFULL")
        self.assertEqual(child[20], "036000291452")
        self.assertEqual(parent[13], "PANKFULL_portada.jpg,old.jpg")

    def test_existing_parent_keeps_other_images_and_its_commercial_cells(self):
        record = dict(CHILD, _parent_cover="new_cover.jpg")
        updates = prepare_capture_updates(values(PARENT), record)
        cover = next(x for x in updates if x["range"].endswith("!N2"))
        self.assertEqual(cover["values"], [["new_cover.jpg,old.jpg"]])
        self.assertFalse(any("A2:" in x["range"] for x in updates))

    def test_duplicate_attribute_and_gtin_block_the_plan(self):
        for child in (dict(CHILD, sku="NEW", codigo_barras=""), dict(CHILD, sku="NEW", sku_padre="OTHER")):
            with self.assertRaisesRegex(ValueError, "ya existe"):
                prepare_capture_updates(values(PARENT, CHILD), child)

    def test_parent_is_required_and_other_brand_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "padre"):
            prepare_capture_updates(values(), CHILD)
        with self.assertRaisesRegex(ValueError, "marca"):
            prepare_capture_updates(values(PARENT), dict(CHILD, Marca="Other"))

    def test_existing_family_is_selected_instead_of_recreated(self):
        with self.assertRaisesRegex(ValueError, "padre con ese nombre"):
            prepare_capture_updates(values(PARENT), dict(CHILD, sku_padre="NEWFULL", _new_parent=dict(PARENT,sku="NEWFULL")))

    def test_unrelated_column_is_never_overwritten(self):
        grid = values(PARENT)
        grid[0][20] = "private_other_field"
        with self.assertRaisesRegex(ValueError, "columna U"):
            prepare_capture_updates(grid, CHILD)


if __name__ == '__main__':
    unittest.main()
