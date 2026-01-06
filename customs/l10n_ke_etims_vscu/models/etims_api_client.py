# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import logging
import requests
import hashlib
import hmac
import base64
from urllib.parse import urljoin
from requests.exceptions import Timeout, RequestException
from json.decoder import JSONDecodeError
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict

from odoo import api, fields, models, _, tools

_logger = logging.getLogger(__name__)

# KRA eTIMS API Base URLs
ETIMS_API_URLS = {
    'prod': 'https://etims.kra.go.ke/etims/api/',
    'test': 'https://etims-test.kra.go.ke/etims/api/',
    'demo': 'http://localhost:8080/etims/api/',
}

# eTIMS API Endpoints
ETIMS_ENDPOINTS = {
    'initialize': 'initOscu',
    'save_sales': 'saveTrnsSalesOsdc',
    'save_purchase': 'insertTrnsPurchase',
    'get_invoice': 'selectInvoiceDetails',
    'get_purchases': 'selectTrnsPurchaseSalesList',
    'save_item': 'saveItem',
    'get_items': 'selectItemList',
    'save_customer': 'saveBhfCustomer',
    'get_customer': 'selectBhfCustomer',
    'get_code_list': 'selectCodeList',
    'get_branches': 'selectBhfList',
}


class EtimsCrypto:
    """Handles cryptographic operations for eTIMS API communication."""
    
    @staticmethod
    def sign_request(data, cmc_key):
        """
        Sign API request using HMAC-SHA256.
        
        :param dict data: The request data to sign
        :param str cmc_key: The CMC key for signing
        :return: Base64 encoded signature
        """
        json_str = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        # Sign the JSON string with the CMC key
        signature = hmac.new(
            cmc_key.encode('utf-8'),
            json_str.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(signature).decode('utf-8')
    
    @staticmethod
    def verify_signature(data, signature, cmc_key):
        """
        Verify API response signature.
        
        :param dict data: The response data
        :param str signature: The signature to verify
        :param str cmc_key: The CMC key used for signing
        :return: Boolean indicating if signature is valid
        """
        try:
            expected_signature = EtimsCrypto.sign_request(data, cmc_key)
            return hmac.compare_digest(signature, expected_signature)
        except Exception:
            return False


class EtimsApiClient:
    """Client for communicating with KRA eTIMS API."""
    
    def __init__(self, company):
        """
        Initialize eTIMS API client.
        
        :param company: res.company record
        """
        self.company = company
        self.session = requests.Session()
        self._setup_headers()
    
    def _setup_headers(self):
        """Setup default headers for API requests."""
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })
    
    def _get_base_url(self):
        """Get the base URL for eTIMS API based on server mode."""
        mode = self.company.l10n_ke_server_mode or 'prod'
        return ETIMS_API_URLS.get(mode, ETIMS_API_URLS['prod'])
    
    def _add_auth_headers(self, data):
        """
        Add authentication headers to request.
        
        :param dict data: The request payload
        """
        # KRA eTIMS uses header-based authentication
        cmc_key = self.company.sudo().l10n_ke_oscu_cmc_key or ''
        
        self.session.headers.update({
            'tin': self.company.vat or '',
            'bhfid': self.company.l10n_ke_branch_code or '00',
            'cmcKey': cmc_key,
        })
    
    def call(self, endpoint, data, timeout=120):
        """
        Make a request to eTIMS API.
        
        :param str endpoint: The API endpoint to call
        :param dict data: The request payload
        :param int timeout: Request timeout in seconds
        :return: Tuple of (success, response_data, error_message)
        """
        if self.company.l10n_ke_server_mode == 'demo':
            return self._get_demo_response(endpoint, data)
        
        self._add_auth_headers(data)
        url = urljoin(self._get_base_url(), endpoint)
        
        _logger.info(f"eTIMS API Call: {endpoint} for {self.company.name}")
        
        try:
            response = self.session.post(
                url,
                json=data,
                timeout=timeout,
                verify=True
            )
            
            _logger.debug(f"eTIMS Response Status: {response.status_code}")
            
            # Handle response
            if response.status_code == 200:
                try:
                    result = response.json()
                    
                    # Check for success
                    result_code = result.get('resultCd', '999')
                    if result_code == '000':
                        _logger.info(f"eTIMS Call Successful: {endpoint}")
                        return True, result.get('data', {}), None
                    else:
                        error_msg = result.get('resultMsg', 'Unknown error')
                        _logger.warning(f"eTIMS Error ({result_code}): {error_msg}")
                        return False, {}, {
                            'code': result_code,
                            'message': error_msg,
                            'timestamp': result.get('resultDt')
                        }
                except JSONDecodeError as e:
                    _logger.error(f"Failed to parse eTIMS response: {e}")
                    return False, {}, {
                        'code': 'JSON_ERROR',
                        'message': 'Invalid JSON response from eTIMS'
                    }
            else:
                _logger.error(f"eTIMS HTTP Error {response.status_code}: {response.text}")
                return False, {}, {
                    'code': str(response.status_code),
                    'message': f"HTTP {response.status_code}: {response.text[:200]}"
                }
        
        except Timeout:
            error_msg = _("KRA is currently unable to process your document. Please try again later.")
            _logger.warning(f"Timeout connecting to eTIMS: {url}")
            return False, {}, {
                'code': 'TIMEOUT',
                'message': error_msg
            }
        
        except RequestException as e:
            error_msg = _("Connection error: %s") % str(e)
            _logger.error(f"Connection error with eTIMS: {e}")
            return False, {}, {
                'code': 'CONNECTION_ERROR',
                'message': error_msg
            }
    
    def _get_demo_response(self, endpoint, content):
        """
        Get a mocked response for demo mode.
        
        :param str endpoint: The API endpoint
        :param dict content: The request payload
        :return: Tuple of (success, response_data, error)
        """
        # Demo mode always returns success for testing
        demo_responses = {
            'saveTrnsSalesOsdc': {
                'resultCd': '000',
                'resultMsg': 'Success',
                'resultDt': datetime.now().strftime('%Y%m%d%H%M%S'),
                'data': {
                    'invcNo': 1,
                    'curRcptNo': 1,
                    'rcptSign': 'DEMO_SIGNATURE_' + hashlib.md5(str(content).encode()).hexdigest(),
                    'sdcDateTime': datetime.now().strftime('%Y%m%d%H%M%S'),
                    'intrlData': base64.b64encode(json.dumps(content).encode()).decode()
                }
            },
            'insertTrnsPurchase': {
                'resultCd': '000',
                'resultMsg': 'Success',
                'resultDt': datetime.now().strftime('%Y%m%d%H%M%S'),
                'data': {'status': 'approved'}
            },
            'saveItem': {
                'resultCd': '000',
                'resultMsg': 'Success',
                'resultDt': datetime.now().strftime('%Y%m%d%H%M%S'),
                'data': {'itemCd': content.get('itemCd', 'DEMO_ITEM')}
            },
            'saveBhfCustomer': {
                'resultCd': '000',
                'resultMsg': 'Success',
                'resultDt': datetime.now().strftime('%Y%m%d%H%M%S'),
                'data': {'status': 'saved'}
            },
            'selectCodeList': {
                'resultCd': '000',
                'resultMsg': 'Success',
                'resultDt': datetime.now().strftime('%Y%m%d%H%M%S'),
                'data': {'codeList': []}
            },
        }
        
        response_data = demo_responses.get(endpoint, {
            'resultCd': '000',
            'resultMsg': 'Demo Success',
            'resultDt': datetime.now().strftime('%Y%m%d%H%M%S'),
            'data': {}
        })
        
        return True, response_data.get('data', {}), None


class EtimsIntegration(models.AbstractModel):
    """Mixin class providing eTIMS integration methods."""
    _name = 'etims.integration'
    _description = 'eTIMS Integration Helper'
    
    @staticmethod
    def format_etims_datetime(dt):
        """Format a UTC datetime as expected by eTIMS."""
        if not dt:
            return datetime.now().replace(tzinfo=ZoneInfo('UTC')).astimezone(
                ZoneInfo('Africa/Nairobi')
            ).strftime('%Y%m%d%H%M%S')
        return dt.replace(tzinfo=ZoneInfo('UTC')).astimezone(
            ZoneInfo('Africa/Nairobi')
        ).strftime('%Y%m%d%H%M%S')
    
    @staticmethod
    def parse_etims_datetime(dt_str):
        """Parse a datetime string received from eTIMS into a UTC datetime."""
        if not dt_str:
            return None
        return datetime.strptime(dt_str, '%Y%m%d%H%M%S').replace(
            tzinfo=ZoneInfo('Africa/Nairobi')
        ).astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
