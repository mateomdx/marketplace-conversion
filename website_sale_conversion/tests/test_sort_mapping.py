# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged

from ..models.website import VELOCITY_ORDER


@tagged('post_install', '-at_install')
class TestSortMapping(TransactionCase):

    def setUp(self):
        super().setUp()
        self.website = self.env['website'].search([], limit=1)

    def test_velocity_is_first_and_natives_survive(self):
        """'Más vendidos' primero, sin perder ninguna opción nativa."""
        mapping = self.website._get_product_sort_mapping()
        self.assertEqual(mapping[0][0], VELOCITY_ORDER)
        keys = [key for key, _label in mapping]
        for native in ('website_sequence asc', 'publish_date desc', 'name asc',
                       'list_price asc', 'list_price desc'):
            self.assertIn(native, keys, "se perdió una opción nativa: %s" % native)

    def test_shop_default_sort_accepts_velocity(self):
        """El Selection dinámico admite el valor nuevo (no lo valida contra
        una lista estática: fields_selection.convert_to_cache con
        _selection None)."""
        self.website.shop_default_sort = VELOCITY_ORDER
        self.assertEqual(self.website.shop_default_sort, VELOCITY_ORDER)

    def test_velocity_defaults_to_zero_not_null(self):
        """Sin 0.0 por defecto, 'sales_velocity desc' pondría los productos
        sin ventas PRIMEROS (PostgreSQL ordena NULLS FIRST en DESC)."""
        product = self.env['product.template'].create({'name': 'Test conv'})
        self.assertEqual(product.sales_velocity, 0.0)
        self.env.cr.execute(
            "SELECT sales_velocity FROM product_template WHERE id = %s",
            (product.id,))
        self.assertIsNotNone(self.env.cr.fetchone()[0])
