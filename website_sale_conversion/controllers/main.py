# -*- coding: utf-8 -*-
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale

from ..models.website import VELOCITY_ORDER


class WebsiteSaleConversion(WebsiteSale):

    def _get_search_order(self, post):
        """Usa 'Más vendidos' como orden por defecto si el sitio lo pide.

        Solo actúa cuando el visitante NO eligió un orden explícito: si hay
        ``?order=`` en la URL se respeta tal cual, así que los enlaces
        existentes y el SEO no cambian de comportamiento.
        """
        if post.get('order'):
            return super()._get_search_order(post)
        website = request.env['website'].get_current_website()
        if not website.mkt_conv_sort_by_velocity:
            return super()._get_search_order(post)
        # Mismo formato que el nativo: is_published primero e `id desc` al
        # final como desempate estable (paginación consistente con empates).
        return 'is_published desc, %s, id desc' % VELOCITY_ORDER
