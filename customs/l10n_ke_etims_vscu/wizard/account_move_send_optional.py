# Part of Odoo. See LICENSE file for full copyright and licensing details.
# Optional integration with account_move_send wizard
# This file is only loaded if account_move_send module is available

from odoo import api, fields, models, _
from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)


class AccountMoveSendWizard(models.TransientModel):
    _name = 'account.move.send.wizard'
    _inherit = 'account.move.send.wizard'

    l10n_ke_show_checkbox_oscu = fields.Boolean(compute="_compute_l10n_ke_show_checkbox_oscu")
    l10n_ke_checkbox_oscu = fields.Boolean(
        string='Send to eTIMS',
        compute='_compute_l10n_ke_checkbox_oscu',
        store=True,
        readonly=False,
        help='Send the invoice to the KRA via eTIMS',
    )

    @api.depends('move_id')
    def _compute_l10n_ke_show_checkbox_oscu(self):
        for wizard in self:
            # Show checkbox if:
            # 1. Move is a customer invoice/credit note
            # 2. Company has eTIMS active
            # 3. Invoice has products with KRA item codes
            # 4. Not already sent to eTIMS
            wizard.l10n_ke_show_checkbox_oscu = any(
                move.move_type in ('out_invoice', 'out_refund') and
                move.company_id.l10n_ke_oscu_is_active and
                move.l10n_ke_has_kra_products and
                not move.l10n_ke_oscu_receipt_number
                for move in wizard.move_id
            )

    @api.depends('move_id')
    def _compute_l10n_ke_checkbox_oscu(self):
        for wizard in self:
            # Default to checked if conditions are met
            wizard.l10n_ke_checkbox_oscu = wizard.l10n_ke_show_checkbox_oscu

    def _get_wizard_values(self):
        # EXTENDS 'account_move_send'
        values = super()._get_wizard_values()
        values['l10n_ke_oscu'] = self.l10n_ke_checkbox_oscu
        return values

    @api.model
    def _call_web_service_before_invoice_pdf_render(self, invoices_data):
        # EXTENDS 'account_move_send'
        super()._call_web_service_before_invoice_pdf_render(invoices_data)

        for invoice, invoice_data in invoices_data.items():
            if not invoice_data.get('l10n_ke_oscu'):
                continue

            try:
                # Validate before sending
                validation_messages = (invoice.l10n_ke_validation_message or {}).values()
                if (blocking := [msg for msg in validation_messages if msg.get('blocking')]):
                    error_msg = "\\n".join(msg['message'] for msg in blocking)
                    invoice_data['error'] = {
                        'error_title': _("eTIMS Validation Error"),
                        'errors': [error_msg],
                    }
                    continue

                # Send to eTIMS
                invoice._l10n_ke_oscu_send_customer_invoice()
                
                # Success notification
                self.env.user.notify_success(
                    message=_("Invoice successfully sent to KRA eTIMS"),
                    title=_("eTIMS Success"),
                )

            except Exception as e:
                _logger.exception("eTIMS transmission error")
                invoice_data['error'] = {
                    'error_title': _("eTIMS Transmission Error"),
                    'errors': [str(e)],
                }
                self.env.user.notify_warning(
                    message=str(e),
                    title=_("eTIMS Error"),
                    sticky=True
                )