"""
🎼 INDEXADOR MUSICAL OTIMIZADO
Versão: Estado da Arte - Agosto 2025
Autor: Arte Comercial Ltda.

FUNCIONALIDADES:
✅ Lê data_base.xlsx e processa descrições com LLM
✅ Extrai metadados estruturados em JSON
✅ Cache em SQLite para evitar reprocessamento
✅ Indexa embeddings no FAISS
✅ Suporte incremental para novos produtos
"""

import pandas as pd
import numpy as np
import faiss
import sqlite3
import os
import logging
import json
import hashlib
from sentence_transformers import SentenceTransformer
from collections import defaultdict
import google.generativeai as genai
from api_google import GOOGLE_API_chave as GOOGLE_API_KEY
import warnings
warnings.filterwarnings('ignore')

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constantes
CAMINHO_DADOS = r"G:\Meu Drive\arte_comercial\base_produtos.xlsx"
PASTA_INDICE = "indice_musical"
ARQUIVO_INDICE = os.path.join(PASTA_INDICE, "instrumentos.index")
ARQUIVO_MAPEAMENTO = os.path.join(PASTA_INDICE, "mapeamento.xlsx")
DB_PATH = "produtos_musicais.db"
NOME_MODELO = 'sentence-transformers/all-mpnet-base-v2'

class ProcessadorMusical:
    def __init__(self):
        # Carregar modelo de embedding
        self.model_embedding = SentenceTransformer(NOME_MODELO)
        logger.info("Modelo de embedding carregado: %s", NOME_MODELO)

        # Carregar modelo generativo (LLM)
        self.model_generativo = None
        if GOOGLE_API_KEY != "SUA_API_KEY_AQUI":
            try:
                genai.configure(api_key=GOOGLE_API_KEY)
                self.model_generativo = genai.GenerativeModel('gemini-2.5-flash')
                logger.info("Modelo Gemini carregado.")
            except Exception as e:
                logger.warning(f"Falha ao carregar Gemini: {e}. LLM desativado.")
        else:
            logger.warning("API Key do Gemini não configurada. LLM desativado.")

        self.iniciar_banco()

    def iniciar_banco(self):
        """Inicia banco SQLite para cache e metadados"""
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
        """Gera hash MD5 para texto"""
        return hashlib.md5(str(texto).encode('utf-8')).hexdigest()

    def extrair_specs_com_llm(self, texto_original, row_index=None):
        """Extrai metadados com LLM, usando cache"""
        if not self.model_generativo:
            logger.warning("LLM não disponível. Retornando metadados vazios.")
            return {}

        # Validar texto_original
        if pd.isna(texto_original) or texto_original is None:
            logger.warning("Texto inválido (NaN ou None) na linha %s", row_index)
            return {}
        
        texto = str(texto_original).strip()
        if not texto or texto.lower() == 'nan':
            logger.warning("Texto vazio ou inválido na linha %s: %s", row_index, texto)
            return {}

        hash_texto = self.gerar_hash(texto)

        # Verificar cache
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT metadados FROM cache_llm WHERE hash_texto = ?", (hash_texto,))
            resultado = cursor.fetchone()
            if resultado:
                logger.info("Metadados encontrados no cache para linha %s: %s", row_index, texto[:50])
                return json.loads(resultado[0])

        # Prompt para LLM
        prompt = f"""
        Você é um especialista em instrumentos musicais, equipamentos de áudio e acessórios para licitações públicas. Dada a descrição de um produto, extraia metadados técnicos em formato JSON, incluindo todas as especificações relevantes, mesmo que não listadas explicitamente. Se uma informação não estiver presente, use null. Priorize precisão e completeza.

        **Campos a Extrair:**
        - categoria_principal (ex.: INSTRUMENTO_SOPRO_METAL, EQUIPAMENTO_SOM, ACESSORIO_PERCUSSAO)
        - subcategoria (ex.: TROMPETE, CAIXA_ATIVA, BAQUETA)
        - afinacao (ex.: Bb, Eb, null)
        - numero_pistos_valvulas (ex.: 3, null)
        - dimensao (ex.: 15 polegadas, 20x30 cm, null)
        - material (ex.: bronze, madeira, null)
        - potencia (ex.: 400W RMS, null)
        - conexao (ex.: XLR, Bluetooth, null)
        - voltagem (ex.: bivolt, 127V, null)
        - numero_cordas (ex.: 6, null)
        - marca (ex.: Yamaha, JBL, null)
        - modelo (ex.: YTR-2330, EON715, null)
        - outras_especificacoes (dicionário com specs adicionais, ex.: {{"campana": "123mm", "calibre": "0.459 polegadas"}})

        **Descrição do Produto:**
        "{texto}"

        **Formato de Saída:**
        {{
          "categoria_principal": "...",
          "subcategoria": "...",
          "afinacao": "...",
          "numero_pistos_valvulas": "...",
          "dimensao": "...",
          "material": "...",
          "potencia": "...",
          "conexao": "...",
          "voltagem": "...",
          "numero_cordas": "...",
          "marca": "...",
          "modelo": "...",
          "outras_especificacoes": {{...}}
        }}
        """

        try:
            response = self.model_generativo.generate_content(prompt)
            metadados = json.loads(response.text.strip('```json\n').strip('\n```'))
            # Salvar no cache
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO cache_llm (hash_texto, metadados) VALUES (?, ?)",
                    (hash_texto, json.dumps(metadados))
                )
            logger.info("Metadados extraídos para linha %s: %s", row_index, texto[:50])
            return metadados
        except Exception as e:
            logger.error("Erro ao extrair metadados com LLM na linha %s: %s", row_index, str(e))
            return {}

    def criar_embedding(self, metadados, texto_original, row_index=None):
        """Cria embedding estruturado"""
        if pd.isna(texto_original) or texto_original is None or str(texto_original).strip().lower() == 'nan':
            logger.warning("Texto inválido para embedding na linha %s: %s", row_index, texto_original)
            return None

        partes = [
            f"CATEGORIA: {metadados.get('categoria_principal', 'OUTROS')}",
            f"SUBCATEGORIA: {metadados.get('subcategoria', 'OUTROS')}",
            f"ESPECIFICACOES: {json.dumps(metadados, ensure_ascii=False)}",
            f"DESCRICAO: {str(texto_original).strip()}"
        ]
        texto_completo = " || ".join(partes)
        return self.model_embedding.encode(texto_completo, normalize_embeddings=True)

class IndexadorMusical:
    def __init__(self, processador):
        self.processador = processador
        self.index = None
        self.df_mapeamento = None
        if not os.path.exists(PASTA_INDICE):
            os.makedirs(PASTA_INDICE)
            logger.info("Diretório criado: %s", PASTA_INDICE)

    def indexar_produtos(self, caminho_dados, incremental=False):
        """Indexa produtos com suporte incremental"""
        try:
            df = pd.read_excel(caminho_dados, engine='openpyxl')
            logger.info("Colunas encontradas: %s", df.columns.tolist())

            # Verificar colunas obrigatórias
            colunas_esperadas = ['DESCRICAO', 'Marca', 'Modelo', 'Valor']
            if not all(col in df.columns for col in colunas_esperadas):
                logger.error("Colunas obrigatórias ausentes: %s", colunas_esperadas)
                return

            # Carregar produtos existentes (para modo incremental)
            existing_ids = set()
            if incremental and os.path.exists(DB_PATH):
                with sqlite3.connect(DB_PATH) as conn:
                    existing_ids = set(
                        row[0] for row in conn.execute("SELECT id_produto FROM produtos").fetchall()
                    )

            embeddings = []
            novos_produtos = []
            for idx, row in df.iterrows():
                if incremental and idx in existing_ids:
                    logger.info("Ignorando linha %s (já indexada)", idx)
                    continue

                # Processar descrição
                metadados = self.processador.extrair_specs_com_llm(row['DESCRICAO'], row_index=idx)
                embedding = self.processador.criar_embedding(metadados, row['DESCRICAO'], row_index=idx)
                
                if embedding is None:
                    logger.warning("Embedding não gerado para linha %s", idx)
                    continue

                embeddings.append(embedding)
                novos_produtos.append((
                    idx,
                    str(row['DESCRICAO']) if not pd.isna(row['DESCRICAO']) else "",
                    str(row['Marca']) if not pd.isna(row['Marca']) else "",
                    str(row['Modelo']) if not pd.isna(row['Modelo']) else "",
                    float(row['Valor']) if not pd.isna(row['Valor']) else 0.0,
                    metadados.get('categoria_principal', 'OUTROS'),
                    metadados.get('subcategoria', 'OUTROS'),
                    json.dumps(metadados)
                ))

            if not embeddings:
                logger.info("Nenhum produto novo para indexar.")
                return

            # Criar ou atualizar índice FAISS
            embeddings = np.array(embeddings).astype('float32')
            faiss.normalize_L2(embeddings)
            dimensao = embeddings.shape[1]

            if incremental and os.path.exists(ARQUIVO_INDICE):
                self.index = faiss.read_index(ARQUIVO_INDICE)
            else:
                self.index = faiss.IndexFlatIP(dimensao)
                self.index = faiss.IndexIDMap(self.index)

            self.index.add_with_ids(embeddings, np.array([p[0] for p in novos_produtos]).astype(np.int64))

            # Salvar índice e mapeamento
            faiss.write_index(self.index, ARQUIVO_INDICE)
            self.df_mapeamento = pd.DataFrame({
                'id_produto': [p[0] for p in novos_produtos],
                'DESCRICAO': [p[1] for p in novos_produtos],
                'Marca': [p[2] for p in novos_produtos],
                'Modelo': [p[3] for p in novos_produtos],
                'Valor': [p[4] for p in novos_produtos],
                'categoria_principal': [p[5] for p in novos_produtos],
                'subcategoria': [p[6] for p in novos_produtos],
                'metadados': [p[7] for p in novos_produtos]
            })
            self.df_mapeamento.to_excel(ARQUIVO_MAPEAMENTO, index=False)

            # Salvar no banco
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
            logger.info("Indexação concluída: %s produtos novos", len(novos_produtos))

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
        indexador.indexar_produtos(CAMINHO_DADOS, incremental=True)
        logger.info("Indexação concluída com sucesso!")

    except Exception as e:
        logger.error("Erro no processo principal: %s", str(e))

if __name__ == "__main__":
    main()