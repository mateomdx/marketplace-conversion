# -*- coding: utf-8 -*-
import logging
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


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

    # ── Sincronización desde PEGASUS ────────────────────────────────────
    # Método PÚBLICO a propósito: es el único punto de escritura y se
    # invoca desde la red local por POST /json/2/product.template/
    # apply_pegasus_velocity con una API key (auth='bearer'). En la v19
    # /xmlrpc y /jsonrpc están deprecados (addons/rpc/controllers/
    # __init__.py: "scheduled for removal in Odoo 22").
    #
    # get_public_method() rechaza nombres con "_" inicial, classmethods,
    # staticmethods y lo decorado con @api.private
    # (odoo/service/model.py:45-71), así que la firma es la que es.

    #: Si la extracción trae menos de este porcentaje de las filas de la
    #: corrida anterior, se asume extracción parcial y NO se escribe nada.
    VELOCITY_SANITY_RATIO = 0.5

    @api.model
    def apply_pegasus_velocity(self, rows, window_days=30):
        """Vuelca la velocidad de venta de PEGASUS sobre el catálogo.

        :param rows: lista de pares ``[CODIGO, UNIDADES]``. CODIGO es el
            mismo valor que ``product.product.default_code``.
        :param window_days: ventana en días que representa ``rows``, solo
            informativa.
        :return: dict con el reporte de la corrida.

        Todo o nada: si la extracción viene vacía o sospechosamente corta,
        se levanta UserError y NO se toca ningún valor — el dato anterior
        sobrevive, que es lo que pide el requerimiento. Nunca se pone el
        catálogo entero en 0 por un fallo de la fuente.
        """
        Param = self.env['ir.config_parameter'].sudo()

        if not rows:
            raise UserError(_(
                "PEGASUS no devolvió ninguna fila. No se modificó ningún "
                "valor de velocidad."))

        previous = int(Param.get_param('website_sale_conversion.velocity_rows', 0))
        if previous and len(rows) < previous * self.VELOCITY_SANITY_RATIO:
            raise UserError(_(
                "Extracción sospechosamente corta: %(now)s filas contra "
                "%(before)s de la corrida anterior. No se modificó ningún "
                "valor. Revisá la conexión con PEGASUS.",
                now=len(rows), before=previous))

        # CODIGO -> unidades. Se netean las notas de crédito (vienen en
        # negativo) y se pisa el piso en 0: un neto negativo ordena igual
        # que "no vendió", no por encima.
        units_by_code = defaultdict(float)
        for row in rows:
            code, units = row[0], row[1]
            if code is None:
                continue
            units_by_code[str(code).strip()] += float(units or 0.0)

        # El cruce va contra product.product: default_code vive ahí
        # (product/models/product_product.py:35). En product.template es un
        # compute stored que queda vacío si la plantilla tiene más de una
        # variante, así que cruzar a nivel plantilla perdería productos.
        variants = self.env['product.product'].sudo().search_fetch(
            [('default_code', 'in', list(units_by_code))],
            ['default_code', 'product_tmpl_id'],
        )
        # Suma a nivel plantilla: si mañana aparecen variantes, las ventas
        # de todas ellas alimentan la plantilla que ordena /shop.
        by_template = defaultdict(float)
        matched_codes = set()
        for variant in variants:
            code = variant.default_code.strip()
            matched_codes.add(code)
            by_template[variant.product_tmpl_id.id] += units_by_code[code]

        now = fields.Datetime.now()
        Template = self.sudo()
        published = Template.search([('is_published', '=', True)])

        # Escritura agrupada por valor: un write por valor distinto en vez
        # de uno por producto.
        ids_by_value = defaultdict(list)
        for tmpl_id, units in by_template.items():
            ids_by_value[max(units, 0.0)].append(tmpl_id)

        touched_ids = set()
        for value, tmpl_ids in ids_by_value.items():
            Template.browse(tmpl_ids).write({
                'sales_velocity': value,
                'sales_velocity_date': now,
                'sales_velocity_matched': True,
            })
            touched_ids.update(tmpl_ids)

        # Publicados que PEGASUS no mencionó: vendieron 0 en la ventana.
        # Es un dato válido, no un fallo — la extracción fue buena.
        stale = published.filtered(lambda t: t.id not in touched_ids)
        if stale:
            stale.write({
                'sales_velocity': 0.0,
                'sales_velocity_date': now,
                'sales_velocity_matched': False,
            })

        unmatched_pegasus = sorted(set(units_by_code) - matched_codes)
        report = {
            'window_days': window_days,
            'synced_at': fields.Datetime.to_string(now),
            'rows_received': len(rows),
            'codes_received': len(units_by_code),
            'codes_matched': len(matched_codes),
            'templates_updated': len(touched_ids),
            'published_without_sales': len(stale),
            # No coincidentes en ambas direcciones, como pide el brief.
            'unmatched_pegasus': unmatched_pegasus[:500],
            'unmatched_pegasus_total': len(unmatched_pegasus),
            'unmatched_odoo': stale.mapped('default_code')[:500],
            'unmatched_odoo_total': len(stale),
        }
        Param.set_param('website_sale_conversion.velocity_rows', len(rows))
        Param.set_param('website_sale_conversion.velocity_last_sync',
                        report['synced_at'])
        _logger.info(
            "PEGASUS velocity: %s códigos recibidos, %s cruzados, "
            "%s plantillas actualizadas, %s publicadas sin ventas, "
            "%s códigos de PEGASUS sin producto en Odoo.",
            report['codes_received'], report['codes_matched'],
            report['templates_updated'], report['published_without_sales'],
            report['unmatched_pegasus_total'])
        return report
