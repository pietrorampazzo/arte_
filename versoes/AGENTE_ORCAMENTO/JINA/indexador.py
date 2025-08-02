#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎼 INDEXADOR MUSICAL OTIMIZADO COM JINA E BATCH PROCESSING
Versão: Estado da Arte - Agosto 2025
Autor: Arte Comercial Ltda.
"""

import pandas as pd
import numpy as np
import faiss
import sqlite3
import os
import logging
import json
import hashlib
import requests
from api_google import GOOGLE_API_KEY
from api_jina import JINA_API_KEY
from rate_limiter import RateLimiter
import google.generativeai as genai
import warnings
from google.api_core import exceptions
warnings.filterwarnings('ignore')

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CAMINHO_DADOS = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\FORNECEDORES\data_base.xlsx"
PASTA_INDICE = "indice_musical"
ARQUIVO_INDICE = os.path.join(PASTA_INDICE, "instrumentos.index")
ARQUIVO_MAPEAMENTO = os.path.join(PASTA_INDICE, "mapeamento.xlsx")
DB_PATH = "produtos_musicais.db"
BATCH_SIZE = 100
ULTIMO_BATCH_ARQUIVO = "ultimo_batch.txt"

class ProcessadorMusical:
    def __init__(self):
        self.model_generativo = None
        self.rate_limiter = RateLimiter(rpm=30, tpm=1_000_000, rpd=200)
        if GOOGLE_API_KEY != "SUA_API_KEY_AQUI":
            try:
                genai.configure(api_key=GOOGLE_API_KEY)
                self.model_generativo = genai.GenerativeModel('gemini-2.0-flash-lite')
                logger.info("Modelo Gemini 2.0 Flash-Lite carregado.")
            except Exception as e:
                logger.warning(f"Falha ao carregar Gemini: {e}. LLM desativado.")
        self.iniciar_banco()

    def iniciar_banco(self):
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS cache_llm (
                        hash_texto TEXT PRIMARY KEY,
                        metadados JSON
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS produtos (
                        id_produto INTEGER PRIMARY KEY,
                        descricao TEXT,
                        marca TEXT,
                        modelo TEXT,
                        valor REAL,
                        categoria_principal TEXT,
                        subcategoria TEXT,
                        metadados JSON
                    )
                """)
            logger.info("Banco SQLite inicializado: %s", DB_PATH)
        except Exception as e:
            logger.error("Erro ao inicializar banco: %s", str(e))
            raise

    def gerar_hash(self, texto):
        return hashlib.md5(str(texto).encode('utf-8')).hexdigest()

    def extrair_specs_com_llm(self, textos, indices=None):
        if not self.model_generativo:
            logger.warning("LLM não disponível. Retornando metadados vazios.")
            return [{}] * len(textos)

        metadados_list = []
        textos_to_process = []
        indices_to_process = []
        hashes = []

        for i, texto in enumerate(textos):
            if pd.isna(texto) or texto is None or str(texto).strip().lower() == 'nan':
                logger.warning("Texto inválido na linha %s: %s", indices[i] if indices else i, texto)
                metadados_list.append({})
                continue

            texto = str(texto).strip()
            hash_texto = self.gerar_hash(texto)
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT metadados FROM cache_llm WHERE hash_texto = ?", (hash_texto,))
                resultado = cursor.fetchone()
                if resultado:
                    logger.info("Metadados encontrados no cache para linha %s: %s", 
                                indices[i] if indices else i, texto[:50])
                    metadados_list.append(json.loads(resultado[0]))
                    continue

            textos_to_process.append({"id": indices[i] if indices else i, "descricao": texto})
            indices_to_process.append(indices[i] if indices else i)
            hashes.append(hash_texto)
            metadados_list.append(None)

        if not textos_to_process:
            return metadados_list

        if not self.rate_limiter.can_make_request([item["descricao"] for item in textos_to_process]):
            logger.error("Não é possível fazer a solicitação devido a limites de API. Batch ignorado.")
            return metadados_list

        prompt = f"""
Você é um especialista... [restante do prompt permanece igual]
"""

        try:
            response = self.model_generativo.generate_content(prompt, request_options={"timeout": 120.0})
            response_text = response.text.strip()
            logger.debug("Resposta bruta do Gemini: %s", response_text[:1000])
            if not response_text or not response_text.strip().startswith('['):
                logger.error("Resposta vazia ou inválida: %s", response_text[:500])
                metadados_batch = [{}] * len(textos_to_process)
            else:
                try:
                    metadados_batch = json.loads(response_text)
                    if not isinstance(metadados_batch, list):
                        raise ValueError("Resposta não é um array de JSONs")
                    if len(metadados_batch) != len(textos_to_process):
                        logger.warning("Número de metadados (%d) não corresponde ao número de itens (%d)", 
                                      len(metadados_batch), len(textos_to_process))
                        metadados_batch = metadados_batch + [{}] * (len(textos_to_process) - len(metadados_batch))
                except json.JSONDecodeError as e:
                    logger.error("Erro ao parsear JSON: %s. Resposta: %s", str(e), response_text[:500])
                    metadados_batch = [{}] * len(textos_to_process)
                except ValueError as e:
                    logger.error("Formato inválido: %s. Resposta: %s", str(e), response_text[:500])
                    metadados_batch = [{}] * len(textos_to_process)

            self.rate_limiter.record_request([item["descricao"] for item in textos_to_process])

            with sqlite3.connect(DB_PATH) as conn:
                for texto, hash_texto, metadados in zip(textos_to_process, hashes, metadados_batch):
                    conn.execute(
                        "INSERT OR REPLACE INTO cache_llm (hash_texto, metadados) VALUES (?, ?)",
                        (hash_texto, json.dumps(metadados))
                    )

            batch_index = 0
            for i, metadados in enumerate(metadados_list):
                if metadados is None:
                    metadados_list[i] = metadados_batch[batch_index] if batch_index < len(metadados_batch) else {}
                    batch_index += 1
            logger.info("Metadados extraídos para batch de %d itens.", len(textos_to_process))
            return metadados_list

        except exceptions.DeadlineExceeded as e:
            logger.error("Timeout na chamada à API do Gemini: %s. Tentando novamente...", str(e))
            return self.extrair_specs_com_llm(textos, indices)
        except exceptions.ServiceUnavailable as e:
            logger.error("Serviço indisponível: %s. Aguardando e tentando novamente...", str(e))
            return self.extrair_specs_com_llm(textos, indices)
        except Exception as e:
            logger.error("Erro ao extrair metadados com LLM para batch: %s", str(e))
            return metadados_list

    def get_jina_embedding(self, text):
        url = "https://api.jina.ai/v1/embeddings"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {JINA_API_KEY}"}
        payload = {"model": "jina-embeddings-v3", "task": "text-matching", "input": [text], "dimensions": 768, "normalized": True, "embedding_type": "float"}
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            embedding = data['data'][0]['embedding']
            return np.array(embedding, dtype=np.float32)
        except Exception as e:
            logger.error(f"Erro ao obter embedding da JINA: {e}")
            return np.zeros(768, dtype=np.float32)

    def criar_embedding(self, metadados, texto_original, row_index=None):
        if metadados is None or pd.isna(texto_original) or texto_original is None or str(texto_original).strip().lower() == 'nan':
            logger.warning("Metadados ou texto inválido para embedding na linha %s: %s", row_index, texto_original)
            return None
        partes = [f"CATEGORIA: {metadados.get('categoria_principal', 'OUTROS')}", f"SUBCATEGORIA: {metadados.get('subcategoria', 'OUTROS')}", f"ESPECIFICACOES: {json.dumps(metadados, ensure_ascii=False)}", f"DESCRICAO: {str(texto_original).strip()}"]
        texto_completo = " || ".join(partes)
        return self.get_jina_embedding(texto_completo)

class IndexadorMusical:
    def __init__(self, processador):
        self.processador = processador
        self.index = None
        self.df_mapeamento = None
        if not os.path.exists(PASTA_INDICE):
            os.makedirs(PASTA_INDICE)
            logger.info("Diretório criado: %s", PASTA_INDICE)

    def indexar_produtos(self, caminho_dados, incremental=False):
        try:
            df = pd.read_excel(caminho_dados, engine='openpyxl')
            logger.info("Colunas encontradas: %s. Total de linhas: %d", df.columns.tolist(), len(df))

            colunas_esperadas = ['Descrição', 'Marca', 'Modelo', 'Valor']
            if not all(col in df.columns for col in colunas_esperadas):
                logger.error("Colunas obrigatórias ausentes: %s", colunas_esperadas)
                return

            ultimo_batch = 0
            if os.path.exists(ULTIMO_BATCH_ARQUIVO):
                with open(ULTIMO_BATCH_ARQUIVO, 'r') as f:
                    ultimo_batch = int(f.read().strip())

            existing_ids = set()
            if incremental and os.path.exists(DB_PATH):
                with sqlite3.connect(DB_PATH) as conn:
                    existing_ids = set(row[0] for row in conn.execute("SELECT id_produto FROM produtos").fetchall())

            embeddings = []
            novos_produtos = []
            batch_textos = []
            batch_indices = []

            total_itens = len(df)
            for idx, row in df.iterrows():
                if idx < ultimo_batch:
                    continue
                if incremental and idx in existing_ids:
                    logger.info("Ignorando linha %s (já indexada)", idx)
                    continue

                descricao = str(row['Descrição']) if not pd.isna(row['Descrição']) else ""
                batch_textos.append(descricao)
                batch_indices.append(idx)

                if len(batch_textos) >= BATCH_SIZE or (idx == len(df) - 1 and batch_textos):
                    try:
                        metadados_list = self.processador.extrair_specs_com_llm(batch_textos, batch_indices)
                        for i, (metadados, texto, idx) in enumerate(zip(metadados_list, batch_textos, batch_indices)):
                            if metadados is None or not metadados:
                                logger.warning("Metadados nulos ou vazios para linha %s, ignorando.", idx)
                                continue
                            embedding = self.processador.criar_embedding(metadados, texto, row_index=idx)
                            if embedding is None:
                                logger.warning("Embedding não gerado para linha %s", idx)
                                continue

                            embeddings.append(embedding)
                            novos_produtos.append((idx, texto, str(row['Marca']) if not pd.isna(row['Marca']) else "", str(row['Modelo']) if not pd.isna(row['Modelo']) else "", float(row['Valor']) if not pd.isna(row['Valor']) else 0.0, metadados.get('categoria_principal', 'OUTROS'), metadados.get('subcategoria', 'OUTROS'), json.dumps(metadados)))
                    except Exception as e:
                        logger.error("Erro ao processar batch (índices %d a %d): %s. Salvando progresso parcial.", batch_indices[0], batch_indices[-1], str(e))
                        with open(ULTIMO_BATCH_ARQUIVO, 'w') as f:
                            f.write(str(batch_indices[-1]))
                        continue

                    with open(ULTIMO_BATCH_ARQUIVO, 'w') as f:
                        f.write(str(idx))
                    batch_textos = []
                    batch_indices = []

            if not embeddings and not novos_produtos:
                logger.info("Nenhum produto novo para indexar. Recuperando estado atual do banco.")
                with sqlite3.connect(DB_PATH) as conn:
                    cursor = conn.execute("SELECT id_produto, descricao, marca, modelo, valor, categoria_principal, subcategoria, metadados FROM produtos")
                    novos_produtos = [(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7]) for row in cursor]
                embeddings = [self.processador.criar_embedding(json.loads(p[7]), p[1], p[0]) for p in novos_produtos if p[7] and self.processador.criar_embedding(json.loads(p[7]), p[1], p[0]) is not None]

            if not embeddings and not novos_produtos:
                logger.info("Nenhum dado para indexar.")
                return

            embeddings = np.array([e for e in embeddings if e is not None]).astype('float32')
            faiss.normalize_L2(embeddings)
            dimensao = embeddings.shape[1]

            if incremental and os.path.exists(ARQUIVO_INDICE):
                self.index = faiss.read_index(ARQUIVO_INDICE)
            else:
                self.index = faiss.IndexFlatIP(dimensao)
                self.index = faiss.IndexIDMap(self.index)

            self.index.add_with_ids(embeddings, np.array([p[0] for p in novos_produtos]).astype(np.int64))

            faiss.write_index(self.index, ARQUIVO_INDICE)
            self.df_mapeamento = pd.DataFrame({
                'id_produto': [p[0] for p in novos_produtos],
                'Descrição': [p[1] for p in novos_produtos],
                'Marca': [p[2] for p in novos_produtos],
                'Modelo': [p[3] for p in novos_produtos],
                'Valor': [p[4] for p in novos_produtos],
                'categoria_principal': [p[5] for p in novos_produtos],
                'subcategoria': [p[6] for p in novos_produtos],
                'metadados': [p[7] for p in novos_produtos]
            })
            self.df_mapeamento.to_excel(ARQUIVO_MAPEAMENTO, index=False)

            with sqlite3.connect(DB_PATH) as conn:
                for produto in novos_produtos:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO produtos
                        (id_produto, descricao, marca, modelo, valor, categoria_principal, subcategoria, metadados)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        produto
                    )
            if os.path.exists(ULTIMO_BATCH_ARQUIVO):
                os.remove(ULTIMO_BATCH_ARQUIVO)
            logger.info("Indexação concluída: %s produtos novos. Total processado: %d de %d", 
                       len(novos_produtos), len(df), total_itens)

        except Exception as e:
            logger.error("Erro durante indexação: %s", str(e))
            raise

def main():
    try:
        if not os.path.exists(CAMINHO_DADOS):
            logger.error("Arquivo não encontrado: %s", CAMINHO_DADOS)
            return

        processador = ProcessadorMusical()
        indexador = IndexadorMusical(processador)
        indexador.indexar_produtos(CAMINHO_DADOS, incremental=False)
        logger.info("Indexação concluída com sucesso!")

    except Exception as e:
        logger.error("Erro no processo principal: %s", str(e))

if __name__ == "__main__":
    main()