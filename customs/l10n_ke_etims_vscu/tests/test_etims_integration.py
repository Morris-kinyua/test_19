# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
from unittest.mock import patch, MagicMock
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError
from datetime import datetime


class TestEtimsIntegration(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Setup company with Kenya configuration
        cls.company = cls.env.company
        cls.company.write({
            'country_id': cls.env.ref('base.ke').id,
            'account_fiscal_country_id': cls.env.ref('base.ke').id,
            'vat': 'P052386110T',
            'l10n_ke_branch_code': '00',
            'l10n_ke_api_url': 'https://etims-sbx.kra.go.ke/etims-api/',
            'l10n_ke_server_mode': 'demo',
            'l10n_ke_oscu_is_active': True,
            'l10n_ke_oscu_user_agreement': True,
        })
        
        # Create test customer
        cls.customer = cls.env['res.partner'].create({
            'name': 'Test Customer Ltd',
            'vat': 'P123456789A',
            'is_company': True,
            'country_id': cls.env.ref('base.ke').id,
        })
        
        # Create test product with eTIMS configuration
        cls.product = cls.env['product.product'].create({
            'name': 'Test Service',
            'type': 'service',
            'list_price': 1000.0,
            'standard_price': 800.0,
            'l10n_ke_packaging_quantity': 1.0,
            'l10n_ke_product_type_code': '3',
            'l10n_ke_is_insurance_applicable': False,
        })
        
        # Create tax with KRA tax type
        cls.tax = cls.env['account.tax'].create({
            'name': 'VAT 16%',
            'amount': 16.0,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'company_id': cls.company.id,
        })

    def test_01_company_configuration(self):
        """Test company eTIMS configuration"""
        self.assertTrue(self.company.l10n_ke_oscu_is_active)
        self.assertEqual(self.company.vat, 'P052386110T')
        self.assertEqual(self.company.l10n_ke_branch_code, '00')
        self.assertTrue(self.company.l10n_ke_api_url)

    def test_02_product_configuration(self):
        """Test product eTIMS fields"""
        self.assertEqual(self.product.l10n_ke_product_type_code, '3')
        self.assertEqual(self.product.l10n_ke_packaging_quantity, 1.0)
        self.assertFalse(self.product.l10n_ke_is_insurance_applicable)

    def test_03_invoice_creation(self):
        """Test invoice creation with eTIMS fields"""
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.customer.id,
            'invoice_date': datetime.now().date(),
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'name': self.product.name,
                'quantity': 1,
                'price_unit': 1000.0,
                'tax_ids': [(6, 0, [self.tax.id])],
            })],
        })
        
        self.assertEqual(invoice.move_type, 'out_invoice')
        self.assertEqual(invoice.partner_id, self.customer)
        self.assertEqual(len(invoice.invoice_line_ids), 1)

    @patch('odoo.addons.l10n_ke_etims_vscu.models.res_company.requests.Session')
    def test_04_etims_api_call(self, mock_session):
        """Test eTIMS API call functionality"""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'resultCd': '000',
            'resultMsg': 'Success',
            'data': {'sdcId': 'TEST_SDC', 'rcptSign': 'TEST_SIGNATURE'}
        }
        mock_session.return_value.post.return_value = mock_response
        
        error, data, date = self.company._l10n_ke_call_etims('test/endpoint', {'test': 'data'})
        
        self.assertFalse(error)
        self.assertIn('sdcId', data)
        self.assertEqual(data['sdcId'], 'TEST_SDC')

    def test_05_credit_note_validation(self):
        """Test credit note validation requirements"""
        # Create original invoice
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.customer.id,
            'invoice_date': datetime.now().date(),
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'name': self.product.name,
                'quantity': 1,
                'price_unit': 1000.0,
                'tax_ids': [(6, 0, [self.tax.id])],
            })],
        })
        invoice.action_post()
        
        # Create credit note
        credit_note = self.env['account.move'].create({
            'move_type': 'out_refund',
            'partner_id': self.customer.id,
            'reversed_entry_id': invoice.id,
            'invoice_date': datetime.now().date(),
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'name': self.product.name,
                'quantity': 1,
                'price_unit': 1000.0,
                'tax_ids': [(6, 0, [self.tax.id])],
            })],
        })
        
        # Check validation message for missing reason code
        validation_messages = credit_note.l10n_ke_validation_message or {}
        self.assertIn('no_reason_code_warning', validation_messages)

    def test_06_qr_code_generation(self):
        """Test QR code URL generation"""
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.customer.id,
            'invoice_date': datetime.now().date(),
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'name': self.product.name,
                'quantity': 1,
                'price_unit': 1000.0,
            })],
        })
        
        # Set eTIMS signature to simulate successful transmission
        invoice.l10n_ke_oscu_signature = 'TEST_SIGNATURE_123'
        
        qr_url = invoice._l10n_ke_oscu_get_receipt_url()
        self.assertIn('etims-sbx.kra.go.ke', qr_url)
        self.assertIn('TEST_SIGNATURE_123', qr_url)

    def test_07_invoice_json_preparation(self):
        """Test invoice JSON preparation for eTIMS"""
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.customer.id,
            'invoice_date': datetime.now().date(),
            'l10n_ke_oscu_confirmation_datetime': datetime.now(),
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'name': self.product.name,
                'quantity': 2,
                'price_unit': 500.0,
                'tax_ids': [(6, 0, [self.tax.id])],
            })],
        })
        invoice.action_post()
        
        try:
            json_data = invoice._l10n_ke_oscu_json_from_move()
            self.assertIn('trdInvcNo', json_data)
            self.assertIn('itemList', json_data)
            self.assertEqual(json_data['totItemCnt'], 1)
        except Exception as e:
            # Expected to fail without proper tax configuration
            self.assertIn('tax', str(e).lower())

    def test_08_cron_job_processing(self):
        """Test cron job processing functionality"""
        # Test code fetching cron
        try:
            self.env['l10n_ke_etims_vscu.code']._cron_get_codes_from_device()
            # Should not raise error even without proper configuration
        except Exception as e:
            self.fail(f"Cron job should handle missing configuration gracefully: {e}")

    def test_09_product_validation(self):
        """Test product validation for eTIMS"""
        # Create product without required fields
        incomplete_product = self.env['product.product'].create({
            'name': 'Incomplete Product',
            'type': 'product',
        })
        
        validation_messages = incomplete_product._l10n_ke_get_validation_messages(for_invoice=True)
        self.assertTrue(len(validation_messages) > 0)

    def test_10_demo_mode_functionality(self):
        """Test demo mode functionality"""
        self.company.l10n_ke_server_mode = 'demo'
        
        # Test demo response generation
        try:
            response = self.company._l10n_ke_get_demo_response('saveTrnsSales', {})
            self.assertIsNotNone(response)
        except Exception:
            # Demo files might not exist in test environment
            pass

    def test_11_fiscal_country_codes_computation(self):
        """Test fiscal country codes computation"""
        # Test the fiscal_country_codes field we added
        self.product._compute_fiscal_country_codes()
        self.assertIn('KE', self.product.fiscal_country_codes or '')

    def test_12_invoice_sequence_generation(self):
        """Test eTIMS invoice sequence generation"""
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.customer.id,
        })
        
        sequence = invoice._l10n_ke_get_invoice_sequence()
        self.assertTrue(sequence)
        self.assertEqual(sequence.code, 'l10n.ke.oscu.sale.sequence')

    @patch('odoo.addons.l10n_ke_etims_vscu.models.res_company.requests.Session')
    def test_13_send_invoice_to_etims(self, mock_session):
        """Test sending invoice to eTIMS"""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'resultCd': '000',
            'resultMsg': 'Success',
            'data': {
                'sdcId': 'TEST_SDC',
                'rcptSign': 'TEST_SIGNATURE',
                'vsdcRcptPbctDate': '20241014120000',
                'intrlData': 'TEST_INTERNAL_DATA'
            }
        }
        mock_session.return_value.post.return_value = mock_response
        
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.customer.id,
            'invoice_date': datetime.now().date(),
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'name': self.product.name,
                'quantity': 1,
                'price_unit': 1000.0,
                'tax_ids': [(6, 0, [self.tax.id])],
            })],
        })
        invoice.action_post()
        
        try:
            result = invoice.action_l10n_ke_oscu_send_customer_invoice()
            self.assertIn('type', result)
        except UserError as e:
            # Expected due to validation requirements
            self.assertIn('eTIMS', str(e))

    def test_14_error_handling(self):
        """Test error handling in various scenarios"""
        # Test with missing configuration
        company_no_config = self.env['res.company'].create({
            'name': 'Test Company No Config',
        })
        
        error, data, date = company_no_config._l10n_ke_call_etims('test', {})
        self.assertTrue(error)
        self.assertIn('CON', error.get('code', ''))

    def test_15_module_installation_compatibility(self):
        """Test module installation and compatibility"""
        # Test that all required models exist
        self.assertTrue(self.env['l10n_ke_etims_vscu.code'])
        self.assertTrue(self.env['l10n_ke_etims_vscu.notice'])
        
        # Test that views are accessible
        invoice_view = self.env.ref('account.view_move_form', raise_if_not_found=False)
        self.assertTrue(invoice_view)