"""
Unified API interface for government procurement systems.
Consolidates best practices from existing API scripts.
"""
import requests
from typing import Dict, List, Optional, Union
import logging
from datetime import datetime
from abc import ABC, abstractmethod
from ratelimit import limits, sleep_and_retry
import backoff

import config_endpoints as config
import utils_licitacoes as utils

logger = logging.getLogger(__name__)

class BaseAPIClient(ABC):
    """
    Abstract base class for API clients
    """
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ARTE-TenderMonitor/1.0',
            'Accept': 'application/json'
        })

    @abstractmethod
    def get_tender_info(self, uasg: str, edital: str) -> Dict:
        pass

    @abstractmethod
    def get_tender_results(self, uasg: str, edital: str) -> Dict:
        pass

    @backoff.on_exception(
        backoff.expo,
        requests.exceptions.RequestException,
        max_tries=config.RETRY_CONFIG["max_retries"]
    )
    def _make_request(self, url: str, params: Optional[Dict] = None) -> Dict:
        """
        Make API request with retry logic
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
            raise

class PNCPClient(BaseAPIClient):
    """
    Client for PNCP API
    """
    @sleep_and_retry
    @limits(calls=config.RATE_LIMITS["pncp"]["requests_per_minute"], period=60)
    def get_tender_info(self, uasg: str, edital: str) -> Dict:
        url = config.ENDPOINTS["pncp"]["licitacoes"]
        params = {
            "uasg": uasg,
            "numero": edital
        }
        return self._make_request(url, params)

    @sleep_and_retry
    @limits(calls=config.RATE_LIMITS["pncp"]["requests_per_minute"], period=60)
    def get_tender_results(self, uasg: str, edital: str) -> Dict:
        url = config.ENDPOINTS["pncp"]["resultados"]
        params = {
            "uasg": uasg,
            "numero": edital,
            "cnpjFornecedor": config.COMPANY_CNPJ
        }
        return self._make_request(url, params)

class ComprasGovClient(BaseAPIClient):
    """
    Client for ComprasGov API
    """
    @sleep_and_retry
    @limits(calls=config.RATE_LIMITS["comprasgov"]["requests_per_minute"], period=60)
    def get_tender_info(self, uasg: str, edital: str) -> Dict:
        url = config.ENDPOINTS["comprasgov"]["pregoes"]
        params = {
            "co_uasg": uasg,
            "nu_pregao": edital
        }
        return self._make_request(url, params)

    @sleep_and_retry
    @limits(calls=config.RATE_LIMITS["comprasgov"]["requests_per_minute"], period=60)
    def get_tender_results(self, uasg: str, edital: str) -> Dict:
        url = config.ENDPOINTS["comprasgov"]["itens"]
        params = {
            "co_uasg": uasg,
            "nu_pregao": edital
        }
        return self._make_request(url, params)

class TransparenciaClient(BaseAPIClient):
    """
    Client for Portal da Transparência API
    """
    @sleep_and_retry
    @limits(calls=config.RATE_LIMITS["transparencia"]["requests_per_minute"], period=60)
    def get_tender_info(self, uasg: str, edital: str) -> Dict:
        url = config.ENDPOINTS["transparencia"]["licitacoes"]
        params = {
            "uasg": uasg,
            "numeroLicitacao": edital
        }
        return self._make_request(url, params)

    @sleep_and_retry
    @limits(calls=config.RATE_LIMITS["transparencia"]["requests_per_minute"], period=60)
    def get_tender_results(self, uasg: str, edital: str) -> Dict:
        url = config.ENDPOINTS["transparencia"]["contratos"]
        params = {
            "uasg": uasg,
            "numeroLicitacao": edital
        }
        return self._make_request(url, params)

class UnifiedAPIClient:
    """
    Unified interface for all procurement APIs
    """
    def __init__(self):
        self.pncp = PNCPClient()
        self.comprasgov = ComprasGovClient()
        self.transparencia = TransparenciaClient()
        self.clients = [self.pncp, self.comprasgov, self.transparencia]

    def get_tender_status(self, uasg: str, edital: str) -> Dict:
        """
        Get tender status from all available APIs
        """
        results = {}
        errors = []

        for client in self.clients:
            try:
                info = client.get_tender_info(uasg, edital)
                results[client.__class__.__name__] = {
                    "info": info,
                    "results": client.get_tender_results(uasg, edital)
                }
            except Exception as e:
                errors.append({
                    "client": client.__class__.__name__,
                    "error": str(e)
                })

        return {
            "uasg": uasg,
            "edital": edital,
            "results": results,
            "errors": errors,
            "timestamp": datetime.now().isoformat()
        }

    def normalize_response(self, response: Dict) -> Dict:
        """
        Normalize API responses into consistent format
        """
        normalized = {
            "uasg": response["uasg"],
            "edital": response["edital"],
            "timestamp": response["timestamp"],
            "status": "Aguardando Disputa",
            "rank": None,
            "adjudicada": False,
            "source": None
        }

        for client_name, data in response["results"].items():
            if not data.get("results"):
                continue

            result = data["results"]
            if result.get("adjudicado"):
                normalized["adjudicada"] = True
                normalized["status"] = "Adjudicada" if result.get("vencedor") == "ARTE" else "Perdida"
                normalized["source"] = client_name
                break

            if result.get("classificacao"):
                normalized["rank"] = result["classificacao"]
                normalized["status"] = f"Rank {result['classificacao']}"
                normalized["source"] = client_name

        return normalized
