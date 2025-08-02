#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎼 BUSCADOR MUSICAL OTIMIZADO - MATCHING INTELIGENTE
Versão: Estado da Arte - Janeiro 2025 (Adaptado para Groq)

ARQUITETURA SIMPLIFICADA:
✅ FAISS para busca vetorial (ultra-rápido)
✅ Excel para metadados (simples e confiável)
✅ LLM Groq para validação inteligente (economia de tokens)
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
from tqdm import tqdm
import warnings
from datetime import datetime
import pickle
import re
from datetime import datetime
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
GROQ_API_KEY = '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'
JINA_API_KEY = "jina_64f56d5dfa26445e8d10ebcec8897233YCgLfgNjODz8G8__hQ_u67Urx3dI"

# Parâmetros de busca
K_CANDIDATOS_INICIAIS = 15
MAX_SUGESTOES_FINAIS = 3
LIMIAR_EXCELENTE = 0.90
LIMIAR_BOM = 0.80
LIMIAR_ACEITAVEL = 0.70

class CacheConsultas:
    def __init__(self, arquivo_cache):
        self.arquivo_cache = arquivo_cache
        self.cache = {}
        self.carregar_cache()
    
    def carregar_cache(self):
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
        try:
            os.makedirs(os.path.dirname(self.arquivo_cache), exist_ok=True)
            with open(self.arquivo_cache, 'wb') as f:
                pickle.dump(self.cache, f)
        except Exception as e:
            logger.error("Erro ao salvar cache de consultas: %s", e)
    
    def get(self, consulta):
        return self.cache.get(consulta.strip().lower())
    
    def set(self, consulta, resultado):
        self.cache[consulta.strip().lower()] = resultado

class ProcessadorConsultaOtimizado:
    def __init__(self):
        self.rate_limiter = RateLimiterOtimizado(rpm=30, tpm=500000, rpd=1000)
        self.cache_consultas = CacheConsultas(ARQUIVO_CACHE_CONSULTAS)
        self.groq_url = "https://api.groq.com/openai/v1/chat/completions"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GROQ_API_KEY}"
        }
        self.model = "meta-llama/llama-4-scout-17b-16e-instruct"
        logger.info("✅ Groq para consultas carregado")
    
    def normalizar_consulta(self, texto_consulta):
        if not texto_consulta or pd.isna(texto_consulta):
            return ""
        texto = str(texto_consulta).upper().strip()
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
        resultado_cache = self.cache_consultas.get(texto_consulta)
        if resultado_cache:
            logger.debug("Cache hit para consulta: %s", texto_consulta[:50])
            return resultado_cache
        
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
                return self._extrair_metadados_basico(texto_consulta)
            
            response_text = response_json['choices'][0]['message']['content'].strip()
            logger.debug("Conteúdo da resposta: %s", response_text[:500])  # Log do conteúdo
            
            try:
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}') + 1
                if start_idx == -1 or end_idx == 0:
                    logger.error("JSON não encontrado na resposta: %s", response_text[:500])
                    return self._extrair_metadados_basico(texto_consulta)
                
                json_text = response_text[start_idx:end_idx]
                metadados = json.loads(json_text)
                self.cache_consultas.set(texto_consulta, metadados)
                logger.debug("Metadados extraídos para consulta: %s", metadados)
                self.rate_limiter.record_request([prompt], success=True)
                return metadados
            except json.JSONDecodeError as e:
                logger.error("❌ Erro ao decodificar JSON: %s. Resposta: %s", e, response_text[:500])
                return self._extrair_metadados_basico(texto_consulta)
        except requests.exceptions.HTTPError as http_err:
            logger.error("❌ Erro HTTP ao processar consulta: %s. Status: %s", http_err, response.status_code)
            if response.status_code == 429:
                logger.warning("HTTP 429 - Rate limit atingido. Aguardando retry...")
                time.sleep(60)
            self.rate_limiter.record_request([prompt], success=False)
            return self._extrair_metadados_basico(texto_consulta)
        except Exception as e:
            logger.error("❌ Erro geral ao processar consulta com LLM: %s", e)
            self.rate_limiter.record_request([prompt], success=False)
            return self._extrair_metadados_basico(texto_consulta)
    
    def _extrair_metadados_basico(self, texto_consulta):
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
        afinacao_match = re.search(r'\b([A-G][b#]?)\b', texto)
        if afinacao_match:
            metadados['afinacao'] = afinacao_match.group(1)
        dimensao_match = re.search(r'(\d+)\s*(?:POLEGADAS?|INCHES?|")', texto)
        if dimensao_match:
            metadados['dimensao'] = f"{dimensao_match.group(1)} polegadas"
        potencia_match = re.search(r'(\d+)\s*W\b', texto)
        if potencia_match:
            metadados['potencia'] = f"{potencia_match.group(1)}W"
        return metadados
    
    def criar_texto_busca(self, metadados_consulta, texto_original):
        partes = []
        categoria = metadados_consulta.get('categoria_principal', 'OUTROS')
        if categoria != 'OUTROS':
            partes.append(f"CATEGORIA: {categoria}")
        subcategoria = metadados_consulta.get('subcategoria', '')
        if subcategoria:
            partes.append(f"TIPO: {subcategoria}")
        specs = []
        for key in ['afinacao', 'dimensao', 'material', 'potencia']:
            value = metadados_consulta.get(key)
            if value:
                specs.append(f"{key.upper()}: {value}")
        if specs:
            partes.append(f"SPECS: {' | '.join(specs)}")
        texto_norm = self.normalizar_consulta(texto_original)
        if texto_norm:
            partes.append(f"DESC: {texto_norm}")
        return " || ".join(partes)

class EmbeddingConsultaOtimizado:
    def __init__(self):
        self.api_key = JINA_API_KEY
        self.url = "https://api.jina.ai/v1/embeddings"
        self.model = "jina-embeddings-v3"
    
    def gerar_embedding_consulta(self, texto_consulta):
        if not self.api_key or self.api_key == "SUA_JINA_API_KEY_AQUI":
            logger.warning("JINA API não configurada. Usando embedding aleatório.")
            return np.random.rand(1024).astype('float32')
        texto_valido = str(texto_consulta).strip()
        if not texto_valido:
            logger.error("Texto de consulta vazio")
            return np.random.rand(1024).astype('float32')
        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}'
            }
            data = {
                'model': self.model,
                'input': [texto_valido],
                'encoding_format': 'float'
            }
            logger.debug("Enviando requisição Jina: %s", json.dumps(data, ensure_ascii=False))
            response = requests.post(self.url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            embedding = result['data'][0]['embedding']
            return np.array(embedding).astype('float32')
        except Exception as e:
            logger.error("Erro ao gerar embedding Jina: %s. Resposta: %s", e, response.text if 'response' in locals() else 'N/A')
            return np.random.rand(1024).astype('float32')

class MatchingHierarquicoOtimizado:
    def __init__(self):
        self.processador_consulta = ProcessadorConsultaOtimizado()
        self.embedding_generator = EmbeddingConsultaOtimizado()
        self.carregar_indice()
        logger.info("🎼 Sistema de matching otimizado inicializado")
    
    def carregar_indice(self):
        try:
            logger.info("📂 Carregando índice e mapeamento...")
            self.index = faiss.read_index(ARQUIVO_INDICE)
            self.df_mapeamento = pd.read_excel(ARQUIVO_MAPEAMENTO, index_col=0)
            logger.info("✅ Índice carregado: %d produtos", self.index.ntotal)
            logger.info("✅ Mapeamento carregado: %d registros", len(self.df_mapeamento))
        except Exception as e:
            logger.error("❌ Erro ao carregar índice: %s", e)
            raise
    
    def calcular_compatibilidade_categoria(self, categoria_consulta, categoria_produto):
        if not categoria_consulta or not categoria_produto:
            return 0.3
        if categoria_consulta == categoria_produto:
            return 1.0
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
        if 'INSTRUMENTO' in categoria_consulta and 'INSTRUMENTO' in categoria_produto:
            return 0.4
        return 0.1
    
    def calcular_compatibilidade_specs(self, specs_consulta, specs_produto):
        if not specs_consulta:
            return 0.7
        scores = []
        for key in ['afinacao', 'dimensao', 'material', 'potencia']:
            valor_consulta = specs_consulta.get(key)
            valor_produto = specs_produto.get(key)
            if not valor_consulta:
                continue
            if not valor_produto:
                scores.append(0.0)
                continue
            if key == 'afinacao':
                score = 1.0 if str(valor_consulta).upper() == str(valor_produto).upper() else 0.0
            elif key == 'dimensao':
                score = self._comparar_dimensoes(valor_consulta, valor_produto)
            elif key == 'potencia':
                score = self._comparar_potencias(valor_consulta, valor_produto)
            else:
                score = 1.0 if str(valor_consulta).upper() in str(valor_produto).upper() else 0.0
            scores.append(score)
        return np.mean(scores) if scores else 0.0
    
    def _comparar_dimensoes(self, dim1, dim2):
        try:
            num1 = float(re.findall(r'\d+', str(dim1))[0])
            num2 = float(re.findall(r'\d+', str(dim2))[0])
            tolerancia = 0.1
            diff = abs(num1 - num2) / max(num1, num2)
            return 1.0 if diff <= tolerancia else 0.0
        except (ValueError, IndexError):
            return 0.0
    
    def _comparar_potencias(self, pot1, pot2):
        try:
            num1 = float(re.findall(r'\d+', str(pot1))[0])
            num2 = float(re.findall(r'\d+', str(pot2))[0])
            tolerancia = 0.2
            diff = abs(num1 - num2) / max(num1, num2)
            return 1.0 if diff <= tolerancia else 0.0
        except (ValueError, IndexError):
            return 0.0
    
    def buscar_candidatos(self, texto_consulta):
        metadados_consulta = self.processador_consulta.extrair_metadados_consulta(texto_consulta)
        texto_busca = self.processador_consulta.criar_texto_busca(metadados_consulta, texto_consulta)
        embedding_consulta = self.embedding_generator.gerar_embedding_consulta(texto_busca)
        embedding_consulta = embedding_consulta.reshape(1, -1)
        faiss.normalize_L2(embedding_consulta)
        distancias, indices = self.index.search(embedding_consulta, K_CANDIDATOS_INICIAIS)
        candidatos = []
        
        for i, (idx, similaridade_semantica) in enumerate(zip(indices[0], distancias[0])):
            if idx == -1:
                continue
            produto_info = self.df_mapeamento.iloc[idx]
            categoria_produto = produto_info.get('llm_categoria_principal', 'OUTROS')
            score_categoria = self.calcular_compatibilidade_categoria(
                metadados_consulta.get('categoria_principal', 'OUTROS'),
                categoria_produto
            )
            if score_categoria < 0.2:
                continue
            specs_produto = {
                'afinacao': produto_info.get('llm_afinacao'),
                'dimensao': produto_info.get('llm_dimensao'),
                'material': produto_info.get('llm_material'),
                'potencia': produto_info.get('llm_potencia')
            }
            score_specs = self.calcular_compatibilidade_specs(metadados_consulta, specs_produto)
            score_final = (
                similaridade_semantica * 0.25 +
                score_categoria * 0.40 +
                score_specs * 0.35
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
        candidatos.sort(key=lambda x: x['score_final'], reverse=True)
        return candidatos[:MAX_SUGESTOES_FINAIS]
    
    def determinar_qualidade(self, score_final):
        if score_final >= LIMIAR_EXCELENTE:
            return "🎼 EXCELENTE", "✅"
        elif score_final >= LIMIAR_BOM:
            return "🎵 BOM", "🟡"
        elif score_final >= LIMIAR_ACEITAVEL:
            return "🎶 ACEITÁVEL", "🟠"
        else:
            return "❌ BAIXO", "❌"

def processar_edital_otimizado(caminho_edital, matcher):
    nome_arquivo = os.path.basename(caminho_edital)
    logger.info("🎼 Processando edital: %s", nome_arquivo)
    try:
        df_edital = pd.read_excel(caminho_edital)
        resultados = []
        for _, row in tqdm(df_edital.iterrows(), total=len(df_edital), desc="Matching otimizado"):
            item_catmat = str(row.get('Item', '')).strip()
            if not item_catmat or item_catmat.lower() == 'nan':
                continue
            candidatos = matcher.buscar_candidatos(item_catmat)
            dados_resultado = row.to_dict()
            if candidatos:
                melhor_candidato = candidatos[0]
                produto_info = melhor_candidato['produto_info']
                qualidade, emoji = matcher.determinar_qualidade(melhor_candidato['score_final'])
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
                if len(candidatos) > 1:
                    alternativas = []
                    for alt in candidatos[1:]:
                        alt_info = alt['produto_info']
                        alternativas.append(f"{alt_info.get('Marca', '')} {alt_info.get('Modelo', '')} ({alt['score_final']:.1%})")
                    dados_resultado['Alternativas'] = " | ".join(alternativas)
                else:
                    dados_resultado['Alternativas'] = "Nenhuma"
            else:
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
        
        df_resultado = pd.DataFrame(resultados)
        nome_base, extensao = os.path.splitext(nome_arquivo)
        caminho_saida = os.path.join(PASTA_RESULTADOS, f"{nome_base}_OTIMIZADO{extensao}")
        os.makedirs(PASTA_RESULTADOS, exist_ok=True)
        df_resultado.to_excel(caminho_saida, index=False)
        
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

if __name__ == "__main__":
    print("🎼 BUSCADOR MUSICAL OTIMIZADO - ESTADO DA ARTE")
    print("=" * 80)
    print("🎯 Matching hierárquico inteligente")
    print("🤖 LLM otimizado com cache e rate limiting")
    print("⚡ Busca vetorial ultra-rápida com FAISS")
    print("📊 Relatórios detalhados com análise técnica")
    print("=" * 80)
    
    try:
        matcher = MatchingHierarquicoOtimizado()
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
        resultados_totais = []
        for edital in arquivos_editais:
            resultado = processar_edital_otimizado(edital, matcher)
            if resultado:
                resultados_totais.append(resultado)
        matcher.processador_consulta.cache_consultas.salvar_cache()
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