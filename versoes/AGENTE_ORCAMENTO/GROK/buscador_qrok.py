import json
import logging
import os
import numpy as np
import pandas as pd
import requests
from typing import List, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Configurações
ARQUIVO_CACHE = "cache.json"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "sua-chave-api-groq-aqui")
PASTA_INDICE = "indices"

if not GROQ_API_KEY or GROQ_API_KEY == "sua-chave-api-groq-aqui":
    logger.error("Chave de API Groq não configurada ou inválida")
    raise ValueError("Configure a variável GROQ_API_KEY com uma chave válida")

@dataclass
class RateLimiterOtimizado:
    rpm: int
    tpm: int
    rpd: int
    tokens_usados: int = 0
    requisicoes_usadas: int = 0
    ultima_requisicao: datetime = None
    limits_set: bool = False

    def pode_fazer_requisicao(self, tokens: int = 0) -> bool:
        agora = datetime.now()
        if self.ultima_requisicao and (agora - self.ultima_requisicao).total_seconds() < 60:
            if self.requisicoes_usadas >= self.rpm or self.tokens_usados + tokens > self.tpm:
                return False
        else:
            self.requisicoes_usadas = 0
            self.tokens_usados = 0
            self.ultima_requisicao = agora
        return True

    def atualizar(self, tokens: int):
        self.requisicoes_usadas += 1
        self.tokens_usados += tokens
        self.ultima_requisicao = datetime.now()

class CacheSimples:
    def __init__(self, arquivo: str):
        self.arquivo = arquivo
        self.cache = {}
        if os.path.exists(arquivo):
            try:
                with open(arquivo, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
            except Exception as e:
                logger.error(f"Erro ao carregar cache: {e}")

    def get(self, chave: str) -> Any:
        return self.cache.get(chave)

    def set(self, chave: str, valor: Any):
        self.cache[chave] = valor
        try:
            with open(self.arquivo, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Erro ao salvar cache: {e}")

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

    def criar_prompt_batch(self, descricoes_batch: List[str]) -> str:
        prompt_base = """
Você é um especialista em instrumentos musicais e equipamentos de áudio para licitações públicas.
TAREFA: Analise cada descrição de produto e extraia metadados técnicos em formato JSON.
CAMPOS JSON OBRIGATÓRIOS:
- categoria_principal: uma das categorias listadas
- subcategoria: tipo específico
- afinacao: afinação musical ou null
- dimensao: medidas principais ou null
- material: material principal ou null
- potencia: potência elétrica ou null
- marca: marca identificada ou null
- modelo: modelo identificado ou null
- especificacoes_extras: dict com specs adicionais ou {}
Retorne APENAS um array JSON válido, sem texto adicional.
"""
        descricoes = "\n".join([f"Descrição {i+1}: {desc}" for i, desc in enumerate(descricoes_batch)])
        return f"{prompt_base}\n\nDESCRIÇÕES:\n{descricoes}"

    def processar_descricao(self, descricoes: List[str]) -> List[Dict]:
        cached = self.cache.get(str(descricoes))
        if cached:
            logger.info("Retornando resultado do cache")
            return cached

        if not self.rate_limiter.pode_fazer_requisicao(len("".join(descricoes))):
            logger.warning("Limite de taxa atingido, aguardando...")
            return []

        try:
            data = {
                "model": self.model,
                "messages": [{"role": "user", "content": self.criar_prompt_batch(descricoes)}]
            }
            response = requests.post(self.groq_url, headers=self.headers, json=data, timeout=60)
            response.raise_for_status()
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            total_tokens = result.get("usage", {}).get("total_tokens", 0)
            if not self.rate_limiter.limits_set:
                self.rate_limiter.rpm = int(response.headers.get('X-RateLimit-Limit-RPM', 30))
                self.rate_limiter.tpm = int(response.headers.get('X-RateLimit-Limit-TPM', 6000))
                self.rate_limiter.rpd = int(response.headers.get('X-RateLimit-Limit-RPD', 1000))
                self.rate_limiter.limits_set = True
            if not content.strip():
                logger.error("Conteúdo da resposta da API está vazio")
                return []
            try:
                metadados = json.loads(content)
                self.cache.set(str(descricoes), metadados)
                self.rate_limiter.atualizar(total_tokens)
                return metadados
            except json.JSONDecodeError as e:
                logger.error(f"Erro ao decodificar JSON: {e}")
                return []
        except Exception