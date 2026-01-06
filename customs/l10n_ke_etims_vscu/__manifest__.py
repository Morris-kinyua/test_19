# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Kenya eTIMS EDI Integration",
    'countries': ['ke'],
    'summary': """
            Kenya eTIMS Device EDI Integration for KRA VSCU
        """,
    'description': """
       This module integrates with the Kenyan VSCU eTIMS device for real-time
       tax compliance with Kenya Revenue Authority (KRA).
       
       Features:
       - Real-time invoice transmission to KRA
       - Automatic tax validation
       - VSCU device integration
       - Purchase confirmation
       - Credit note management
    """,
    'author': 'Code Kenya <dev@code.ke>',
    'category': 'Accounting/Localizations/EDI',
    'version': '19.0.1.0.0',
    'license': 'OPL-1',
    'depends': [
        'l10n_ke', 
        'product_unspsc',
        'account_edi',
        'account_move_send',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/l10n_ke_etims_vscu.code.csv',
        'data/ir_cron_data.xml',
        'data/ir_sequence_data.xml',
        'data/uom.uom.csv',
        'views/account_tax_views.xml',
        'views/product_views.xml',
        'views/account_move_views.xml',
        'views/account_move_send_views.xml',
        'views/report_invoice.xml',
        'views/res_company_views.xml',
        'views/res_config_settings_views.xml',
        'views/res_users_views.xml',
        'views/res_partner_views.xml',
        'views/uom_uom_views.xml',
        'views/l10n_ke_etims_vscu_code_views.xml',
        'views/l10n_ke_etims_vscu_notice_views.xml',
        'views/menuitems.xml',
        'wizard/account_move_reversal_view.xml',
        'wizard/account_move_send_views.xml',
    ],
    'demo': [
        'demo/demo_company.xml',
        'demo/demo_product.xml',
    ],
    'post_init_hook': '_post_init_hook',
    'auto_install': False,
    'installable': True,
    'application': False,
}
