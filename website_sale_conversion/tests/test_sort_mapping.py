# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
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


@tagged('post_install', '-at_install')
class TestPegasusVelocity(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Template = self.env['product.template']
        self.tmpl = self.Template.create({
            'name': 'Conv sync A', 'is_published': True, 'default_code': 'CONV-A'})
        self.other = self.Template.create({
            'name': 'Conv sync B', 'is_published': True, 'default_code': 'CONV-B'})

    def _apply(self, rows, **kw):
        return self.Template.apply_pegasus_velocity(rows, **kw)

    def test_matches_by_default_code_and_reports(self):
        report = self._apply([['CONV-A', 12], ['NO-EXISTE', 5]])
        self.assertEqual(self.tmpl.sales_velocity, 12.0)
        self.assertTrue(self.tmpl.sales_velocity_matched)
        self.assertIn('NO-EXISTE', report['unmatched_pegasus'])

    def test_published_without_sales_go_to_zero_not_null(self):
        """Sin ventas es 0 y matched=False: distingue 'no vendió' de
        'no cruzó'. Nunca NULL, o el orden DESC los pondría primeros."""
        self._apply([['CONV-A', 12]])
        self.assertEqual(self.other.sales_velocity, 0.0)
        self.assertFalse(self.other.sales_velocity_matched)

    def test_credit_notes_never_push_below_zero(self):
        """Una nota de crédito puede dejar el neto negativo; se pisa en 0
        para que ordene como 'no vendió' y no por debajo."""
        self._apply([['CONV-A', 5], ['CONV-A', -40]])
        self.assertEqual(self.tmpl.sales_velocity, 0.0)

    def test_aggregates_repeated_codes(self):
        self._apply([['CONV-A', 5], ['CONV-A', 7]])
        self.assertEqual(self.tmpl.sales_velocity, 12.0)

    def test_empty_extraction_changes_nothing(self):
        self._apply([['CONV-A', 30]])
        with self.assertRaises(UserError):
            self._apply([])
        self.assertEqual(self.tmpl.sales_velocity, 30.0,
                         "una extracción fallida no debe pisar el dato bueno")

    def test_short_extraction_is_rejected(self):
        """Corte de cordura: una extracción parcial no puede poner el
        catálogo en 0."""
        self._apply([['CONV-A', 1], ['CONV-B', 1]] * 50)
        before = self.tmpl.sales_velocity
        with self.assertRaises(UserError):
            self._apply([['CONV-A', 1]])
        self.assertEqual(self.tmpl.sales_velocity, before)

    def test_method_is_remotely_callable(self):
        """La API JSON-2 solo expone métodos públicos
        (odoo/service/model.py:45-71). Si alguien le pone guión bajo al
        nombre, el script deja de funcionar en silencio."""
        from odoo.service.model import get_public_method
        self.assertTrue(get_public_method(self.Template, 'apply_pegasus_velocity'))
