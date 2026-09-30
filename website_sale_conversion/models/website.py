# -*- coding: utf-8 -*-
from odoo import _, fields, models

VELOCITY_ORDER = 'sales_velocity desc'


class Website(models.Model):
    _inherit = 'website'

    # Campo PROPIO del módulo. No se escribe `shop_default_sort` (que es de
    # website_sale) para no violar la restricción 6: el default se resuelve
    # en el controlador, no pisando datos ajenos.
    mkt_conv_sort_by_velocity = fields.Boolean(
        string="Ordenar la tienda por más vendidos",
        default=False,
        help="Cuando está activo, /shop usa 'Más vendidos' como orden por "
             "defecto. El visitante puede elegir cualquier otra opción y se "
             "respeta. No modifica 'Destacado' ni website_sequence.",
    )

    def _get_product_sort_mapping(self):
        """Antepone 'Más vendidos' conservando TODAS las opciones nativas.

        En website_sale el método original es un ``@staticmethod``, pero el
        campo Selection lo resuelve con ``determine(selection, env[model])``
        (odoo/orm/fields_selection.py:199-220), es decir POR NOMBRE sobre el
        recordset — así que este override se toma igual. ``super()`` sobre un
        staticmethod se invoca sin argumentos y funciona.
        """
        mapping = list(super()._get_product_sort_mapping())
        return [(VELOCITY_ORDER, _("Más vendidos"))] + mapping

    # ── R4: pills de subcategorías sobre la grilla ───────────────────────
    PILL_LIMIT = 6

    def _mkt_conv_pill_categories(self, category=None):
        """Subcategorías a mostrar como pills sobre la grilla de /shop.

        Dentro de una categoría: sus hijas directas. En /shop sin categoría:
        las raíces. Se acota a las que tienen algún producto publicado
        dentro del dominio de la tienda, para no ofrecer una pill que lleva
        a una grilla vacía.
        """
        self.ensure_one()
        Category = self.env['product.public.category'].sudo()
        parent_id = category.id if category else False
        children = Category.search(
            [('parent_id', '=', parent_id)], order='sequence, name',
        )
        if not children:
            return []
        Product = self.env['product.template'].sudo()
        keep_ids = []
        for child in children:
            if len(keep_ids) >= self.PILL_LIMIT:
                break
            has_product = Product.search_count(
                self.sale_product_domain() + [
                    ('website_published', '=', True),
                    ('public_categ_ids', 'child_of', child.id),
                ], limit=1,
            )
            if has_product:
                keep_ids.append(child.id)
        # Se devuelven dicts con la URL ya resuelta: `slug` no está expuesto
        # como global de QWeb en la v19, el helper es ir.http._slug().
        slug = self.env['ir.http']._slug
        return [
            {'name': c.name, 'url': '/shop/category/%s' % slug(c)}
            for c in Category.browse(keep_ids)
        ]
