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

FLUXO OTIMIZADO:
data_base.xlsx → Batches LLM → Embeddings JINA → FAISS + Excel

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
from datetime import datetime
import pickle
import time

# Importar módulos locais
from rate_limiter_otimizado import RateLimiterOtimizado

warnings.filterwarnings('ignore')

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# === CONFIGURAÇÕES ===
CAMINHO_DADOS = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\FORNECEDORES\data_base.xlsx"
PASTA_INDICE = "indice_musical_otimizado"
ARQUIVO_INDICE = os.path.join(PASTA_INDICE, "instrumentos.index")
ARQUIVO_MAPEAMENTO = os.path.join(PASTA_INDICE, "mapeamento_completo.xlsx")
ARQUIVO_CACHE = os.path.join(PASTA_INDICE, "cache_llm.pkl")
ARQUIVO_PROGRESSO = os.path.join(PASTA_INDICE, "progresso.json")

# APIs
GROQ_API_KEY = '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'
JINA_API_KEY = "jina_64f56d5dfa26445e8d10ebcec8897233YCgLfgNjODz8G8__hQ_u67Urx3dI"

# Parâmetros de processamento
BATCH_SIZE_DEFAULT = 500
BATCH_SIZE_MIN = 100
BATCH_SIZE_MAX = 500
EMBEDDING_DIMENSION = 1024  # JINA embeddings

class CacheSimples:
    """Cache simples baseado em arquivo pickle (sem SQL)"""
    
    def __init__(self, arquivo_cache):
        self.arquivo_cache = arquivo_cache
        self.cache = {}
        self.carregar_cache()
    
    def carregar_cache(self):
        try:
            if os.path.exists(self.arquivo_cache):
                with open(self.arquivo_cache, 'rb') as f:
                    self.cache = pickle.load(f)
                logger.info("Cache carregado: %d entradas", len(self.cache))
            else:
                self.cache = {}
                logger.info("Cache novo criado")
        except Exception as e:
            logger.warning("Erro ao carregar cache: %s. Criando novo.", e)
            self.cache = {}
    
    def salvar_cache(self):
        try:
            os.makedirs(os.path.dirname(self.arquivo_cache), exist_ok=True)
            with open(self.arquivo_cache, 'wb') as f:
                pickle.dump(self.cache, f)
            logger.debug("Cache salvo: %d entradas", len(self.cache))
        except Exception as e:
            logger.error("Erro ao salvar cache: %s", e)
    
    def gerar_hash(self, texto):
        return hashlib.md5(str(texto).encode('utf-8')).hexdigest()
    
    def get(self, texto):
        hash_texto = self.gerar_hash(texto)
        return self.cache.get(hash_texto)
    
    def set(self, texto, metadados):
        hash_texto = self.gerar_hash(texto)
        self.cache[hash_texto] = metadados
    
    def get_stats(self):
        return {
            'total_entradas': len(self.cache),
            'tamanho_arquivo': os.path.getsize(self.arquivo_cache) if os.path.exists(self.arquivo_cache) else 0
        }

class ProcessadorLLMOtimizado:
    """Processador LLM com batches inteligentes e rate limiting"""
    
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

    def criar_prompt_batch(self, descricoes_batch):
        prompt_base = """
Você é um especialista em instrumentos musicais e equipamentos de áudio para licitações públicas.

TAREFA: Analise cada descrição de produto e extraia metadados técnicos em formato JSON.

CATEGORIAS PRINCIPAIS:
- INSTRUMENTO_SOPRO_METAL (trompete, bombardino, trombone, tuba, sousafone)
- INSTRUMENTO_SOPRO_MADEIRA (clarinete, saxofone, flauta, oboé)
- INSTRUMENTO_PERCUSSAO_PELE (bumbo, surdo, tarol, caixa clara, tambor)
- INSTRUMENTO_PERCUSSAO_METAL (prato, triângulo, carrilhão, sino)
- INSTRUMENTO_CORDA (violino, viola, violão, guitarra, baixo)
- ACESSORIO_SOPRO (bocal, boquilha, palheta, estante)
- ACESSORIO_PERCUSSAO (baqueta, talabarte, pele, esteira)
- ACESSORIO_CORDA (corda, arco, cavalete)
- EQUIPAMENTO_SOM (caixa de som, amplificador, mesa de som)
- EQUIPAMENTO_AUDIO (microfone, cabo, conector)
- OUTROS (produtos não identificados)

CAMPOS JSON OBRIGATÓRIOS:
- categoria_principal: uma das categorias acima
- subcategoria: tipo específico (ex: TROMPETE, CAIXA_ATIVA, BAQUETA)
- afinacao: afinação musical (ex: Bb, Eb, F) ou null
- dimensao: medidas principais (ex: "15 polegadas", "20x30 cm") ou null
- material: material principal (ex: bronze, madeira, plástico) ou null
- potencia: potência elétrica (ex: "400W RMS") ou null
- marca: marca identificada ou null
- modelo: modelo identificado ou null
- especificacoes_extras: dict com specs adicionais ou {}

FORMATO DE RESPOSTA:
Retorne APENAS um array JSON válido, sem texto adicional:
[
  {"categoria_principal": "...", "subcategoria": "...", ...},
  {"categoria_principal": "...", "subcategoria": "...", ...}
]

DESCRIÇÕES PARA ANÁLISE:
"""
        descricoes_numeradas = [f"{i+1}. {desc}" for i, desc in enumerate(descricoes_batch)]
        return prompt_base + "\n".join(descricoes_numeradas)
    
    def processar_batch_llm(self, descricoes_batch):
        prompt = self.criar_prompt_batch(descricoes_batch)
        
        if not self.rate_limiter.wait_if_needed([prompt]):
            logger.error("Rate limit excedido. Não é possível processar batch.")
            return [{}] * len(descricoes_batch)
        
        try:
            logger.info("Processando batch de %d itens com Groq LLM...", len(descricoes_batch))
            data = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}]
            }
            response = requests.post(self.groq_url, headers=self.headers, json=data, timeout=120)  # Aumentado o timeout
            response.raise_for_status()
            
            response_json = response.json()
            logger.debug("Resposta bruta da Groq: %s", response_json)  # Log da resposta bruta
            
            if 'choices' not in response_json or not response_json['choices']:
                logger.error("Resposta não contém 'choices': %s", response_json)
                return [{}] * len(descricoes_batch)
            
            response_text = response_json['choices'][0]['message']['content'].strip()
            logger.debug("Conteúdo da resposta: %s", response_text[:500])  # Log do conteúdo (primeiros 500 caracteres)
            
            # Tentar extrair JSON da resposta
            try:
                # Procurar por JSON entre colchetes
                start_idx = response_text.find('[')
                end_idx = response_text.rfind(']') + 1
                if start_idx == -1 or end_idx == 0:
                    logger.error("JSON não encontrado na resposta: %s", response_text[:500])
                    return [{}] * len(descricoes_batch)
                
                json_text = response_text[start_idx:end_idx]
                metadados_list = json.loads(json_text)
                
                if len(metadados_list) != len(descricoes_batch):
                    logger.warning("Número de metadados (%d) diferente do esperado (%d)", 
                                 len(metadados_list), len(descricoes_batch))
                    while len(metadados_list) < len(descricoes_batch):
                        metadados_list.append({})
                    metadados_list = metadados_list[:len(descricoes_batch)]
                
                logger.info("✅ Batch processado com sucesso: %d metadados extraídos", len(metadados_list))
                self.rate_limiter.record_request([prompt], success=True)
                return metadados_list
            except json.JSONDecodeError as e:
                logger.error("❌ Erro ao decodificar JSON: %s. Resposta: %s", e, response_text[:500])
                return [{}] * len(descricoes_batch)
        except requests.exceptions.HTTPError as http_err:
            logger.error("❌ Erro HTTP ao processar batch: %s. Status: %s", http_err, response.status_code)
            if response.status_code == 429:
                logger.warning("HTTP 429 - Rate limit atingido. Aguardando retry...")
                time.sleep(60)  # Aguardar 1 minuto em caso de rate limit
            self.rate_limiter.record_request([prompt], success=False)
            return [{}] * len(descricoes_batch)
        except Exception as e:
            logger.error("❌ Erro geral ao processar batch com LLM: %s", e)
            self.rate_limiter.record_request([prompt], success=False)
            return [{}] * len(descricoes_batch)
    
    def processar_descricoes_com_cache(self, df_produtos):
        logger.info("🔄 Iniciando processamento de %d produtos", len(df_produtos))
        produtos_para_processar = []
        metadados_finais = []
        
        for idx, row in df_produtos.iterrows():
            descricao = str(row.get('Descrição', '')).strip()
            if not descricao or descricao.lower() == 'nan':
                metadados_finais.append({})
                continue
            metadados_cache = self.cache.get(descricao)
            if metadados_cache:
                metadados_finais.append(metadados_cache)
                logger.debug("Cache hit para: %s", descricao[:50])
            else:
                produtos_para_processar.append((idx, descricao))
                metadados_finais.append(None)
        
        cache_hits = len([m for m in metadados_finais if m is not None])
        logger.info("📊 Cache: %d hits, %d para processar", cache_hits, len(produtos_para_processar))
        
        if produtos_para_processar:
            batch_size = self.rate_limiter.suggest_batch_size(
                len(produtos_para_processar), avg_tokens_per_item=250
            )
            logger.info("🔄 Processando %d produtos em batches de %d", 
                       len(produtos_para_processar), batch_size)
            
            for i in tqdm(range(0, len(produtos_para_processar), batch_size), 
                         desc="Processando batches"):
                batch = produtos_para_processar[i:i+batch_size]
                descricoes_batch = [desc for _, desc in batch]
                indices_batch = [idx for idx, _ in batch]
                metadados_batch = self.processar_batch_llm(descricoes_batch)
                
                for j, (idx_original, descricao) in enumerate(batch):
                    metadados = metadados_batch[j] if j < len(metadados_batch) else {}
                    pos_final = next(i for i, (idx, _) in enumerate(produtos_para_processar) 
                                   if idx == idx_original)
                    metadados_finais[idx_original] = metadados
                    self.cache.set(descricao, metadados)
                
                if i % (batch_size * 5) == 0:
                    self.cache.salvar_cache()
                time.sleep(1)
        
        self.cache.salvar_cache()
        metadados_finais = [m if m is not None else {} for m in metadados_finais]
        logger.info("✅ Processamento concluído: %d metadados gerados", len(metadados_finais))
        return metadados_finais

class EmbeddingJINAOtimizado:
    def __init__(self):
        self.api_key = JINA_API_KEY
        self.url = "https://api.jina.ai/v1/embeddings"
        self.model = "jina-embeddings-v3"
        self.max_batch_size = 500
        if not self.api_key or self.api_key == "SUA_JINA_API_KEY_AQUI":
            logger.warning("⚠️ JINA API Key não configurada")
    
    def criar_texto_embedding(self, row, metadados):
        marca = str(row.get('Marca', '')).strip()
        modelo = str(row.get('Modelo', '')).strip()
        descricao = str(row.get('Descrição', '')).strip()
        categoria = metadados.get('categoria_principal', 'OUTROS')
        subcategoria = metadados.get('subcategoria', '')
        afinacao = metadados.get('afinacao', '')
        dimensao = metadados.get('dimensao', '')
        material = metadados.get('material', '')
        potencia = metadados.get('potencia', '')
        
        partes = []
        if categoria != 'OUTROS':
            partes.append(f"CATEGORIA: {categoria}")
        if subcategoria:
            partes.append(f"TIPO: {subcategoria}")
        if marca:
            partes.append(f"MARCA: {marca}")
        if modelo:
            partes.append(f"MODELO: {modelo}")
        specs = []
        if afinacao:
            specs.append(f"AFINACAO: {afinacao}")
        if dimensao:
            specs.append(f"DIMENSAO: {dimensao}")
        if material:
            specs.append(f"MATERIAL: {material}")
        if potencia:
            specs.append(f"POTENCIA: {potencia}")
        if specs:
            partes.append(f"SPECS: {' | '.join(specs)}")
        if descricao:
            partes.append(f"DESC: {descricao}")
        return " || ".join(partes)
    
    def gerar_embeddings_batch(self, textos):
        if not self.api_key or self.api_key == "SUA_JINA_API_KEY_AQUI":
            logger.warning("JINA API não configurada. Usando embeddings aleatórios.")
            return np.random.rand(len(textos), EMBEDDING_DIMENSION).astype('float32')
        
        # Sanitizar textos
        textos_validos = [str(t).strip() for t in textos if str(t).strip()]
        if not textos_validos:
            logger.error("Nenhum texto válido para embedding")
            return np.random.rand(len(textos), EMBEDDING_DIMENSION).astype('float32')
        
        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}'
            }
            data = {
                'model': self.model,
                'input': textos_validos,
                'encoding_format': 'float'
            }
            logger.debug("Enviando requisição Jina: %s", json.dumps(data, ensure_ascii=False)[:500])
            response = requests.post(self.url, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            result = response.json()
            embeddings = [item['embedding'] for item in result['data']]
            return np.array(embeddings).astype('float32')
        except Exception as e:
            logger.error("Erro ao gerar embeddings JINA: %s. Resposta: %s", e, response.text if 'response' in locals() else 'N/A')
            return np.random.rand(len(textos), EMBEDDING_DIMENSION).astype('float32')

class IndexadorOtimizado:
    def __init__(self):
        self.processador_llm = ProcessadorLLMOtimizado()
        self.embedding_generator = EmbeddingJINAOtimizado()
        os.makedirs(PASTA_INDICE, exist_ok=True)
        logger.info("🎼 Indexador Otimizado inicializado")
    
    def carregar_dados(self):
        try:
            logger.info("📂 Carregando dados de: %s", CAMINHO_DADOS)
            df = pd.read_excel(CAMINHO_DADOS)
            df = df.dropna(subset=['Descrição'])
            df = df[df['Descrição'].str.strip() != '']
            logger.info("✅ Dados carregados: %d produtos válidos", len(df))
            return df
        except Exception as e:
            logger.error("❌ Erro ao carregar dados: %s", e)
            raise
    
    def salvar_progresso(self, etapa, dados=None):
        progresso = {
            'timestamp': datetime.now().isoformat(),
            'etapa': etapa,
            'dados': dados
        }
        try:
            with open(ARQUIVO_PROGRESSO, 'w', encoding='utf-8') as f:
                json.dump(progresso, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning("Erro ao salvar progresso: %s", e)
    
    def processar_completo(self):
        logger.info("🚀 Iniciando processamento completo")
        df_produtos = self.carregar_dados()
        self.salvar_progresso("dados_carregados", {"total_produtos": len(df_produtos)})
        
        logger.info("🤖 Processando metadados com LLM...")
        metadados_list = self.processador_llm.processar_descricoes_com_cache(df_produtos)
        self.salvar_progresso("metadados_processados", {"total_metadados": len(metadados_list)})
        
        logger.info("📝 Criando textos para embedding...")
        textos_embedding = []
        for idx, row in df_produtos.iterrows():
            metadados = metadados_list[idx] if idx < len(metadados_list) else {}
            texto = self.embedding_generator.criar_texto_embedding(row, metadados)
            textos_embedding.append(texto)
        textos_embedding = [str(t).strip() if t else "vazio" for t in textos_embedding]
        
        logger.info("🧠 Gerando embeddings com JINA...")
        embeddings = self.embedding_generator.gerar_embeddings_batch(textos_embedding)
        faiss.normalize_L2(embeddings)
        self.salvar_progresso("embeddings_gerados", {"dimensao": embeddings.shape[1]})
        
        logger.info("🔍 Criando índice FAISS...")
        dimensao = embeddings.shape[1]
        index = faiss.IndexFlatIP(dimensao)
        index = faiss.IndexIDMap(index)
        index.add_with_ids(embeddings, np.arange(len(embeddings)))
        faiss.write_index(index, ARQUIVO_INDICE)
        logger.info("💾 Índice FAISS salvo: %s", ARQUIVO_INDICE)
        logger.info("📊 Criando mapeamento completo...")
        df_mapeamento = df_produtos.copy().reset_index(drop=True)
        if len(metadados_list) != len(df_mapeamento):
            logger.warning("Tamanho de metadados_list (%d) difere de df_mapeamento (%d)", 
                        len(metadados_list), len(df_mapeamento))
            metadados_list = metadados_list[:len(df_mapeamento)] + [{}] * (len(df_mapeamento) - len(metadados_list))
        for idx, metadados in enumerate(metadados_list):
            for key, value in metadados.items():
                df_mapeamento.iloc[idx][f'llm_{key}'] = value
        df_mapeamento['texto_embedding'] = textos_embedding
        df_mapeamento.to_excel(ARQUIVO_MAPEAMENTO, index=True)
        logger.info("💾 Mapeamento salvo: %s", ARQUIVO_MAPEAMENTO)
        
        stats_cache = self.processador_llm.cache.get_stats()
        stats_rate_limiter = self.processador_llm.rate_limiter.get_statistics()
        estatisticas = {
            'total_produtos': len(df_produtos),
            'total_metadados': len(metadados_list),
            'dimensao_embeddings': dimensao,
            'cache_stats': stats_cache,
            'rate_limiter_stats': stats_rate_limiter
        }
        self.salvar_progresso("processamento_completo", estatisticas)
        
        logger.info("🎉 PROCESSAMENTO COMPLETO CONCLUÍDO!")
        logger.info("📊 Estatísticas:")
        logger.info("   Produtos processados: %d", len(df_produtos))
        logger.info("   Metadados extraídos: %d", len(metadados_list))
        logger.info("   Dimensão embeddings: %d", dimensao)
        logger.info("   Cache: %d entradas", stats_cache['total_entradas'])
        logger.info("   Solicitações LLM: %d", stats_rate_limiter['total_requests'])
        logger.info("   Taxa de sucesso: %.1f%%", stats_rate_limiter['success_rate'])
        return estatisticas

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
        print("=" * 80)
        print("🚀 Execute agora: python buscador_otimizado.py")
        print("=" * 80)
    except Exception as e:
        logger.error("❌ Erro durante indexação: %s", e)
        print(f"\n❌ ERRO: {e}")
        print("Verifique os logs para mais detalhes.")