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
import faiss

logger = logging.getLogger(__name__)

# Configurações
CAMINHO_DADOS = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\data_base.xlsx"
PASTA_INDICE = "base_dados"
ARQUIVO_CACHE = "cache_llm.pkl"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "sua-chave-api-groq-aqui")

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

class ProcessadorLLM:
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
        except Exception as e:
            logger.error(f"Erro ao processar descrições: {e}")
            return []

class EmbeddingLocalOtimizado:
    def __init__(self, modelo: str = "all-MiniLM-L6-v2"):
        self.modelo = SentenceTransformer(modelo)
        logger.info(f"✅ Embedding local inicializado com {modelo}")

    def criar_texto_embedding(self, row: Dict, metadados: Dict) -> str:
        marca = str(row.get('Marca', '')).strip()
        modelo = str(row.get('Modelo', '')).strip()
        descricao = str(row.get('Descrição', '')).strip()
        categoria = metadados.get('categoria_principal', 'OUTROS')
        subcategoria = metadados.get('subcategoria', '')
        return f"Categoria: {categoria} | Subcategoria: {subcategoria} | Marca: {marca} | Modelo: {modelo} | Descrição: {descricao}"

    def gerar_embeddings_batch(self, textos: List[str]) -> np.ndarray:
        textos_validos = [str(t).strip()[:512] for t in textos if str(t).strip()]
        if not textos_validos:
            logger.error("Nenhum texto válido para embedding")
            return np.random.rand(len(textos), 384).astype('float32')
        try:
            embeddings = self.modelo.encode(textos_validos, batch_size=32, show_progress_bar=False)
            return np.array(embeddings).astype('float32')
        except Exception as e:
            logger.error(f"Erro ao gerar embeddings: {e}")
            return np.random.rand(len(textos), 384).astype('float32')

class IndexadorOtimizado:
    def __init__(self):
        self.processador_llm = ProcessadorLLM()
        self.embedding_generator = EmbeddingLocalOtimizado()
        os.makedirs(PASTA_INDICE, exist_ok=True)
        logger.info("🎼 Indexador Otimizado inicializado")

    def processar_lote(self, dados: pd.DataFrame, batch_size: int = 20) -> List[Dict]:
        metadados = []
        for i in range(0, len(dados), batch_size):
            batch = dados.iloc[i:i + batch_size]
            descricoes = batch['Descrição'].tolist()
            metadados_batch = self.processador_llm.processar_descricao(descricoes)
            metadados.extend(metadados_batch)
        return metadados

    def processar_completo(self):
        logger.info("🚀 Iniciando processamento completo")
        df = pd.read_excel(CAMINHO_DADOS)
        logger.info(f"✅ Dados carregados: {len(df)} produtos válidos")
        metadados = self.processar_lote(df)
        logger.info(f"✅ Processamento concluído: {len(metadados)} metadados gerados")
        
        logger.info("📝 Criando textos para embedding...")
        textos = [self.embedding_generator.criar_texto_embedding(row, meta) for _, row, meta in zip(range(len(df)), df.to_dict('records'), metadados)]
        
        logger.info("🧠 Gerando embeddings locais...")
        embeddings = self.embedding_generator.gerar_embeddings_batch(textos)
        
        logger.info("🔍 Criando índice FAISS...")
        index = faiss.IndexFlatL2(384)
        index.add(embeddings)
        faiss.write_index(index, os.path.join(PASTA_INDICE, 'instrumentos.index'))
        logger.info(f"💾 Índice FAISS salvo: {os.path.join(PASTA_INDICE, 'instrumentos.index')}")
        
        logger.info("📊 Criando mapeamento completo...")
        mapeamentos = pd.DataFrame({
            'id': df.index,
            'metadados': metadados
        }).reset_index(drop=True)
        mapeamentos.to_excel(os.path.join(PASTA_INDICE, 'mapeamentos.xlsx'), index=False)
        logger.info("✅ Mapeamento salvo")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    indexador = IndexadorOtimizado()
    indexador.processar_completo()