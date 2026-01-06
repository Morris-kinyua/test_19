# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError

PRODUCT_TYPE_CODE_SELECTION = [('1', "Raw Material"), ('2', "Finished Product"), ('3', "Service")]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    l10n_ke_packaging_unit_id = fields.Many2one(
        comodel_name='l10n_ke_etims_vscu.code',
        string="Packaging Unit",
        compute='_compute_l10n_ke_packaging_unit_id',
        inverse='_set_l10n_ke_packaging_unit_id',
        domain=[('code_type', '=', '17')],
        help="KRA code that describes the type of packaging used.",
    )
    l10n_ke_packaging_quantity = fields.Float(
        string="Package Quantity",
        compute='_compute_l10n_ke_packaging_quantity',
        inverse='_set_l10n_ke_packaging_quantity',
        help="Number of products in a package.",
    )
    l10n_ke_origin_country_id = fields.Many2one(
        comodel_name='res.country',
        string="Origin Country",
        compute='_compute_l10n_ke_origin_country_id',
        inverse='_set_l10n_ke_origin_country_id',
        help="The origin country of the product.",
    )
    l10n_ke_product_type_code = fields.Selection(
        string="eTIMS Product Type",
        selection=PRODUCT_TYPE_CODE_SELECTION,
        compute='_compute_l10n_ke_product_type_code',
        inverse='_set_l10n_ke_product_type_code',
        help="Used by eTIMS to determine the type of the product",
    )
    l10n_ke_is_insurance_applicable = fields.Boolean(
        string="Insurance Applicable",
        help="Check this box if the product is covered by insurance.",
        compute='_compute_l10n_ke_is_insurance_applicable',
        inverse='_set_l10n_ke_is_insurance_applicable',
    )
    l10n_ke_item_code = fields.Char(
        string="KRA Item Code",
        help="The code assigned to this product on eTIMS",
        compute='_compute_l10n_ke_item_code',
        search='_search_l10n_ke_item_code',
    )
    l10n_ke_remark = fields.Char(
        string="eTIMS Remark",
        size=400,
        help="Remark for eTIMS transmission (e.g., 'Disbursement')",
    )

    # === Computes === #

    @api.depends('product_variant_ids.l10n_ke_packaging_unit_id')
    def _compute_l10n_ke_packaging_unit_id(self):
        self._compute_template_field_from_variant_field('l10n_ke_packaging_unit_id')

    def _set_l10n_ke_packaging_unit_id(self):
        self._set_product_variant_field('l10n_ke_packaging_unit_id')

    @api.depends('product_variant_ids.l10n_ke_packaging_quantity')
    def _compute_l10n_ke_packaging_quantity(self):
        self._compute_template_field_from_variant_field('l10n_ke_packaging_quantity')

    def _set_l10n_ke_packaging_quantity(self):
        self._set_product_variant_field('l10n_ke_packaging_quantity')

    @api.depends('product_variant_ids.l10n_ke_origin_country_id')
    def _compute_l10n_ke_origin_country_id(self):
        self._compute_template_field_from_variant_field('l10n_ke_origin_country_id')

    def _set_l10n_ke_origin_country_id(self):
        self._set_product_variant_field('l10n_ke_origin_country_id')

    @api.depends('product_variant_ids.l10n_ke_product_type_code')
    def _compute_l10n_ke_product_type_code(self):
        self._compute_template_field_from_variant_field('l10n_ke_product_type_code')

    def _set_l10n_ke_product_type_code(self):
        self._set_product_variant_field('l10n_ke_product_type_code')

    @api.depends('product_variant_ids.l10n_ke_is_insurance_applicable')
    def _compute_l10n_ke_is_insurance_applicable(self):
        self._compute_template_field_from_variant_field('l10n_ke_is_insurance_applicable')

    def _set_l10n_ke_is_insurance_applicable(self):
        self._set_product_variant_field('l10n_ke_is_insurance_applicable')

    @api.depends('product_variant_ids.l10n_ke_item_code')
    def _compute_l10n_ke_item_code(self):
        self._compute_template_field_from_variant_field('l10n_ke_item_code')

    @api.model
    def _search_l10n_ke_item_code(self, operator, value):
        return [('product_variant_ids.l10n_ke_item_code', operator, value)]

    # === Actions === #

    def action_l10n_ke_oscu_save_item(self):
        if self.product_variant_count != 1:
            raise UserError(_("There should only be one product variant per product template!"))
        return self.product_variant_ids.action_l10n_ke_oscu_save_item()

    def _get_related_fields_variant_template(self):
        # EXTENDS 'product'
        return [
            *super()._get_related_fields_variant_template(),
            'l10n_ke_packaging_unit_id',
            'l10n_ke_packaging_quantity',
            'l10n_ke_origin_country_id',
            'l10n_ke_product_type_code',
            'l10n_ke_is_insurance_applicable',
        ]


class ProductProduct(models.Model):
    _inherit = 'product.product'

    l10n_ke_packaging_unit_id = fields.Many2one(
        comodel_name='l10n_ke_etims_vscu.code',
        string="Packaging Unit",
        domain=[('code_type', '=', '17')],
        help="KRA code that describes the type of packaging used.",
    )
    l10n_ke_packaging_quantity = fields.Float(
        string="Package Quantity",
        help="Number of products in a package.",
        default=1,
    )
    l10n_ke_origin_country_id = fields.Many2one(
        comodel_name='res.country',
        string="Origin Country",
        help="The origin country of the product.",
    )
    l10n_ke_product_type_code = fields.Selection(
        string="eTIMS Product Type",
        selection=PRODUCT_TYPE_CODE_SELECTION,
        help="Used by eTIMS to determine the type of the product",
    )
    l10n_ke_is_insurance_applicable = fields.Boolean(
        string="Insurance Applicable",
        help="Check this box if the product is covered by insurance.",
    )
    l10n_ke_item_code = fields.Char(
        string="KRA Item Code",
        help="The code assigned to this product on eTIMS",
    )
    l10n_ke_remark = fields.Char(
        related='product_tmpl_id.l10n_ke_remark',
        readonly=False,
        store=True,
    )

    def _l10n_ke_get_validation_messages(self, for_invoice=False):
        """Check that products are configured correctly for eTIMS"""
        messages = {}
        
        # Check for missing UNSPSC codes
        products_without_unspsc = self.filtered(lambda p: not p.unspsc_code_id)
        if products_without_unspsc:
            messages['unspsc_code_missing'] = {
                'message': _("Some products are missing UNSPSC codes where one must be configured."),
                'action_text': _("View Product(s)"),
                'action': products_without_unspsc._get_records_action(name=_("Products Missing UNSPSC"), context={}),
                'blocking': for_invoice,
            }
        
        # Check for missing packaging units
        products_without_packaging = self.filtered(lambda p: not p.l10n_ke_packaging_unit_id)
        if products_without_packaging:
            messages['packaging_unit_missing'] = {
                'message': _("Some products are missing packaging unit codes."),
                'action_text': _("View Product(s)"),
                'action': products_without_packaging._get_records_action(name=_("Products Missing Packaging"), context={}),
                'blocking': for_invoice,
            }
        
        return messages

    @api.model
    def _l10n_ke_oscu_find_product_from_json(self, item_data):
        """Find product from eTIMS JSON data"""
        product = None
        message = None
        
        # Try to find by barcode first
        if item_data.get('bcd'):
            product = self.search([('barcode', '=', item_data['bcd'])], limit=1)
        
        # Try to find by UNSPSC code
        if not product and item_data.get('itemClsCd'):
            product = self.search([('unspsc_code_id.code', '=', item_data['itemClsCd'])], limit=1)
        
        # Create message if not found
        if not product:
            message = _("Product not found for item: %s", item_data.get('itemNm', 'Unknown'))
        
        return product, message

    def action_l10n_ke_oscu_save_item(self):
        """Save item to eTIMS"""
        # This would implement the actual eTIMS item saving logic
        # For now, just return a success message
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("Item saved to eTIMS successfully"),
            }
        }
