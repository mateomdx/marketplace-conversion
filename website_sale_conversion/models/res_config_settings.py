# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    mkt_conv_sort_by_velocity = fields.Boolean(
        related='website_id.mkt_conv_sort_by_velocity',
        readonly=False,
    )
