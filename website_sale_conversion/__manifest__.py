# -*- coding: utf-8 -*-
{
    'name': "Website Sale Conversion",
    'summary': "Orden por más vendidos (PEGASUS), sidebar compacto y sticky, "
               "megamenú de marcas compacto y pills de subcategorías en /shop.",
    'version': '19.0.1.0.0',
    'category': 'Website/eCommerce',
    'license': 'LGPL-3',
    'author': 'Marketplace SA',
    # website_market_v1 es una dependencia REAL: R4 ajusta el riel de marcas
    # de SU megamenú (.o_mkt_brands_rail) y el orden de carga de assets
    # depende del grafo de dependencias.
    'depends': ['website_sale', 'website_market_v1'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/shop_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'website_sale_conversion/static/src/scss/shop.scss',
            'website_sale_conversion/static/src/scss/megamenu.scss',
        ],
    },
    'installable': True,
    'application': False,
}
