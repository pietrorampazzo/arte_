"""
Configuration module for tender monitoring system.
Contains al# Excel Configuration
EXCEL_CONFIG = {
    "input_file": "C:/Users/pietr/OneDrive/.vscode/arte_/TRELLO.xlsx",
    "output_dir": "C:/Users/pietr/OneDrive/.vscode/arte_/DOWNLOADS/RESULTADO",
    "sheet_name": "Planilha1",  # Nome correto da aba
    "date_format": "%Y-%m-%d"}endpoints, parameters, and settings.
"""

# Company Information
COMPANY_CNPJ = "05019519000135"

# API Base URLs
PNCP_BASE_URL = "https://pncp.gov.br/api/v1"
COMPRASGOV_BASE_URL = "https://compras.dados.gov.br"
TRANSPARENCIA_BASE_URL = "https://api.portaldatransparencia.gov.br/api-de-dados"

# API Endpoints
ENDPOINTS = {
    "pncp": {
        "licitacoes": f"{PNCP_BASE_URL}/licitacoes",
        "resultados": f"{PNCP_BASE_URL}/resultados",
        "contratos": f"{PNCP_BASE_URL}/contratos",
    },
    "comprasgov": {
        "pregoes": f"{COMPRASGOV_BASE_URL}/pregoes/v1/pregoes",
        "itens": f"{COMPRASGOV_BASE_URL}/pregoes/v1/itens",
        "atas": f"{COMPRASGOV_BASE_URL}/pregoes/v1/atas",
    },
    "transparencia": {
        "licitacoes": f"{TRANSPARENCIA_BASE_URL}/licitacoes",
        "contratos": f"{TRANSPARENCIA_BASE_URL}/contratos",
    }
}

# Rate Limiting Configuration
RATE_LIMITS = {
    "pncp": {"requests_per_minute": 60, "burst": 10},
    "comprasgov": {"requests_per_minute": 30, "burst": 5},
    "transparencia": {"requests_per_minute": 30, "burst": 5}
}

# Request Timeouts (seconds)
TIMEOUTS = {
    "connect": 5,
    "read": 30,
    "total": 35
}

# Retry Configuration
RETRY_CONFIG = {
    "max_retries": 3,
    "backoff_factor": 2,
    "status_forcelist": [500, 502, 503, 504]
}

# Response Validation Rules
VALIDATION_RULES = {
    "pncp": {
        "required_fields": ["numero", "uasg", "dataAbertura", "status"],
        "date_fields": ["dataAbertura", "dataPublicacao"],
    },
    "comprasgov": {
        "required_fields": ["codigoLicitacao", "numeroUasg", "dataAbertura"],
        "date_fields": ["dataAbertura", "dataPublicacao"],
    },
    "transparencia": {
        "required_fields": ["id", "uasg", "dataAbertura"],
        "date_fields": ["dataAbertura"],
    }
}

# Excel Configuration
EXCEL_CONFIG = {
    "input_file": r"C:\Users\pietr\OneDrive\.vscode\arte_\TRELLO.xlsx",
    "output_dir": r"C:\Users\pietr\OneDrive\.vscode\arte_\DOWNLOADS\RESULTADO",
    "sheet_name": "Licitações",
    "date_format": "%Y-%m-%d"
}
