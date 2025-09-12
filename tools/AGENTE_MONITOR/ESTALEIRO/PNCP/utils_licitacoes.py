"""
Utility functions for tender monitoring system.
"""
import re
import os
import pandas as pd
from datetime import datetime
import logging
from typing import Dict, List, Optional, Union
import config_endpoints as config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('arte_orchestrator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def parse_tender_info(filename: str) -> Dict[str, str]:
    """
    Extract UASG and edital numbers from filename using U_xxx_E_yyy pattern
    """
    pattern = r"U_(\d+)_E_(\d+)"
    match = re.search(pattern, filename)
    if not match:
        raise ValueError(f"Invalid filename format: {filename}")
    return {
        "uasg": match.group(1),
        "edital": match.group(2)
    }

def normalize_cnpj(cnpj: str) -> str:
    """
    Normalize CNPJ format by removing special characters
    """
    return re.sub(r'[^0-9]', '', cnpj)

def format_date(date_str: str, input_format: str = "%Y-%m-%d") -> str:
    """
    Convert date string to standard format
    """
    try:
        date_obj = datetime.strptime(date_str, input_format)
        return date_obj.strftime("%Y-%m-%d")
    except ValueError as e:
        logger.error(f"Date format error: {e}")
        return date_str

def load_excel_data(filepath: str = config.EXCEL_CONFIG["input_file"]) -> pd.DataFrame:
    """
    Load and validate Excel data
    """
    try:
        # Primeiro tenta ler a planilha especificada
        try:
            df = pd.read_excel(filepath, sheet_name=config.EXCEL_CONFIG["sheet_name"])
        except ValueError:
            # Se falhar, lê todas as planilhas e usa a primeira
            df = pd.read_excel(filepath, sheet_name=None)
            df = df[list(df.keys())[0]]
        
        # Verifica se as colunas necessárias existem
        required_columns = ["UASG", "EDITAL", "Item"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        return df
    except Exception as e:
        logger.error(f"Error loading Excel file: {e}")
        raise

def save_excel_data(df: pd.DataFrame, filename: str) -> None:
    """
    Save DataFrame to Excel with standard formatting
    """
    output_path = os.path.join(config.EXCEL_CONFIG["output_dir"], filename)
    try:
        df.to_excel(output_path, index=False, date_format=config.EXCEL_CONFIG["date_format"])
        logger.info(f"Data saved successfully to {output_path}")
    except Exception as e:
        logger.error(f"Error saving Excel file: {e}")
        raise

def validate_api_response(response: Dict, api_type: str) -> bool:
    """
    Validate API response against configured rules
    """
    rules = config.VALIDATION_RULES.get(api_type)
    if not rules:
        return True
    
    required_fields = rules["required_fields"]
    missing_fields = [field for field in required_fields if field not in response]
    
    if missing_fields:
        logger.warning(f"Missing required fields in {api_type} response: {missing_fields}")
        return False
        
    return True

def format_api_url(base_url: str, **params) -> str:
    """
    Format API URL with parameters
    """
    query_params = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
    return f"{base_url}{'?' + query_params if query_params else ''}"

def get_tender_status(response_data: Dict) -> str:
    """
    Determine tender status from API response
    """
    if not response_data:
        return "Aguardando Disputa"
    
    if response_data.get("adjudicado"):
        return "Adjudicada" if response_data.get("vencedor") == "ARTE" else "Perdida"
    
    rank = response_data.get("classificacao")
    return f"Rank {rank}" if rank else "Aguardando Disputa"
