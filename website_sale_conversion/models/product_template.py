# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # R1 — velocidad de venta traída de PEGASUS (fuente de verdad).
    #
    # default=0.0 NO es cosmético: `_get_search_order` arma
    # "is_published desc, sales_velocity desc, id desc" y en PostgreSQL
    # DESC ordena NULLS FIRST. Con NULLs, los productos SIN ventas
    # quedarían PRIMEROS — exactamente lo contrario de lo pedido. Con 0.0
    # como piso no hay NULLs y el desempate lo cierra `id desc`.
    sales_velocity = fields.Float(
        string="Unidades vendidas (PEGASUS)",
        default=0.0,
        index=True,
        readonly=True,
        copy=False,
        help="Cantidad vendida en la ventana configurada según PEGASUS, "
             "cruzada por referencia interna (default_code = CODIGO). "
             "La escribe únicamente el proceso de sincronización.",
    )
    sales_velocity_date = fields.Datetime(
        string="Última sincronización de ventas",
        readonly=True,
        copy=False,
    )
    sales_velocity_matched = fields.Boolean(
        string="Encontrado en PEGASUS",
        default=False,
        readonly=True,
        copy=False,
        help="False = la referencia interna no apareció en la última "
             "extracción de PEGASUS. Distingue 'sin ventas' de 'sin cruce'.",
    )
