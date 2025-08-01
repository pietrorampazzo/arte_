#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎼 INDEXADOR DE INSTRUMENTOS MUSICAIS
Versão: Estado da Arte - Janeiro 2025
Autor: Arte Comercial Ltda. criado pra ajudar com licitações musicais

FUNCIONALIDADES:
✅ Lê data_base.xlsx e processa coluna Descrição
✅ Extrai especificações técnicas com NLP (spacy)
✅ Cria categorias automáticas com clustering
✅ Indexa no FAISS e salva metadados em SQLite
"""

import pandas as pd
import numpy as np
import faiss
import spacy
import sqlite3
import os
import re
import logging
from sklearn.cluster import KMeans
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')
import unidecode
# Verificar dependências
try:
    from sentence_transformers import SentenceTransformer
    from unidecode import unidecode
except ImportError as e:
    print(f"Erro: Módulo não encontrado. Instale com: pip install {str(e).split('named ')[-1]}")
    exit(1)

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constantes
CAMINHO_DADOS = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\FORNECEDORES\data_base.xlsx"
PASTA_INDICE = "indice_musical"
ARQUIVO_INDICE = os.path.join(PASTA_INDICE, "instrumentos.index")
ARQUIVO_MAPEAMENTO = os.path.join(PASTA_INDICE, "mapeamento.xlsx")
DB_PATH = "produtos_musicais.db"
NOME_MODELO = 'sentence-transformers/all-mpnet-base-v2'
N_CLUSTERS = 5  # Número inicial de clusters para categorização

class ProcessadorMusical:
    def __init__(self):
        # Carregar modelo de embedding
        try:
            self.model_embedding = SentenceTransformer(NOME_MODELO)
            logger.info("Modelo de embedding carregado: %s", NOME_MODELO)
        except Exception as e:
            logger.error("Erro ao carregar modelo de embedding: %s", str(e))
            raise

        # Carregar modelo NLP (spacy)
        try:
            self.nlp = spacy.load('pt_core_news_lg')
            logger.info("Modelo spacy carregado: pt_core_news_lg")
        except Exception as e:
            logger.error("Erro ao carregar spacy: %s. Instale com: pip install spacy; python -m spacy download pt_core_news_lg", str(e))
            raise

        # Dicionário de categorias iniciais
        self.categorias = {
            'INSTRUMENTO_SOPRO': ['trompete', 'saxofone', 'clarinete', 'tuba'],
            'INSTRUMENTO_PERCUSSAO': ['bumbo', 'tarol', 'prato', 'tambor'],
            'INSTRUMENTO_CORDA': ['violino', 'guitarra', 'baixo', 'violoncelo'],
            'ACESSORIO': ['boquilha', 'palheta', 'baqueta', 'corda'],
            'EQUIPAMENTO_SOM': ['caixa de som', 'amplificador', 'microfone', 'caixa ativa']
        }

        # Padrões para extração de especificações
        self.specs_tecnicas = {
            'AFINACAO': [r'afinacao\s+em\s+([A-G][b#]?)', r'([A-G][b#]?)\s+bemol'],
            'DIMENSAO': [r'(\d+\.?\d*)\s*(polegada|cm|mm)\b'],
            'MATERIAL': [r'(laca|cromado|dourado|bronze|titanio|aluminio|madeira|plastico)\b'],
            'POTENCIA': [r'(\d+)\s*(w|watts|rms)\b'],
            'CONEXAO': [r'\b(xlr|bluetooth|p10|p2)\b']
        }

        self.iniciar_banco()

    def iniciar_banco(self):
        """Inicia banco SQLite para armazenar categorias e specs"""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS categorias (
                        nome TEXT PRIMARY KEY,
                        palavras_chave TEXT
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS specs (
                        id_produto INTEGER,
                        nome TEXT,
                        valor TEXT,
                        PRIMARY KEY (id_produto, nome, valor)
                    )
                """)
                # Inicializar categorias padrão
                for cat, palavras in self.categorias.items():
                    conn.execute(
                        "INSERT OR REPLACE INTO categorias (nome, palavras_chave) VALUES (?, ?)",
                        (cat, str(palavras))
                    )
            logger.info("Banco SQLite inicializado: %s", DB_PATH)
        except Exception as e:
            logger.error("Erro ao inicializar banco: %s", str(e))
            raise

    def normalizar_texto(self, texto):
        """Normaliza texto para extração"""
        if pd.isna(texto):
            return ""
        texto_norm = unidecode(str(texto).lower())
        texto_norm = re.sub(r'[^\w\s\-\+\(\)\[\]#♭♯]', ' ', texto_norm)
        texto_norm = re.sub(r'\s+', ' ', texto_norm).strip()
        traducoes = {
            'si bemol': 'Bb', 'mi bemol': 'Eb', 'fa sustenido': 'F#',
            'pistos': 'valvulas', 'campana': 'bell', 'calibre': 'bore'
        }
        for termo, traducao in traducoes.items():
            texto_norm = texto_norm.replace(termo, traducao)
        return texto_norm

    def extrair_specs(self, texto):
        """Extrai especificações técnicas com regex e spacy"""
        texto_norm = self.normalizar_texto(texto)
        specs = defaultdict(list)

        # Extração com regex
        for spec_name, patterns in self.specs_tecnicas.items():
            for pattern in patterns:
                matches = re.findall(pattern, texto_norm, re.IGNORECASE)
                if matches:
                    specs[spec_name].extend([m if isinstance(m, str) else m[0] for m in matches])

        # Extração com spacy para entidades adicionais
        doc = self.nlp(texto_norm)
        for ent in doc.ents:
            if ent.label_ in ['PRODUCT', 'ORG', 'QUANTITY']:
                specs['ENTIDADE'].append(ent.text)

        # Deduplicar valores
        for key in specs:
            specs[key] = list(set(specs[key]))

        return dict(specs)

    def identificar_categoria(self, texto):
        """Identifica categoria com base em palavras-chave"""
        texto_norm = self.normalizar_texto(texto)
        for categoria, palavras in self.categorias.items():
            if any(palavra in texto_norm for palavra in palavras):
                return categoria
        return "OUTROS"

    def criar_embedding(self, texto, categoria, specs):
        """Cria texto estruturado para embedding"""
        texto_norm = self.normalizar_texto(texto)
        specs_texto = ' | '.join(f'{k}: {", ".join(v)}' for k, v in specs.items())
        texto_completo = f"CATEGORIA: {categoria} || SPECS: {specs_texto} || DESCRICAO: {texto_norm}".strip()
        return self.model_embedding.encode(texto_completo, normalize_embeddings=True)

    def detectar_novas_categorias(self, textos, df, indices):
        """Detecta novas categorias via clustering"""
        embeddings = self.model_embedding.encode(textos, show_progress_bar=True)
        kmeans = KMeans(n_clusters=min(N_CLUSTERS, len(textos)), random_state=42)
        labels = kmeans.fit_predict(embeddings)

        novas_categorias = defaultdict(list)
        for idx, label, texto in zip(indices, labels, textos):
            cluster_name = f"CLUSTER_{label}"
            novas_categorias[cluster_name].append(texto)
            df.at[idx, 'categoria'] = cluster_name  # Atualiza categoria no DataFrame

        # Salvar novas categorias no banco
        with sqlite3.connect(DB_PATH) as conn:
            for cluster, descricoes in novas_categorias.items():
                palavras_chave = descricoes[:3]  # Usa primeiras descrições como palavras-chave
                conn.execute(
                    "INSERT OR REPLACE INTO categorias (nome, palavras_chave) VALUES (?, ?)",
                    (cluster, str(palavras_chave))
                )

        return df

class IndexadorMusical:
    def __init__(self, processador):
        self.processador = processador
        self.index = None
        self.df_mapeamento = None
        if not os.path.exists(PASTA_INDICE):
            os.makedirs(PASTA_INDICE)
            logger.info("Diretório criado: %s", PASTA_INDICE)

    def indexar_produtos(self, caminho_dados):
        """Indexa produtos e extrai especificações"""
        try:
            logger.info("Lendo arquivo XLSX: %s", caminho_dados)
            df = pd.read_excel(caminho_dados, engine='openpyxl')
            logger.info("Colunas encontradas: %s", df.columns.tolist())

            # Verificar colunas obrigatórias
            colunas_esperadas = ['Descrição', 'Marca', 'Modelo', 'Valor']
            if not all(col in df.columns for col in colunas_esperadas):
                logger.error("Colunas obrigatórias ausentes: %s", colunas_esperadas)
                return

            # Extrair specs e categorias
            df['embedding_texto'] = df['Descrição'].apply(self.processador.normalizar_texto)
            df['categoria'] = df['Descrição'].apply(self.processador.identificar_categoria)
            df['specs'] = df['Descrição'].apply(self.processador.extrair_specs)

            # Detectar novas categorias via clustering
            textos = df['embedding_texto'].tolist()
            df = self.processador.detectar_novas_categorias(textos, df, df.index)

            # Criar embeddings
            embeddings = []
            for idx, row in df.iterrows():
                embedding = self.processador.criar_embedding(row['Descrição'], row['categoria'], row['specs'])
                embeddings.append(embedding)

            # Criar índice FAISS
            embeddings = np.array(embeddings).astype('float32')
            faiss.normalize_L2(embeddings)
            dimensao = embeddings.shape[1]
            self.index = faiss.IndexFlatIP(dimensao)
            self.index = faiss.IndexIDMap(self.index)
            self.index.add_with_ids(embeddings, df.index.values.astype(np.int64))

            # Salvar índice e mapeamento
            faiss.write_index(self.index, ARQUIVO_INDICE)
            self.df_mapeamento = df[['Marca', 'Modelo', 'Descrição', 'Valor', 'embedding_texto', 'categoria', 'specs']]
            self.df_mapeamento.to_csv(ARQUIVO_MAPEAMENTO, index=True)
            logger.info("Índice e mapeamento salvos em %s e %s", ARQUIVO_INDICE, ARQUIVO_MAPEAMENTO)

            # Salvar specs no banco
            with sqlite3.connect(DB_PATH) as conn:
                for idx, row in df.iterrows():
                    for spec_name, spec_valores in row['specs'].items():
                        for valor in spec_valores:
                            conn.execute(
                                "INSERT OR REPLACE INTO specs (id_produto, nome, valor) VALUES (?, ?, ?)",
                                (idx, spec_name, valor)
                            )

        except Exception as e:
            logger.error("Erro durante indexação: %s", str(e))
            raise

def main():
    try:
        # Verificar se o arquivo CSV existe
        if not os.path.exists(CAMINHO_DADOS):
            logger.error("Arquivo CSV não encontrado: %s", CAMINHO_DADOS)
            return

        # Inicializar processador e indexador
        processador = ProcessadorMusical()
        indexador = IndexadorMusical(processador)

        # Indexar produtos
        indexador.indexar_produtos(CAMINHO_DADOS)
        logger.info("Indexação concluída com sucesso!")

    except Exception as e:
        logger.error("Erro no processo principal: %s", str(e))

if __name__ == "__main__":
    main()