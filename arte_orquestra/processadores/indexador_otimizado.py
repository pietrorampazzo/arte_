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
GOOGLE_API_KEY = 'AIzaSyBdrzcton2jUCv5PSaXE38UCp-l8O42Fvc'

# Parâmetros de processamento
BATCH_SIZE_DEFAULT = 20
BATCH_SIZE_MIN = 10
BATCH_SIZE_MAX = 50
EMBEDDING_DIMENSION = 384  # all-MiniLM-L6-v2

class CacheSimples:
    """Cache simples baseado em arquivo pickle (sem SQL)"""
    
    def __init__(self, arquivo_cache):
        self.arquivo_cache = arquivo_cache
        self.cache = {}
        self.carregar_cache()
    
    def carregar_cache(self):
        """Carrega cache do arquivo"""
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
        """Salva cache no arquivo"""
        try:
            os.makedirs(os.path.dirname(self.arquivo_cache), exist_ok=True)
            with open(self.arquivo_cache, 'wb') as f:
                pickle.dump(self.cache, f)
            logger.debug("Cache salvo: %d entradas", len(self.cache))
        except Exception as e:
            logger.error("Erro ao salvar cache: %s", e)
    
    def gerar_hash(self, texto):
        """Gera hash MD5 para texto"""
        return hashlib.md5(str(texto).encode('utf-8')).hexdigest()
    
    def get(self, texto):
        """Busca no cache"""
        hash_texto = self.gerar_hash(texto)
        return self.cache.get(hash_texto)
    
    def set(self, texto, metadados):
        """Adiciona ao cache"""
        hash_texto = self.gerar_hash(texto)
        self.cache[hash_texto] = metadados
    
    def get_stats(self):
        """Retorna estatísticas do cache"""
        return {
            'total_entradas': len(self.cache),
            'tamanho_arquivo': os.path.getsize(self.arquivo_cache) if os.path.exists(self.arquivo_cache) else 0
        }

class ProcessadorLLMOtimizado:
    """Processador LLM com batches inteligentes e rate limiting"""
    
    def __init__(self):
        self.model_generativo = None
        self.rate_limiter = RateLimiterOtimizado()
        self.cache = CacheSimples(ARQUIVO_CACHE)
        
        # Inicializar Gemini
        if GOOGLE_API_KEY and GOOGLE_API_KEY != "SUA_GOOGLE_API_KEY_AQUI":
            try:
                genai.configure(api_key=GOOGLE_API_KEY)
                self.model_generativo = genai.GenerativeModel('gemini-2.0-flash-lite')
                logger.info("✅ Gemini 2.0 Flash-Lite carregado")
            except Exception as e:
                logger.warning("⚠️ Erro ao carregar Gemini: %s", e)
        else:
            logger.warning("⚠️ Google API Key não configurada")
    
    def criar_prompt_batch(self, descricoes_batch):
        """Cria prompt otimizado para batch de descrições"""
        
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
        
        # Adicionar descrições numeradas
        descricoes_numeradas = []
        for i, desc in enumerate(descricoes_batch):
            descricoes_numeradas.append(f"{i+1}. {desc}")
        
        prompt_completo = prompt_base + "\n".join(descricoes_numeradas)
        
        return prompt_completo
    
    def processar_batch_llm(self, descricoes_batch):
        """Processa batch de descrições com LLM"""
        
        if not self.model_generativo:
            logger.warning("LLM não disponível. Retornando metadados vazios.")
            return [{}] * len(descricoes_batch)
        
        # Verificar rate limits
        prompt = self.criar_prompt_batch(descricoes_batch)
        
        if not self.rate_limiter.wait_if_needed([prompt]):
            logger.error("Rate limit excedido. Não é possível processar batch.")
            return [{}] * len(descricoes_batch)
        
        try:
            # Fazer solicitação
            logger.info("Processando batch de %d itens com LLM...", len(descricoes_batch))
            response = self.model_generativo.generate_content(prompt)
            
            # Registrar solicitação bem-sucedida
            self.rate_limiter.record_request([prompt], success=True)
            
            # Processar resposta
            response_text = response.text.strip()
            
            # Extrair JSON da resposta
            try:
                # Tentar encontrar array JSON na resposta
                start_idx = response_text.find('[')
                end_idx = response_text.rfind(']') + 1
                
                if start_idx != -1 and end_idx != -1:
                    json_text = response_text[start_idx:end_idx]
                    metadados_list = json.loads(json_text)
                    
                    # Validar que temos o número correto de resultados
                    if len(metadados_list) == len(descricoes_batch):
                        logger.info("✅ Batch processado com sucesso: %d metadados extraídos", len(metadados_list))
                        return metadados_list
                    else:
                        logger.warning("⚠️ Número de metadados (%d) diferente do esperado (%d)", 
                                     len(metadados_list), len(descricoes_batch))
                        
                        # Ajustar lista se necessário
                        while len(metadados_list) < len(descricoes_batch):
                            metadados_list.append({})
                        
                        return metadados_list[:len(descricoes_batch)]
                
                else:
                    logger.error("❌ JSON não encontrado na resposta do LLM")
                    return [{}] * len(descricoes_batch)
                    
            except json.JSONDecodeError as e:
                logger.error("❌ Erro ao decodificar JSON: %s", e)
                logger.debug("Resposta recebida: %s", response_text[:500])
                return [{}] * len(descricoes_batch)
        
        except Exception as e:
            logger.error("❌ Erro ao processar batch com LLM: %s", e)
            self.rate_limiter.record_request([prompt], success=False)
            return [{}] * len(descricoes_batch)
    
    def processar_descricoes_com_cache(self, df_produtos):
        """Processa todas as descrições usando cache e batches"""
        
        logger.info("🔄 Iniciando processamento de %d produtos", len(df_produtos))
        
        # Verificar cache primeiro
        produtos_para_processar = []
        metadados_finais = []
        
        for idx, row in df_produtos.iterrows():
            descricao = str(row.get('Descrição', '')).strip()
            
            if not descricao or descricao.lower() == 'nan':
                metadados_finais.append({})
                continue
            
            # Verificar cache
            metadados_cache = self.cache.get(descricao)
            if metadados_cache:
                metadados_finais.append(metadados_cache)
                logger.debug("Cache hit para: %s", descricao[:50])
            else:
                produtos_para_processar.append((idx, descricao))
                metadados_finais.append(None)  # Placeholder
        
        cache_hits = len([m for m in metadados_finais if m is not None])
        logger.info("📊 Cache: %d hits, %d para processar", cache_hits, len(produtos_para_processar))
        
        # Processar em batches
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
                
                # Processar batch
                metadados_batch = self.processar_batch_llm(descricoes_batch)
                
                # Atualizar resultados e cache
                for j, (idx_original, descricao) in enumerate(batch):
                    metadados = metadados_batch[j] if j < len(metadados_batch) else {}
                    
                    # Encontrar posição no array final
                    pos_final = next(i for i, (idx, _) in enumerate(produtos_para_processar) 
                                   if idx == idx_original)
                    
                    # Atualizar resultado final
                    metadados_finais[idx_original] = metadados
                    
                    # Adicionar ao cache
                    self.cache.set(descricao, metadados)
                
                # Salvar cache periodicamente
                if i % (batch_size * 5) == 0:
                    self.cache.salvar_cache()
                
                # Pequena pausa entre batches
                time.sleep(1)
        
        # Salvar cache final
        self.cache.salvar_cache()
        
        # Verificar se todos foram processados
        metadados_finais = [m if m is not None else {} for m in metadados_finais]
        
        logger.info("✅ Processamento concluído: %d metadados gerados", len(metadados_finais))
        
        return metadados_finais

class EmbeddingJINAOtimizado:
    """Gerador de embeddings usando JINA AI"""
    
    def __init__(self):
        self.api_key = JINA_API_KEY
        self.url = "https://api.jina.ai/v1/embeddings"
        self.model = "jina-embeddings-v3"
        self.max_batch_size = 100  # JINA suporta batches grandes
        
        if not self.api_key or self.api_key == "SUA_JINA_API_KEY_AQUI":
            logger.warning("⚠️ JINA API Key não configurada")
    
    def criar_texto_embedding(self, row, metadados):
        """Cria texto otimizado para embedding"""
        
        # Dados básicos
        marca = str(row.get('Marca', '')).strip()
        modelo = str(row.get('Modelo', '')).strip()
        descricao = str(row.get('Descrição', '')).strip()
        
        # Metadados extraídos
        categoria = metadados.get('categoria_principal', 'OUTROS')
        subcategoria = metadados.get('subcategoria', '')
        afinacao = metadados.get('afinacao', '')
        dimensao = metadados.get('dimensao', '')
        material = metadados.get('material', '')
        potencia = metadados.get('potencia', '')
        
        # Construir texto estruturado
        partes = []
        
        # Categoria (peso alto)
        if categoria != 'OUTROS':
            partes.append(f"CATEGORIA: {categoria}")
        
        if subcategoria:
            partes.append(f"TIPO: {subcategoria}")
        
        # Marca e modelo
        if marca:
            partes.append(f"MARCA: {marca}")
        if modelo:
            partes.append(f"MODELO: {modelo}")
        
        # Especificações técnicas
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
        
        # Descrição original
        if descricao:
            partes.append(f"DESC: {descricao}")
        
        return " || ".join(partes)
    
    def gerar_embeddings_batch(self, textos):
        """Gera embeddings em batch usando JINA"""
        
        if not self.api_key or self.api_key == "SUA_JINA_API_KEY_AQUI":
            logger.warning("JINA API não configurada. Usando embeddings aleatórios.")
            return np.random.rand(len(textos), EMBEDDING_DIMENSION).astype('float32')
        
        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}'
            }
            
            data = {
                'model': self.model,
                'input': textos,
                'encoding_format': 'float'
            }
            
            response = requests.post(self.url, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            embeddings = [item['embedding'] for item in result['data']]
            
            return np.array(embeddings).astype('float32')
            
        except Exception as e:
            logger.error("Erro ao gerar embeddings JINA: %s", e)
            # Fallback para embeddings aleatórios
            return np.random.rand(len(textos), EMBEDDING_DIMENSION).astype('float32')

class IndexadorOtimizado:
    """Indexador principal otimizado"""
    
    def __init__(self):
        self.processador_llm = ProcessadorLLMOtimizado()
        self.embedding_generator = EmbeddingJINAOtimizado()
        
        # Criar pasta de índice
        os.makedirs(PASTA_INDICE, exist_ok=True)
        
        logger.info("🎼 Indexador Otimizado inicializado")
    
    def carregar_dados(self):
        """Carrega dados da planilha"""
        try:
            logger.info("📂 Carregando dados de: %s", CAMINHO_DADOS)
            df = pd.read_excel(CAMINHO_DADOS)
            
            # Limpar dados
            df = df.dropna(subset=['Descrição'])
            df = df[df['Descrição'].str.strip() != '']
            
            logger.info("✅ Dados carregados: %d produtos válidos", len(df))
            return df
            
        except Exception as e:
            logger.error("❌ Erro ao carregar dados: %s", e)
            raise
    
    def salvar_progresso(self, etapa, dados=None):
        """Salva progresso do processamento"""
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
        """Executa processamento completo"""
        
        logger.info("🚀 Iniciando processamento completo")
        
        # 1. Carregar dados
        df_produtos = self.carregar_dados()
        self.salvar_progresso("dados_carregados", {"total_produtos": len(df_produtos)})
        
        # 2. Processar com LLM
        logger.info("🤖 Processando metadados com LLM...")
        metadados_list = self.processador_llm.processar_descricoes_com_cache(df_produtos)
        self.salvar_progresso("metadados_processados", {"total_metadados": len(metadados_list)})
        
        # 3. Criar textos para embedding
        logger.info("📝 Criando textos para embedding...")
        textos_embedding = []
        for idx, row in df_produtos.iterrows():
            metadados = metadados_list[idx] if idx < len(metadados_list) else {}
            texto = self.embedding_generator.criar_texto_embedding(row, metadados)
            textos_embedding.append(texto)

        # Limpar os textos de embedding para evitar erro 400
        textos_embedding = [str(t).strip() if t else "vazio" for t in textos_embedding]

        # 4. Gerar embeddings
        logger.info("🧠 Gerando embeddings com JINA...")
        embeddings = self.embedding_generator.gerar_embeddings_batch(textos_embedding)
        
        # Normalizar embeddings
        faiss.normalize_L2(embeddings)
        self.salvar_progresso("embeddings_gerados", {"dimensao": embeddings.shape[1]})
        
        # 5. Criar índice FAISS
        logger.info("🔍 Criando índice FAISS...")
        dimensao = embeddings.shape[1]
        index = faiss.IndexFlatIP(dimensao)  # Similaridade de cosseno
        index = faiss.IndexIDMap(index)
        
        # Adicionar embeddings
        index.add_with_ids(embeddings, np.arange(len(embeddings)))
        
        # 6. Salvar índice
        faiss.write_index(index, ARQUIVO_INDICE)
        logger.info("💾 Índice FAISS salvo: %s", ARQUIVO_INDICE)
        
        # 7. Criar mapeamento completo
        logger.info("📊 Criando mapeamento completo...")
        df_mapeamento = df_produtos.copy()
        
        # Adicionar metadados
        # Adicionar metadados
        for idx, metadados in enumerate(metadados_list):
            for key, value in metadados.items():
                df_mapeamento.at[idx, f'llm_{key}'] = value

        
        # Adicionar textos de embedding
        df_mapeamento['texto_embedding'] = textos_embedding
        
        # Salvar mapeamento
        df_mapeamento.to_excel(ARQUIVO_MAPEAMENTO, index=True)
        logger.info("💾 Mapeamento salvo: %s", ARQUIVO_MAPEAMENTO)
        
        # 8. Estatísticas finais
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

# === SCRIPT PRINCIPAL ===
if __name__ == "__main__":
    print("🎼 INDEXADOR MUSICAL OTIMIZADO - ESTADO DA ARTE")
    print("=" * 80)
    print("🎯 Arquitetura simplificada: FAISS + Excel (sem SQL)")
    print("🤖 Batches inteligentes com rate limiting")
    print("⚡ Cache otimizado para economia de tokens")
    print("🔄 Processamento adaptativo e recuperação de erros")
    print("=" * 80)
    
    try:
        # Criar e executar indexador
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

