"""
Structured endpoints for tender monitoring system.
Provides comprehensive endpoint testing and management.
"""
import requests
import time
from typing import Dict, List, Optional
import logging
from ratelimit import limits, sleep_and_retry
import config_endpoints as config
import utils_licitacoes as utils

logger = logging.getLogger(__name__)

class EndpointTester:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ARTE-TenderMonitor/1.0',
            'Accept': 'application/json'
        })

    @sleep_and_retry
    @limits(calls=60, period=60)
    def _make_request(self, url: str, params: Optional[Dict] = None) -> Dict:
        """
        Make rate-limited API request
        """
        try:
            response = self.session.get(
                url,
                params=params,
                timeout=(config.TIMEOUTS["connect"], config.TIMEOUTS["read"])
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {url} - {str(e)}")
            return {}

    def test_pncp_endpoints(self, uasg: str, edital: str) -> Dict:
        """
        Test PNCP API endpoints
        """
        results = {}
        endpoints = config.ENDPOINTS["pncp"]
        
        for endpoint_name, url in endpoints.items():
            response = self._make_request(url, {
                "uasg": uasg,
                "numero": edital,
                "cnpjFornecedor": config.COMPANY_CNPJ
            })
            
            if utils.validate_api_response(response, "pncp"):
                results[endpoint_name] = {
                    "status": "working",
                    "url": url,
                    "sample_data": response
                }
            else:
                results[endpoint_name] = {
                    "status": "error",
                    "url": url
                }
        
        return results

    def test_comprasgov_endpoints(self, uasg: str, edital: str) -> Dict:
        """
        Test ComprasGov API endpoints
        """
        results = {}
        endpoints = config.ENDPOINTS["comprasgov"]
        
        for endpoint_name, url in endpoints.items():
            response = self._make_request(url, {
                "co_uasg": uasg,
                "nu_pregao": edital
            })
            
            if utils.validate_api_response(response, "comprasgov"):
                results[endpoint_name] = {
                    "status": "working",
                    "url": url,
                    "sample_data": response
                }
            else:
                results[endpoint_name] = {
                    "status": "error",
                    "url": url
                }
        
        return results

    def test_transparencia_endpoints(self, uasg: str, edital: str) -> Dict:
        """
        Test Portal da Transparência API endpoints
        """
        results = {}
        endpoints = config.ENDPOINTS["transparencia"]
        
        for endpoint_name, url in endpoints.items():
            response = self._make_request(url, {
                "uasg": uasg,
                "numeroLicitacao": edital
            })
            
            if utils.validate_api_response(response, "transparencia"):
                results[endpoint_name] = {
                    "status": "working",
                    "url": url,
                    "sample_data": response
                }
            else:
                results[endpoint_name] = {
                    "status": "error",
                    "url": url
                }
        
        return results

    def test_all_endpoints(self, uasg: str, edital: str) -> Dict:
        """
        Test all available endpoints for a tender
        """
        results = {
            "pncp": self.test_pncp_endpoints(uasg, edital),
            "comprasgov": self.test_comprasgov_endpoints(uasg, edital),
            "transparencia": self.test_transparencia_endpoints(uasg, edital)
        }
        
        return results

def get_working_endpoints(test_results: Dict) -> Dict:
    """
    Extract working endpoints from test results
    """
    working_endpoints = {}
    
    for api_name, api_results in test_results.items():
        working = {
            name: data
            for name, data in api_results.items()
            if data["status"] == "working"
        }
        if working:
            working_endpoints[api_name] = working
    
    return working_endpoints
