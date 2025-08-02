#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎼 BUSCADOR MUSICAL OTIMIZADO COM JINA
Versão: Estado da Arte - Agosto 2025
Autor: Arte Comercial Ltda.

FUNCIONALIDADES:
✅ Matching hierárquico com embeddings FAISS usando JINA
✅ Validação de metadados com LLM e SQLite
✅ Processamento iterativo de editais
✅ Cache para consultas repetidas
✅ Exportação estruturada para licitações
"""

import pandas as pd
import numpy as np
import faiss
import sqlite3
import os
import logging
import json
import requests
import google.generativeai as genai
from api_google import GOOGLE_API_KEY
import hashlib
from api_jina import JINA_API_KEY
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constantes
PASTA_INDICE = "indice_musical"
PASTA_EDITAIS = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\ORCAMENTOS"
PASTA_RESULTADOS = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\PROPOSTAS"
ARQUIVO_INDICE = os.path.join(PASTA_INDICE, "instrumentos.index")
ARQUIVO_MAPEAMENTO = os.path.join(PASTA_INDICE, "mapeamento.xlsx")
DB_PATH = "produtos_musicais.db"
K_CANDIDATOS = 15
MAX_SUGESTOES = 3
LIMIAR_EXCELENTE = 0.95
LIMIAR_BOM = 0.80
LIMIAR_ACEITAVEL = 0.70

class ProcessadorConsultaMusical:
    def __init__(self):
        # Carregar modelo generativo (LLM)
        self.model_generativo = None
        if GOOGLE_API_KEY != "SUA_API_KEY_AQUI":
            try:
                genai.configure(api_key=GOOGLE_API_KEY)
                self.model_generativo = genai.GenerativeModel('gemini-1.5-flash-latest')
                logger.info("Modelo Gemini carregado.")
            except Exception as e:
                logger.warning(f"Falha ao carregar Gemini: {e}. LLM desativado.")

    def gerar_hash(self, texto):
        """Gera hash MD5 para texto"""
        return hashlib.md5(texto.encode('utf-8')).hexdigest()

    def extrair_specs_com_llm(self, texto_original):
        """Extrai metadados com LLM, usando cache"""
        if not self.model_generativo:
            return {}

        texto = str(texto_original).strip()
        hash_texto = self.gerar_hash(texto)

        # Verificar cache
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT metadados FROM cache_llm WHERE hash_texto = ?", (hash_texto,))
            resultado = cursor.fetchone()
            if resultado:
                logger.info("Metadados encontrados no cache para: %s", texto[:50])
                return json.loads(resultado[0])

        # Prompt idêntico ao do indexador
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
            return metadados
        except Exception as e:
            logger.error("Erro ao extrair metadados com LLM: %s", str(e))
            return {}

    def get_jina_embedding(self, text):
        """Obtém embedding da API da JINA"""
        url = "https://api.jina.ai/v1/embeddings"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {JINA_API_KEY}"
        }
        payload = {
            "model": "jina-embeddings-v3",
            "task": "text-matching",
            "input": [text],
            "dimensions": 768,
            "normalized": True,
            "embedding_type": "float"
        }
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            embedding = data['embeddings'][0]
            return np.array(embedding, dtype=np.float32)
        except Exception as e:
            logger.error(f"Erro ao obter embedding da JINA: {e}")
            return np.zeros(768, dtype=np.float32)

    def criar_embedding(self, metadados, texto_original):
        """Cria embedding estruturado usando JINA"""
        partes = [
            f"CATEGORIA: {metadados.get('categoria_principal', 'OUTROS')}",
            f"SUBCATEGORIA: {metadados.get('subcategoria', 'OUTROS')}",
            f"ESPECIFICACOES: {json.dumps(metadados, ensure_ascii=False)}",
            f"DESCRICAO: {texto_original.strip()}"
        ]
        texto_completo = " || ".join(partes)
        return self.get_jina_embedding(texto_completo)

class MatchingMusicalHierarquico:
    def __init__(self):
        self.processador = ProcessadorConsultaMusical()
        self.index = faiss.read_index(ARQUIVO_INDICE)
        self.df_mapeamento = pd.read_excel(ARQUIVO_MAPEAMENTO)

    def calcular_compatibilidade_metadados(self, metadados_consulta, metadados_produto):
        """Calcula score de compatibilidade entre metadados"""
        score = 0.0
        pesos = {
            'categoria_principal': 0.4,
            'subcategoria': 0.3,
            'afinacao': 0.1,
            'numero_pistos_valvulas': 0.05,
            'dimensao': 0.05,
            'material': 0.05,
            'potencia': 0.05
        }
        for campo, peso in pesos.items():
            valor_consulta = metadados_consulta.get(campo)
            valor_produto = metadados_produto.get(campo)
            if valor_consulta and valor_produto and valor_consulta == valor_produto:
                score += peso
        return score

    def matching_hierarquico(self, consulta_texto):
        """Executa matching hierárquico"""
        metadados_consulta = self.processador.extrair_specs_com_llm(consulta_texto)
        embedding_consulta = self.processador.criar_embedding(metadados_consulta, consulta_texto)

        embedding_consulta = np.array([embedding_consulta]).astype('float32')
        faiss.normalize_L2(embedding_consulta)
        distancias, indices = self.index.search(embedding_consulta, K_CANDIDATOS)

        candidatos = []
        for idx, similaridade in zip(indices[0], distancias[0]):
            if idx == -1:
                continue
            produto = self.df_mapeamento.iloc[idx]
            metadados_produto = json.loads(produto['metadados'])
            score_metadados = self.calcular_compatibilidade_metadados(metadados_consulta, metadados_produto)
            score_final = similaridade * 0.5 + score_metadados * 0.5

            candidatos.append({
                'produto': produto,
                'score_final': score_final,
                'score_semantico': similaridade,
                'score_metadados': score_metadados,
                'metadados_produto': metadados_produto
            })

        candidatos.sort(key=lambda x: x['score_final'], reverse=True)
        return candidatos[:MAX_SUGESTOES]

    def determinar_qualidade(self, score_final):
        """Determina qualidade do match"""
        if score_final >= LIMIAR_EXCELENTE:
            return "EXCELENTE", "✅"
        elif score_final >= LIMIAR_BOM:
            return "BOM", "🟡"
        elif score_final >= LIMIAR_ACEITAVEL:
            return "ACEITÁVEL", "🟠"
        else:
            return "BAIXO", "❌"

def processar_edital(caminho_edital, matcher):
    """Processa edital e gera relatório"""
    df_edital = pd.read_excel(caminho_edital)
    resultados = []

    for _, row in tqdm(df_edital.iterrows(), total=len(df_edital), desc="Processando edital"):
        descricao = str(row['Descrição']) if not pd.isna(row['Descrição']) else ""
        if not descricao.strip():
            continue

        candidatos = matcher.matching_hierarquico(descricao)
        resultado = row.to_dict()

        if candidatos:
            melhor = candidatos[0]
            produto = melhor['produto']
            qualidade, emoji = matcher.determinar_qualidade(melhor['score_final'])

            resultado.update({
                'Marca Sugerida': produto['Marca'],
                'Produto Sugerido': produto['Modelo'],
                'Descrição Sugerida': produto['Descrição'],
                'Preço': produto['Valor'],
                'Compatibilidade': f"{melhor['score_final']:.1%}",
                'Qualidade': qualidade,
                'Análise': f"{emoji} Produto {qualidade.lower()}. Categoria: {produto['categoria_principal']}. Score: {melhor['score_final']:.2f}."
            })
        else:
            resultado.update({
                'Marca Sugerida': "Nenhum encontrado",
                'Produto Sugerido': "N/A",
                'Descrição Sugerida': "N/A",
                'Preço': "N/A",
                'Compatibilidade': "0%",
                'Qualidade': "BAIXO",
                'Análise': "❌ Nenhum produto compatível encontrado."
            })

        resultados.append(resultado)

    df_resultado = pd.DataFrame(resultados)
    nome_arquivo = os.path.basename(caminho_edital)
    caminho_saida = os.path.join(PASTA_RESULTADOS, f"{os.path.splitext(nome_arquivo)[0]}_MUSICAL.xlsx")
    df_resultado.to_excel(caminho_saida, index=False)
    logger.info("Resultados salvos em: %s", caminho_saida)

def main():
    matcher = MatchingMusicalHierarquico()
    arquivos_editais = [
        os.path.join(PASTA_EDITAIS, f) for f in os.listdir(PASTA_EDITAIS) if f.endswith('.xlsx')
    ]
    for edital in arquivos_editais:
        processar_edital(edital, matcher)
    logger.info("Processamento concluído!")

if __name__ == "__main__":
    main()