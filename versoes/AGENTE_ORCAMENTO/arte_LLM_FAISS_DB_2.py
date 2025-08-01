#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎼 INDEXADOR DE INSTRUMENTOS MUSICAIS
Versão: Estado da Arte - Janeiro 2025
Autor: Arte Comercial Ltda. criado pra ajudar com licitações musicais

FUNCIONALIDADES:
✅ Lê data_base.xlsx e processa coluna Descrição
✅ Extrai especificações técnicas com NLP (spacy) E LLM (Gemini)
✅ Cria categorias automáticas com clustering E LLM
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
from api_google import GOOGLE_API_KEY

# Importar API key para Gemini
try:
    import google.generativeai as genai
    from api_google import GOOGLE_API_KEY
except ImportError:
    GOOGLE_API_KEY = GOOGLE_API_KEY# Substitua pela sua chave real
    genai = None
    logging.warning("API Key do Google Gemini não encontrada ou módulo 'google.generativeai' não instalado. A extração via LLM será desativada.")

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
PASTA_INDICE = "indice_musical" # Manter o nome para compatibilidade com o buscador
ARQUIVO_INDICE = os.path.join(PASTA_INDICE, "instrumentos.index") # Manter o nome
ARQUIVO_MAPEAMENTO = os.path.join(PASTA_INDICE, "mapeamento.xlsx") # Manter o nome
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

        # Carregar modelo generativo (LLM)
        self.model_generativo = None
        if genai and GOOGLE_API_KEY != "SUA_API_KEY_AQUI":
            try:
                genai.configure(api_key=GOOGLE_API_KEY)
                self.model_generativo = genai.GenerativeModel('gemini-1.5-flash-latest')
                logger.info("Modelo Gemini carregado para extração de LLM.")
            except Exception as e:
                logger.warning(f"Não foi possível carregar o modelo Gemini para extração de LLM: {e}. A extração via LLM será desativada.")
        else:
            logger.warning("API Key do Google Gemini não configurada ou módulo 'google.generativeai' ausente. A extração via LLM será desativada.")


        # Dicionário de categorias iniciais (expandido para alinhar com o buscador)
        self.categorias = {
            'INSTRUMENTO_SOPRO_METAL': ['trompete', 'saxofone', 'clarinete', 'tuba', 'bombardino', 'euphonium', 'trombone', 'sousafone', 'corneta', 'flugelhorn', 'clarone'],
            'INSTRUMENTO_SOPRO_MADEIRA': ['clarinete', 'saxofone', 'flauta', 'oboé', 'fagote'],
            'INSTRUMENTO_PERCUSSAO_PELE': ['bumbo', 'tarol', 'tambor', 'caixa clara', 'surdo', 'timpano', 'quintoton'],
            'INSTRUMENTO_PERCUSSAO_METAL': ['prato', 'triangulo', 'carrilhao', 'sino'],
            'INSTRUMENTO_CORDA': ['violino', 'guitarra', 'baixo', 'violoncelo', 'viola', 'contrabaixo'],
            'ACESSORIO_SOPRO': ['boquilha', 'palheta', 'bocal', 'estante'],
            'ACESSORIO_PERCUSSAO': ['baqueta', 'malho', 'talabarte', 'colete', 'pele', 'esteira'],
            'EQUIPAMENTO_SOM': ['caixa de som', 'amplificador', 'microfone', 'caixa ativa']
        }

        # Padrões para extração de especificações (expandido para alinhar com o buscador)
        self.specs_tecnicas = {
            'AFINACAO': [r'afinacao\s+em\s+([A-G][b#]?)', r'([A-G][b#]?)\s+bemol', r'\b([A-G][b#]?)\b(?=\s|$)'],
            'DIMENSAO': [r'(\d+\.?\d*)\s*(polegada|cm|mm)\b', r'(\d+)\"', r'(\d+)\s*x\s*(\d+)\s*cm'],
            'MATERIAL': [r'(laca|cromado|dourado|bronze|titanio|aluminio|madeira|plastico|verniz|prateado|alpaca)\b'],
            'POTENCIA': [r'(\d+)\s*(w|watts|rms)\b'],
            'CONEXAO': [r'\b(xlr|bluetooth|p10|p2)\b'],
            'PISTOS': [r'(\d+)\s*pistos?', r'(\d+)\s*valvulas?'],
            'CAMPANA': [r'campana\s+de\s+(\d+\.?\d*)\s*(cm|mm|polegada)\b', r'bell\s+diameter\s+(\d+\.?\d*)'],
            'CALIBRE': [r'calibre\s+de\s+(\d+\.?\d*)\s*(mm|polegada)\b', r'bore\s+size\s+(\d+\.?\d*)']
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
            'pistos': 'valvulas', 'campana': 'bell', 'calibre': 'bore',
            'bombardino': 'tuba bombardao', 'tarol': 'caixa clara snare drum',
            'bumbo sinfonico': 'bumbo orquestra concert bass drum',
            'caixa de guerra': 'caixa clara militar snare',
            'surdo': 'surdo bass drum samba',
            'afinadores': 'tuning lugs tensores', 'esteira': 'snare wires bordao'
        }
        for termo, traducao in traducoes.items():
            texto_norm = texto_norm.replace(termo, traducao)
        return texto_norm

    def extrair_specs_com_llm(self, texto_original):
        """Extrai especificações usando LLM (Gemini)"""
        if not self.model_generativo:
            return {}

        prompt = f"""
        Você é um especialista em instrumentos musicais. Dada a descrição de um produto, extraia as seguintes especificações técnicas em formato JSON. Se uma especificação não for encontrada, omita-a ou use null.

        Especificações a extrair:
        - Categoria Principal (ex: INSTRUMENTO_SOPRO_METAL, INSTRUMENTO_PERCUSSAO_PELE, ACESSORIO_SOPRO, EQUIPAMENTO_SOM)
        - Afinação (ex: Bb, Eb, F#)
        - Número de Pistos/Válvulas (apenas números)
        - Dimensão (ex: 10 polegadas, 20x30 cm, 50mm)
        - Material (ex: laca, cromado, dourado, bronze, madeira)
        - Potência (ex: 100W, 500 RMS)
        - Conexão (ex: XLR, Bluetooth, P10)
        - Marca
        - Modelo

        Descrição do Produto: "{texto_original}"

        Formato de Saída JSON:"""
        