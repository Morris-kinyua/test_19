# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)



class AccountMoveSendWizard(models.TransientModel):
    _inherit = 'account.move.send.wizard'

    l10n_ke_show_checkbox_oscu = fields.Boolean(compute="_compute_l10n_ke_show_checkbox_oscu")
    l10n_ke_checkbox_oscu = fields.Boolean(
        string='Send to eTIMS',
        compute='_compute_l10n_ke_checkbox_oscu',
        store=True,
        readonly=False,
        help='Send the invoice to the KRA',
    )

    @api.depends('move_id')
    def _compute_l10n_ke_show_checkbox_oscu(self):
        for wizard in self:
            wizard.l10n_ke_show_checkbox_oscu = any(
                not move.l10n_ke_oscu_receipt_number for move in wizard.move_id)

    @api.depends('move_id')
    def _compute_l10n_ke_checkbox_oscu(self):
        for wizard in self:
            wizard.l10n_ke_checkbox_oscu = not any(
                move.l10n_ke_oscu_receipt_number for move in wizard.move_id)

    def _get_wizard_values(self):
        # EXTENDS 'account'
        values = super()._get_wizard_values()
        values['l10n_ke_oscu'] = self.l10n_ke_checkbox_oscu
        return values

    # -------------------------------------------------------------------------
    # BUSINESS ACTIONS
    # -------------------------------------------------------------------------

    def _send_invoice_to_etims(self, invoice):
        """New method to encapsulate eTIMS sending logic"""
        try:
            validation_messages = (invoice.l10n_ke_validation_message or {}).values()
            if (blocking := [msg for msg in validation_messages if msg.get('blocking')]):
                return {
                    'success': False,
                    'error': {
                        'title': _("Validation Error"),
                        'message': "\n".join(msg['message'] for msg in blocking)
                    }
                }

            invoice._l10n_ke_oscu_send_customer_invoice()
            return {'success': True}
            
        except Exception as e:
            _logger.exception("eTIMS transmission error")
            return {
                'success': False,
                'error': {
                    'title': _("System Error"),
                    'message': str(e)
                }
            }

    @api.model
    def _call_web_service_before_invoice_pdf_render(self, invoices_data):
        # EXTENDS 'account'
        super()._call_web_service_before_invoice_pdf_render(invoices_data)

        for invoice, invoice_data in invoices_data.items():
            if not invoice_data.get('l10n_ke_oscu'):
                continue

            result = self._send_invoice_to_etims(invoice)
            
            if not result['success']:
                invoice_data['error'] = {
                    'error_title': result['error']['title'],
                    'errors': [result['error']['message']],
                }
                self.env.user.notify_warning(
                    message=result['error']['message'],
                    title=result['error']['title'],
                    sticky=True
                )
                continue

            self.env.user.notify_success(
                message=_("Invoice successfully sent to KRA eTIMS"),
                title=_("Success"),
            )

            # Commit after successful transmission
            if self._can_commit():
                self._cr.commit()
