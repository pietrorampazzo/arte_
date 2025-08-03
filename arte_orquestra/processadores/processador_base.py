#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎼 INDEXADOR MUSICAL OTIMIZADO - BATCHES INTELIGENTES
Versão: Estado da Arte - Janeiro 2025 (Adaptado para Groq)

ARQUITETURA SIMPLIFICADA:
✅ FAISS para vetores (rápido e eficiente)
✅ Excel/CSV para metadados (simples e confiável)
✅ Batches inteligentes com LLM Groq (economia de tokens)
✅ Rate limiting otimizado (respeita limites Groq)
✅ Cache em arquivo (sem SQL, mais simples)
✅ Embeddings locais com sentence-transformers (sem APIs externas)

FLUXO OTIMIZADO:
data_base.xlsx → Batches LLM → Embeddings Locais → FAISS + Excel

ESTRATÉGIA DE BATCHES:
- 20 itens por batch (~5.000 tokens)
- Processamento adaptativo baseado em rate limits
- Cache para evitar reprocessamento
- Recuperação automática de erros

Autor: Sistema Simplificado
"""

import pandas as pd
import numpy as np
import faiss
import os
import logging
import json
import hashlib
import requests
from tqdm import tqdm
import warnings
from datetime import datetime, timedelta
import pickle
import time
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
from dataclasses import dataclass
import sys

warnings.filterwarnings('ignore')

# Adicionar diretório src ao caminho, se necessário
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Importar RateLimiterOtimizado de utils
try:
    from utils import RateLimiterOtimizado
except ImportError as e:
    logger.error("Erro ao importar RateLimiterOtimizado de utils: %s. Verifique a pasta 'src/utils.py'.", e)
    raise

# === CONFIGURAÇÕES ===
CAMINHO_DADOS = os.getenv("CAMINHO_DADOS", "data_base.xlsx")
PASTA_INDICE = "indice_musical_otimizado"
ARQUIVO_INDICE = os.path.join(PASTA_INDICE, "instrumentos.index")
ARQUIVO_MAPEAMENTO = os.path.join(PASTA_INDICE, "mapeamento_completo.xlsx")
ARQUIVO_CACHE = os.path.join(PASTA_INDICE, "cache_llm.pkl")
ARQUIVO_PROGRESSO = os.path.join(PASTA_INDICE, "progresso.json")

# APIs
GROQ_API_KEY = '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'

# Parâmetros de processamento
BATCH_SIZE_DEFAULT = 20
BATCH_SIZE_MIN = 10
BATCH_SIZE_MAX = 50
EMBEDDING_DIMENSION = 384  # all-MiniLM-L6-v2

class CacheSimples:
    # ... (implementação idêntica à anterior)

class ProcessadorLLMOtimizado:
    def __init__(self):
        self.rate_limiter = RateLimiterOtimizado(rpm=30, tpm=6000, rpd=1000)
        self.cache = CacheSimples(ARQUIVO_CACHE)
        self.groq_url = "https://api.groq.com/openai/v1/chat/completions"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GROQ_API_KEY}"
        }
        self.model = "deepseek-r1-distill-llama-70b"
        logger.info("✅ Groq LLM inicializado")

    # ... (implementação idêntica à anterior)

class EmbeddingLocalOtimizado:
    # ... (implementação idêntica à anterior)

class IndexadorOtimizado:
    def __init__(self):
        self.processador_llm = ProcessadorLLMOtimizado()
        self.embedding_generator = EmbeddingLocalOtimizado()
        os.makedirs(PASTA_INDICE, exist_ok=True)
        logger.info("🎼 Indexador Otimizado inicializado")

    # ... (implementação idêntica à anterior)

if __name__ == "__main__":
    print("🎼 INDEXADOR MUSICAL OTIMIZADO - ESTADO DA ARTE")
    print("=" * 80)
    print("🎯 Arquitetura simplificada: FAISS + Excel (sem SQL)")
    print("🤖 Batches inteligentes com rate limiting")
    print("⚡ Cache otimizado para economia de tokens")
    print("🔄 Processamento adaptativo e recuperação de erros")
    print("=" * 80)

    try:
        indexador = IndexadorOtimizado()
        estatisticas = indexador.processar_completo()
        print("\n🎉 INDEXAÇÃO CONCLUÍDA COM SUCESSO!")
        print("=" * 80)
        print(f"📁 Arquivos gerados:")
        print(f"   Índice FAISS: {ARQUIVO_INDICE}")
        print(f"   Mapeamento: {ARQUIVO_MAPEAMENTO}")
        print(f"   Cache: {ARQUIVO_CACHE}")
        print(f"   Progresso: {ARQUIVO_PROGRESSO}")
        print(f"   Relatório: {os.path.join(PASTA_INDICE, 'relatorio_licitacao.csv')}")
        print("=" * 80)
        print("🚀 Execute agora: python buscador_otimizado.py")
        print("=" * 80)
    except Exception as e:
        logger.error("❌ Erro durante indexação: %s", e)
        print(f"\n❌ ERRO: {e}")
        print("Verifique os logs para mais detalhes.")