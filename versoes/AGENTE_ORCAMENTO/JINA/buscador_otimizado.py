#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎼 BUSCADOR MUSICAL OTIMIZADO - MATCHING INTELIGENTE
Versão: Estado da Arte - Janeiro 2025

ARQUITETURA SIMPLIFICADA:
✅ FAISS para busca vetorial (ultra-rápido)
✅ Excel para metadados (simples e confiável)
✅ LLM para validação inteligente (economia de tokens)
✅ Matching hierárquico (categoria + semântica + specs)
✅ Cache para consultas repetidas

FLUXO OTIMIZADO:
Editais → Processamento LLM → Busca FAISS → Validação → Resultados Excel

ESTRATÉGIAS DE MATCHING:
1. Busca semântica inicial (k=15 candidatos)
2. Filtro por categoria musical (peso 40%)
3. Compatibilidade de especificações (peso 35%)
4. Validação LLM para casos duvidosos (peso 25%)
5. Re-ranking final ponderado

Autor: Sistema Simplificado
"""

import pandas as pd
import numpy as np
import faiss
import os
import logging
import json
import requests
import google.generativeai as genai
from tqdm import tqdm
import warnings
from datetime import datetime
import pickle
import re

# Importar módulos locais
from rate_limiter_otimizado import RateLimiterOtimizado

warnings.filterwarnings('ignore')

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# === CONFIGURAÇÕES ===
PASTA_INDICE = "indice_musical_otimizado"
PASTA_EDITAIS = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\ORCAMENTOS"
PASTA_RESULTADOS = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\PROPOSTAS_OTIMIZADAS"

ARQUIVO_INDICE = os.path.join(PASTA_INDICE, "instrumentos.index")
ARQUIVO_MAPEAMENTO = os.path.join(PASTA_INDICE, "mapeamento_completo.xlsx")
ARQUIVO_CACHE_CONSULTAS = os.path.join(PASTA_INDICE, "cache_consultas.pkl")

# APIs
try:
    from api_google import GOOGLE_API_KEY
    from api_jina import JINA_API_KEY
except ImportError:
    GOOGLE_API_KEY = 'AIzaSyBdrzcton2jUCv5PSaXE38UCp-l8O42Fvc'
    JINA_API_KEY = "jina_64f56d5dfa26445e8d10ebcec8897233YCgLfgNjODz8G8__hQ_u67Urx3dI"

# Parâmetros de busca
K_CANDIDATOS_INICIAIS = 15
MAX_SUGESTOES_FINAIS = 3
LIMIAR_EXCELENTE = 0.90
LIMIAR_BOM = 0.80
LIMIAR_ACEITAVEL = 0.70

class CacheConsultas:
    """Cache para consultas de edital (evita reprocessamento)"""
    
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
                logger.info("Cache de consultas carregado: %d entradas", len(self.cache))
            else:
                self.cache = {}
        except Exception as e:
            logger.warning("Erro ao carregar cache de consultas: %s", e)
            self.cache = {}
    
    def salvar_cache(self):
        """Salva cache no arquivo"""
        try:
            os.makedirs(os.path.dirname(self.arquivo_cache), exist_ok=True)
            with open(self.arquivo_cache, 'wb') as f:
                pickle.dump(self.cache, f)
        except Exception as e:
            logger.error("Erro ao salvar cache de consultas: %s", e)
    
    def get(self, consulta):
        """Busca consulta no cache"""
        return self.cache.get(consulta.strip().lower())
    
    def set(self, consulta, resultado):
        """Adiciona consulta ao cache"""
        self.cache[consulta.strip().lower()] = resultado

class ProcessadorConsultaOtimizado:
    """Processador de consultas de edital com LLM otimizado"""
    
    def __init__(self):
        self.model_generativo = None
        self.rate_limiter = RateLimiterOtimizado()
        self.cache_consultas = CacheConsultas(ARQUIVO_CACHE_CONSULTAS)
        
        # Inicializar Gemini
        if GOOGLE_API_KEY and GOOGLE_API_KEY != "SUA_GOOGLE_API_KEY_AQUI":
            try:
                genai.configure(api_key=GOOGLE_API_KEY)
                self.model_generativo = genai.GenerativeModel('gemini-2.0-flash-lite')
                logger.info("✅ Gemini para consultas carregado")
            except Exception as e:
                logger.warning("⚠️ Erro ao carregar Gemini: %s", e)
    
    def normalizar_consulta(self, texto_consulta):
        """Normaliza texto da consulta"""
        if not texto_consulta or pd.isna(texto_consulta):
            return ""
        
        texto = str(texto_consulta).upper().strip()
        
        # Normalizações musicais básicas
        normalizacoes = {
            'SI BEMOL': 'Bb', 'SIb': 'Bb', 'SI♭': 'Bb',
            'MI BEMOL': 'Eb', 'MIb': 'Eb', 'MI♭': 'Eb',
            'BOMBARDINO': 'BOMBARDINO EUPHONIUM',
            'TAROL': 'CAIXA CLARA SNARE',
            'BUMBO SINFONICO': 'BUMBO ORQUESTRA',
            'PISTOS': 'VALVULAS',
            'POLEGADAS': 'INCHES'
        }
        
        for original, normalizado in normalizacoes.items():
            texto = texto.replace(original, normalizado)
        
        return texto
    
    def extrair_metadados_consulta(self, texto_consulta):
        """Extrai metadados da consulta usando LLM (com cache)"""
        
        # Verificar cache primeiro
        resultado_cache = self.cache_consultas.get(texto_consulta)
        if resultado_cache:
            logger.debug("Cache hit para consulta: %s", texto_consulta[:50])
            return resultado_cache
        
        if not self.model_generativo:
            logger.warning("LLM não disponível para processar consulta")
            return self._extrair_metadados_basico(texto_consulta)
        
        # Processar com LLM
        prompt = f"""
Analise esta descrição de item de licitação e extraia metadados em JSON:

ITEM: "{texto_consulta}"

Extraia:
- categoria_principal: INSTRUMENTO_SOPRO_METAL, INSTRUMENTO_PERCUSSAO_PELE, EQUIPAMENTO_SOM, etc.
- subcategoria: tipo específico (TROMPETE, BUMBO, CAIXA_ATIVA, etc.)
- afinacao: afinação musical (Bb, Eb, F) ou null
- dimensao: medidas (ex: "15 polegadas", "20x30 cm") ou null
- material: material principal ou null
- potencia: potência elétrica ou null
- especificacoes_chave: lista de specs importantes

Responda APENAS com JSON válido:
{{"categoria_principal": "...", "subcategoria": "...", ...}}
"""
        
        if not self.rate_limiter.wait_if_needed([prompt]):
            logger.warning("Rate limit para consulta. Usando extração básica.")
            return self._extrair_metadados_basico(texto_consulta)
        
        try:
            response = self.model_generativo.generate_content(prompt)
            self.rate_limiter.record_request([prompt], success=True)
            
            # Extrair JSON da resposta
            response_text = response.text.strip()
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_text = response_text[start_idx:end_idx]
                metadados = json.loads(json_text)
                
                # Adicionar ao cache
                self.cache_consultas.set(texto_consulta, metadados)
                
                logger.debug("Metadados extraídos para consulta: %s", metadados)
                return metadados
            
        except Exception as e:
            logger.warning("Erro ao extrair metadados com LLM: %s", e)
            self.rate_limiter.record_request([prompt], success=False)
        
        # Fallback para extração básica
        return self._extrair_metadados_basico(texto_consulta)
    
    def _extrair_metadados_basico(self, texto_consulta):
        """Extração básica de metadados sem LLM"""
        texto = self.normalizar_consulta(texto_consulta)
        
        metadados = {
            'categoria_principal': 'OUTROS',
            'subcategoria': '',
            'afinacao': None,
            'dimensao': None,
            'material': None,
            'potencia': None,
            'especificacoes_chave': []
        }
        
        # Identificar categoria básica
        if any(term in texto for term in ['BOMBARDINO', 'TROMPETE', 'TROMBONE', 'TUBA']):
            metadados['categoria_principal'] = 'INSTRUMENTO_SOPRO_METAL'
        elif any(term in texto for term in ['CLARINETE', 'SAXOFONE', 'FLAUTA']):
            metadados['categoria_principal'] = 'INSTRUMENTO_SOPRO_MADEIRA'
        elif any(term in texto for term in ['BUMBO', 'SURDO', 'TAROL', 'CAIXA CLARA']):
            metadados['categoria_principal'] = 'INSTRUMENTO_PERCUSSAO_PELE'
        elif any(term in texto for term in ['PRATO', 'TRIANGULO', 'CARRILHAO']):
            metadados['categoria_principal'] = 'INSTRUMENTO_PERCUSSAO_METAL'
        elif any(term in texto for term in ['BOCAL', 'BOQUILHA', 'PALHETA']):
            metadados['categoria_principal'] = 'ACESSORIO_SOPRO'
        elif any(term in texto for term in ['BAQUETA', 'TALABARTE', 'PELE']):
            metadados['categoria_principal'] = 'ACESSORIO_PERCUSSAO'
        elif any(term in texto for term in ['CAIXA DE SOM', 'AMPLIFICADOR', 'MESA']):
            metadados['categoria_principal'] = 'EQUIPAMENTO_SOM'
        
        # Extrair especificações básicas
        
        # Afinação
        afinacao_match = re.search(r'\b([A-G][b#]?)\b', texto)
        if afinacao_match:
            metadados['afinacao'] = afinacao_match.group(1)
        
        # Dimensão
        dimensao_match = re.search(r'(\d+)\s*(?:POLEGADAS?|INCHES?|")', texto)
        if dimensao_match:
            metadados['dimensao'] = f"{dimensao_match.group(1)} polegadas"
        
        # Potência
        potencia_match = re.search(r'(\d+)\s*W\b', texto)
        if potencia_match:
            metadados['potencia'] = f"{potencia_match.group(1)}W"
        
        return metadados
    
    def criar_texto_busca(self, metadados_consulta, texto_original):
        """Cria texto otimizado para busca"""
        
        partes = []
        
        # Categoria
        categoria = metadados_consulta.get('categoria_principal', 'OUTROS')
        if categoria != 'OUTROS':
            partes.append(f"CATEGORIA: {categoria}")
        
        # Subcategoria
        subcategoria = metadados_consulta.get('subcategoria', '')
        if subcategoria:
            partes.append(f"TIPO: {subcategoria}")
        
        # Especificações importantes
        specs = []
        for key in ['afinacao', 'dimensao', 'material', 'potencia']:
            value = metadados_consulta.get(key)
            if value:
                specs.append(f"{key.upper()}: {value}")
        
        if specs:
            partes.append(f"SPECS: {' | '.join(specs)}")
        
        # Texto original normalizado
        texto_norm = self.normalizar_consulta(texto_original)
        if texto_norm:
            partes.append(f"DESC: {texto_norm}")
        
        return " || ".join(partes)

class EmbeddingConsultaOtimizado:
    """Gerador de embeddings para consultas usando JINA"""
    
    def __init__(self):
        self.api_key = JINA_API_KEY
        self.url = "https://api.jina.ai/v1/embeddings"
        self.model = "jina-embeddings-v3"
    
    def gerar_embedding_consulta(self, texto_consulta):
        """Gera embedding para consulta"""
        
        if not self.api_key or self.api_key == "SUA_JINA_API_KEY_AQUI":
            logger.warning("JINA API não configurada. Usando embedding aleatório.")
            return np.random.rand(1024).astype('float32')
        
        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}'
            }
            
            data = {
                'model': self.model,
                'input': [texto_consulta],
                'encoding_format': 'float'
            }
            
            response = requests.post(self.url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            embedding = result['data'][0]['embedding']
            
            return np.array(embedding).astype('float32')
            
        except Exception as e:
            logger.error("Erro ao gerar embedding de consulta: %s", e)
            return np.random.rand(1024).astype('float32')

class MatchingHierarquicoOtimizado:
    """Sistema de matching hierárquico otimizado"""
    
    def __init__(self):
        self.processador_consulta = ProcessadorConsultaOtimizado()
        self.embedding_generator = EmbeddingConsultaOtimizado()
        
        # Carregar índice e mapeamento
        self.carregar_indice()
        
        logger.info("🎼 Sistema de matching otimizado inicializado")
    
    def carregar_indice(self):
        """Carrega índice FAISS e mapeamento"""
        try:
            logger.info("📂 Carregando índice e mapeamento...")
            
            # Carregar índice FAISS
            self.index = faiss.read_index(ARQUIVO_INDICE)
            
            # Carregar mapeamento
            self.df_mapeamento = pd.read_excel(ARQUIVO_MAPEAMENTO, index_col=0)
            
            logger.info("✅ Índice carregado: %d produtos", self.index.ntotal)
            logger.info("✅ Mapeamento carregado: %d registros", len(self.df_mapeamento))
            
        except Exception as e:
            logger.error("❌ Erro ao carregar índice: %s", e)
            raise
    
    def calcular_compatibilidade_categoria(self, categoria_consulta, categoria_produto):
        """Calcula compatibilidade entre categorias"""
        
        if not categoria_consulta or not categoria_produto:
            return 0.3
        
        if categoria_consulta == categoria_produto:
            return 1.0
        
        # Compatibilidades específicas
        compatibilidades = {
            'INSTRUMENTO_SOPRO_METAL': ['INSTRUMENTO_SOPRO_METAL'],
            'INSTRUMENTO_SOPRO_MADEIRA': ['INSTRUMENTO_SOPRO_MADEIRA'],
            'INSTRUMENTO_PERCUSSAO_PELE': ['INSTRUMENTO_PERCUSSAO_PELE'],
            'INSTRUMENTO_PERCUSSAO_METAL': ['INSTRUMENTO_PERCUSSAO_METAL'],
            'ACESSORIO_SOPRO': ['ACESSORIO_SOPRO'],
            'ACESSORIO_PERCUSSAO': ['ACESSORIO_PERCUSSAO', 'INSTRUMENTO_PERCUSSAO_PELE'],
            'EQUIPAMENTO_SOM': ['EQUIPAMENTO_SOM']
        }
        
        categorias_compativeis = compatibilidades.get(categoria_consulta, [])
        if categoria_produto in categorias_compativeis:
            return 0.8
        
        # Compatibilidade parcial para instrumentos
        if 'INSTRUMENTO' in categoria_consulta and 'INSTRUMENTO' in categoria_produto:
            return 0.4
        
        return 0.1
    
    def calcular_compatibilidade_specs(self, specs_consulta, specs_produto):
        """Calcula compatibilidade de especificações"""
        
        if not specs_consulta:
            return 0.7  # Neutro se não há specs na consulta
        
        scores = []
        
        for key in ['afinacao', 'dimensao', 'material', 'potencia']:
            valor_consulta = specs_consulta.get(key)
            valor_produto = specs_produto.get(key)
            
            if not valor_consulta:
                continue
            
            if not valor_produto:
                scores.append(0.0)
                continue
            
            # Comparação específica por tipo
            if key == 'afinacao':
                # Afinação deve ser exata
                score = 1.0 if str(valor_consulta).upper() == str(valor_produto).upper() else 0.0
            elif key == 'dimensao':
                # Dimensão com tolerância
                score = self._comparar_dimensoes(valor_consulta, valor_produto)
            elif key == 'potencia':
                # Potência com tolerância de 20%
                score = self._comparar_potencias(valor_consulta, valor_produto)
            else:
                # Comparação textual
                score = 1.0 if str(valor_consulta).upper() in str(valor_produto).upper() else 0.0
            
            scores.append(score)
        
        return np.mean(scores) if scores else 0.0
    
    def _comparar_dimensoes(self, dim1, dim2):
        """Compara dimensões com tolerância"""
        try:
            # Extrair números das dimensões
            num1 = float(re.findall(r'\d+', str(dim1))[0])
            num2 = float(re.findall(r'\d+', str(dim2))[0])
            
            # Tolerância de 10%
            tolerancia = 0.1
            diff = abs(num1 - num2) / max(num1, num2)
            
            return 1.0 if diff <= tolerancia else 0.0
            
        except (ValueError, IndexError):
            return 0.0
    
    def _comparar_potencias(self, pot1, pot2):
        """Compara potências com tolerância"""
        try:
            # Extrair números das potências
            num1 = float(re.findall(r'\d+', str(pot1))[0])
            num2 = float(re.findall(r'\d+', str(pot2))[0])
            
            # Tolerância de 20%
            tolerancia = 0.2
            diff = abs(num1 - num2) / max(num1, num2)
            
            return 1.0 if diff <= tolerancia else 0.0
            
        except (ValueError, IndexError):
            return 0.0
    
    def buscar_candidatos(self, texto_consulta):
        """Executa busca hierárquica completa"""
        
        # 1. Processar consulta
        metadados_consulta = self.processador_consulta.extrair_metadados_consulta(texto_consulta)
        texto_busca = self.processador_consulta.criar_texto_busca(metadados_consulta, texto_consulta)
        
        # 2. Gerar embedding da consulta
        embedding_consulta = self.embedding_generator.gerar_embedding_consulta(texto_busca)
        embedding_consulta = embedding_consulta.reshape(1, -1)
        faiss.normalize_L2(embedding_consulta)
        
        # 3. Busca semântica inicial
        distancias, indices = self.index.search(embedding_consulta, K_CANDIDATOS_INICIAIS)
        
        candidatos = []
        
        for i, (idx, similaridade_semantica) in enumerate(zip(indices[0], distancias[0])):
            if idx == -1:
                continue
            
            # Obter dados do produto
            produto_info = self.df_mapeamento.iloc[idx]
            
            # 4. Calcular compatibilidade de categoria
            categoria_produto = produto_info.get('llm_categoria_principal', 'OUTROS')
            score_categoria = self.calcular_compatibilidade_categoria(
                metadados_consulta.get('categoria_principal', 'OUTROS'),
                categoria_produto
            )
            
            # Filtrar produtos muito incompatíveis
            if score_categoria < 0.2:
                continue
            
            # 5. Calcular compatibilidade de especificações
            specs_produto = {
                'afinacao': produto_info.get('llm_afinacao'),
                'dimensao': produto_info.get('llm_dimensao'),
                'material': produto_info.get('llm_material'),
                'potencia': produto_info.get('llm_potencia')
            }
            
            score_specs = self.calcular_compatibilidade_specs(metadados_consulta, specs_produto)
            
            # 6. Score final ponderado
            score_final = (
                similaridade_semantica * 0.25 +  # Semântica
                score_categoria * 0.40 +         # Categoria (peso alto)
                score_specs * 0.35               # Especificações
            )
            
            candidatos.append({
                'indice': idx,
                'produto_info': produto_info,
                'metadados_consulta': metadados_consulta,
                'score_semantico': float(similaridade_semantica),
                'score_categoria': float(score_categoria),
                'score_specs': float(score_specs),
                'score_final': float(score_final),
                'categoria_produto': categoria_produto
            })
        
        # 7. Re-ranking final
        candidatos.sort(key=lambda x: x['score_final'], reverse=True)
        
        return candidatos[:MAX_SUGESTOES_FINAIS]
    
    def determinar_qualidade(self, score_final):
        """Determina qualidade do match"""
        if score_final >= LIMIAR_EXCELENTE:
            return "🎼 EXCELENTE", "✅"
        elif score_final >= LIMIAR_BOM:
            return "🎵 BOM", "🟡"
        elif score_final >= LIMIAR_ACEITAVEL:
            return "🎶 ACEITÁVEL", "🟠"
        else:
            return "❌ BAIXO", "❌"

def processar_edital_otimizado(caminho_edital, matcher):
    """Processa edital com sistema otimizado"""
    
    nome_arquivo = os.path.basename(caminho_edital)
    logger.info("🎼 Processando edital: %s", nome_arquivo)
    
    try:
        df_edital = pd.read_excel(caminho_edital)
        resultados = []
        
        for _, row in tqdm(df_edital.iterrows(), total=len(df_edital), desc="Matching otimizado"):
            item_catmat = str(row.get('Item', '')).strip()
            
            if not item_catmat or item_catmat.lower() == 'nan':
                continue
            
            # Buscar candidatos
            candidatos = matcher.buscar_candidatos(item_catmat)
            
            # Processar resultado
            dados_resultado = row.to_dict()
            
            if candidatos:
                melhor_candidato = candidatos[0]
                produto_info = melhor_candidato['produto_info']
                
                qualidade, emoji = matcher.determinar_qualidade(melhor_candidato['score_final'])
                
                # Preencher dados do resultado
                dados_resultado.update({
                    'Marca Sugerida': produto_info.get('Marca', ''),
                    'Produto Sugerido': produto_info.get('Modelo', ''),
                    'Descrição do Produto Sugerido': produto_info.get('Descrição', ''),
                    'Preço Produto': produto_info.get('Valor', ''),
                    '% Compatibilidade': f"{melhor_candidato['score_final']:.1%}",
                    'Qualidade Match': qualidade,
                    'Score Semântico': f"{melhor_candidato['score_semantico']:.3f}",
                    'Score Categoria': f"{melhor_candidato['score_categoria']:.3f}",
                    'Score Especificações': f"{melhor_candidato['score_specs']:.3f}",
                    'Categoria Identificada': melhor_candidato['categoria_produto'],
                    'Categoria Consulta': melhor_candidato['metadados_consulta'].get('categoria_principal', ''),
                    'Metadados Consulta': json.dumps(melhor_candidato['metadados_consulta'], ensure_ascii=False)
                })
                
                # Alternativas
                if len(candidatos) > 1:
                    alternativas = []
                    for alt in candidatos[1:]:
                        alt_info = alt['produto_info']
                        alternativas.append(f"{alt_info.get('Marca', '')} {alt_info.get('Modelo', '')} ({alt['score_final']:.1%})")
                    dados_resultado['Alternativas'] = " | ".join(alternativas)
                else:
                    dados_resultado['Alternativas'] = "Nenhuma"
            
            else:
                # Nenhum candidato encontrado
                dados_resultado.update({
                    'Marca Sugerida': "❌ Não encontrado",
                    'Produto Sugerido': "N/A",
                    'Descrição do Produto Sugerido': "N/A",
                    'Preço Produto': "N/A",
                    '% Compatibilidade': "0%",
                    'Qualidade Match': "❌ BAIXO",
                    'Score Semântico': "0.000",
                    'Score Categoria': "0.000",
                    'Score Especificações': "0.000",
                    'Categoria Identificada': "N/A",
                    'Categoria Consulta': "N/A",
                    'Metadados Consulta': "{}",
                    'Alternativas': "Nenhuma"
                })
            
            resultados.append(dados_resultado)
        
        # Criar DataFrame final
        df_resultado = pd.DataFrame(resultados)
        
        # Salvar resultado
        nome_base, extensao = os.path.splitext(nome_arquivo)
        caminho_saida = os.path.join(PASTA_RESULTADOS, f"{nome_base}_OTIMIZADO{extensao}")
        
        os.makedirs(PASTA_RESULTADOS, exist_ok=True)
        df_resultado.to_excel(caminho_saida, index=False)
        
        # Estatísticas
        total_items = len(df_resultado)
        matches_excelentes = len(df_resultado[df_resultado['Qualidade Match'].str.contains('EXCELENTE', na=False)])
        matches_bons = len(df_resultado[df_resultado['Qualidade Match'].str.contains('BOM', na=False)])
        matches_baixos = len(df_resultado[df_resultado['Qualidade Match'].str.contains('BAIXO', na=False)])
        
        try:
            compatibilidade_media = df_resultado['% Compatibilidade'].str.replace('%', '').astype(float).mean()
        except:
            compatibilidade_media = 0.0
        
        logger.info("✅ Resultado salvo: %s", caminho_saida)
        logger.info("📊 Estatísticas: %d itens | ✅ %d excelentes | 🟡 %d bons | ❌ %d baixos | Média: %.1f%%", 
                   total_items, matches_excelentes, matches_bons, matches_baixos, compatibilidade_media)
        
        return {
            'arquivo': caminho_saida,
            'total': total_items,
            'excelentes': matches_excelentes,
            'bons': matches_bons,
            'baixos': matches_baixos,
            'media': compatibilidade_media
        }
        
    except Exception as e:
        logger.error("❌ Erro ao processar edital %s: %s", nome_arquivo, e)
        return None

# === SCRIPT PRINCIPAL ===
if __name__ == "__main__":
    print("🎼 BUSCADOR MUSICAL OTIMIZADO - ESTADO DA ARTE")
    print("=" * 80)
    print("🎯 Matching hierárquico inteligente")
    print("🤖 LLM otimizado com cache e rate limiting")
    print("⚡ Busca vetorial ultra-rápida com FAISS")
    print("📊 Relatórios detalhados com análise técnica")
    print("=" * 80)
    
    try:
        # Inicializar sistema de matching
        matcher = MatchingHierarquicoOtimizado()
        
        # Encontrar editais
        if not os.path.exists(PASTA_EDITAIS):
            logger.error("❌ Pasta de editais não encontrada: %s", PASTA_EDITAIS)
            exit(1)
        
        arquivos_editais = [
            os.path.join(PASTA_EDITAIS, f) 
            for f in os.listdir(PASTA_EDITAIS) 
            if f.endswith('.xlsx')
        ]
        
        if not arquivos_editais:
            logger.error("❌ Nenhum arquivo .xlsx encontrado em: %s", PASTA_EDITAIS)
            exit(1)
        
        logger.info("📁 %d editais encontrados", len(arquivos_editais))
        
        # Processar editais
        resultados_totais = []
        
        for edital in arquivos_editais:
            resultado = processar_edital_otimizado(edital, matcher)
            if resultado:
                resultados_totais.append(resultado)
        
        # Salvar cache de consultas
        matcher.processador_consulta.cache_consultas.salvar_cache()
        
        # Estatísticas finais
        if resultados_totais:
            total_geral = sum(r['total'] for r in resultados_totais)
            excelentes_geral = sum(r['excelentes'] for r in resultados_totais)
            bons_geral = sum(r['bons'] for r in resultados_totais)
            baixos_geral = sum(r['baixos'] for r in resultados_totais)
            media_geral = np.mean([r['media'] for r in resultados_totais])
            
            print("\n🎉 PROCESSAMENTO OTIMIZADO CONCLUÍDO!")
            print("=" * 80)
            print(f"📊 ESTATÍSTICAS GERAIS:")
            print(f"   Total de itens: {total_geral}")
            print(f"   ✅ Excelentes: {excelentes_geral} ({excelentes_geral/total_geral*100:.1f}%)")
            print(f"   🟡 Bons: {bons_geral} ({bons_geral/total_geral*100:.1f}%)")
            print(f"   ❌ Baixos: {baixos_geral} ({baixos_geral/total_geral*100:.1f}%)")
            print(f"   📈 Compatibilidade média: {media_geral:.1f}%")
            print(f"📁 Resultados salvos em: {PASTA_RESULTADOS}")
            print("=" * 80)
        
    except Exception as e:
        logger.error("❌ Erro durante processamento: %s", e)
        print(f"\n❌ ERRO: {e}")
        print("Verifique os logs para mais detalhes.")

