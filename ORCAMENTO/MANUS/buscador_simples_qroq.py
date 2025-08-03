#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔍 BUSCADOR SIMPLES GROQ - FUNCIONAL
Versão: Simplificada - Janeiro 2025

OBJETIVO: Buscar produtos usando embeddings gerados
✅ Carrega índice FAISS e mapeamento
✅ Processa consultas de edital com Groq
✅ Busca semântica rápida
✅ Gera relatórios de matching
✅ Sistema completo e funcional

FOCO: SIMPLICIDADE E FUNCIONALIDADE
Complementa processador_simples_groq.py + gerador_embeddings_simples.py

Autor: Sistema Simplificado
"""

import pandas as pd
import numpy as np
import faiss
import os
import logging
import json
import requests
import time
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import pickle
import hashlib

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# === CONFIGURAÇÕES ===
PASTA_INDICE = "indice_simples"
PASTA_EDITAIS = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\ORCAMENTOS"
PASTA_RESULTADOS = "resultados_busca"

# Arquivos do índice
ARQUIVO_INDICE_FAISS = os.path.join(PASTA_INDICE, "produtos.index")
ARQUIVO_MAPEAMENTO = os.path.join(PASTA_INDICE, "mapeamento.xlsx")
ARQUIVO_CACHE_CONSULTAS = os.path.join(PASTA_RESULTADOS, "cache_consultas.pkl")

# API Groq
GROQ_API_KEY = "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"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODELO_GROQ = "meta-llama/llama-3.1-70b-versatile"

# Modelo de embeddings (mesmo usado na indexação)
MODELO_EMBEDDING = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Parâmetros de busca
K_CANDIDATOS = 10
MAX_SUGESTOES = 3
LIMIAR_BOM = 0.75
LIMIAR_ACEITAVEL = 0.60

class CacheConsultas:
    """Cache simples para consultas de edital"""
    
    def __init__(self, arquivo_cache):
        self.arquivo_cache = arquivo_cache
        self.cache = {}
        self.carregar()
    
    def carregar(self):
        """Carrega cache se existir"""
        try:
            if os.path.exists(self.arquivo_cache):
                with open(self.arquivo_cache, 'rb') as f:
                    self.cache = pickle.load(f)
                logger.info(f"Cache de consultas carregado: {len(self.cache)} entradas")
        except Exception as e:
            logger.warning(f"Erro ao carregar cache de consultas: {e}")
            self.cache = {}
    
    def salvar(self):
        """Salva cache"""
        try:
            os.makedirs(os.path.dirname(self.arquivo_cache), exist_ok=True)
            with open(self.arquivo_cache, 'wb') as f:
                pickle.dump(self.cache, f)
        except Exception as e:
            logger.error(f"Erro ao salvar cache de consultas: {e}")
    
    def get(self, consulta):
        """Busca consulta no cache"""
        hash_consulta = hashlib.md5(consulta.strip().lower().encode()).hexdigest()
        return self.cache.get(hash_consulta)
    
    def set(self, consulta, resultado):
        """Adiciona consulta ao cache"""
        hash_consulta = hashlib.md5(consulta.strip().lower().encode()).hexdigest()
        self.cache[hash_consulta] = resultado

class ProcessadorConsultaGroq:
    """Processador de consultas usando Groq"""
    
    def __init__(self):
        self.cache = CacheConsultas(ARQUIVO_CACHE_CONSULTAS)
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GROQ_API_KEY}"
        }
        self.total_requests = 0
        self.total_cache_hits = 0
        
        logger.info("🤖 Processador de consultas Groq inicializado")
    
    def processar_consulta(self, texto_consulta):
        """Processa consulta de edital com Groq"""
        
        # Verificar cache primeiro
        resultado_cache = self.cache.get(texto_consulta)
        if resultado_cache:
            self.total_cache_hits += 1
            logger.debug(f"Cache hit para consulta: {texto_consulta[:50]}")
            return resultado_cache
        
        # Processar com Groq
        prompt_sistema = """Você é um especialista em instrumentos musicais e equipamentos de áudio para licitações.

TAREFA: Analise esta descrição de item de licitação e extraia metadados em JSON.

CATEGORIAS:
- INSTRUMENTO_SOPRO_METAL (trompete, bombardino, trombone, tuba)
- INSTRUMENTO_SOPRO_MADEIRA (clarinete, saxofone, flauta)
- INSTRUMENTO_PERCUSSAO_PELE (bumbo, surdo, tarol, caixa clara)
- INSTRUMENTO_PERCUSSAO_METAL (prato, triângulo, carrilhão)
- ACESSORIO_SOPRO (bocal, boquilha, palheta)
- ACESSORIO_PERCUSSAO (baqueta, talabarte, pele)
- EQUIPAMENTO_SOM (caixa de som, amplificador, mesa)
- OUTROS (não identificado)

CAMPOS JSON:
- categoria_principal: uma das categorias acima
- subcategoria: tipo específico
- afinacao: afinação musical ou null
- dimensao: medidas principais ou null
- material: material principal ou null
- potencia: potência elétrica ou null
- especificacoes_chave: lista de specs importantes

Responda APENAS com JSON válido."""

        prompt_usuario = f"ITEM DE LICITAÇÃO: {texto_consulta}"
        
        payload = {
            "model": MODELO_GROQ,
            "messages": [
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario}
            ],
            "temperature": 0.1,
            "max_tokens": 1000
        }
        
        try:
            response = requests.post(
                GROQ_URL,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content'].strip()
                
                # Extrair JSON
                try:
                    start_idx = content.find('{')
                    end_idx = content.rfind('}') + 1
                    
                    if start_idx != -1 and end_idx != -1:
                        json_text = content[start_idx:end_idx]
                        metadados = json.loads(json_text)
                        
                        # Adicionar ao cache
                        self.cache.set(texto_consulta, metadados)
                        self.total_requests += 1
                        
                        return metadados
                
                except json.JSONDecodeError:
                    logger.warning("Erro ao decodificar JSON da consulta")
            
            elif response.status_code == 429:
                logger.warning("Rate limit atingido para consulta")
                time.sleep(10)
        
        except Exception as e:
            logger.warning(f"Erro ao processar consulta: {e}")
        
        # Fallback: metadados básicos
        return self._extrair_metadados_basico(texto_consulta)
    
    def _extrair_metadados_basico(self, texto_consulta):
        """Extração básica sem LLM"""
        texto = texto_consulta.upper()
        
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
        
        # Especificações
        specs = []
        for key in ['afinacao', 'dimensao', 'material', 'potencia']:
            value = metadados_consulta.get(key)
            if value:
                specs.append(f"{key.upper()}: {value}")
        
        if specs:
            partes.append(f"SPECS: {' | '.join(specs)}")
        
        # Texto original
        if texto_original:
            partes.append(f"DESC: {texto_original.upper()}")
        
        return " || ".join(partes)

class BuscadorSimplesGroq:
    """Buscador principal usando FAISS + Groq"""
    
    def __init__(self):
        self.processador_consulta = ProcessadorConsultaGroq()
        self.carregar_indice()
        self.carregar_modelo_embedding()
        
        logger.info("🔍 Buscador simples inicializado")
    
    def carregar_indice(self):
        """Carrega índice FAISS e mapeamento"""
        
        logger.info("📂 Carregando índice e mapeamento...")
        
        # Verificar arquivos
        if not os.path.exists(ARQUIVO_INDICE_FAISS):
            raise FileNotFoundError(f"Índice não encontrado: {ARQUIVO_INDICE_FAISS}")
        
        if not os.path.exists(ARQUIVO_MAPEAMENTO):
            raise FileNotFoundError(f"Mapeamento não encontrado: {ARQUIVO_MAPEAMENTO}")
        
        # Carregar índice FAISS
        self.index = faiss.read_index(ARQUIVO_INDICE_FAISS)
        
        # Carregar mapeamento
        self.df_mapeamento = pd.read_excel(ARQUIVO_MAPEAMENTO)
        
        logger.info(f"✅ Índice carregado: {self.index.ntotal} produtos")
        logger.info(f"✅ Mapeamento carregado: {len(self.df_mapeamento)} registros")
    
    def carregar_modelo_embedding(self):
        """Carrega modelo de embeddings"""
        
        logger.info("🧠 Carregando modelo de embeddings...")
        
        try:
            self.model_embedding = SentenceTransformer(MODELO_EMBEDDING)
            logger.info(f"✅ Modelo carregado: {MODELO_EMBEDDING}")
        except Exception as e:
            logger.error(f"❌ Erro ao carregar modelo: {e}")
            raise
    
    def buscar_produtos(self, texto_consulta):
        """Busca produtos para uma consulta"""
        
        # 1. Processar consulta com Groq
        metadados_consulta = self.processador_consulta.processar_consulta(texto_consulta)
        
        # 2. Criar texto para busca
        texto_busca = self.processador_consulta.criar_texto_busca(metadados_consulta, texto_consulta)
        
        # 3. Gerar embedding da consulta
        embedding_consulta = self.model_embedding.encode([texto_busca], convert_to_numpy=True)
        embedding_consulta = embedding_consulta.astype('float32')
        faiss.normalize_L2(embedding_consulta)
        
        # 4. Buscar no índice
        distancias, indices = self.index.search(embedding_consulta, K_CANDIDATOS)
        
        # 5. Processar resultados
        candidatos = []
        
        for i, (idx, similaridade) in enumerate(zip(indices[0], distancias[0])):
            if idx == -1:
                continue
            
            # Obter dados do produto
            produto_info = self.df_mapeamento.iloc[idx]
            
            # Calcular compatibilidade de categoria
            categoria_produto = produto_info.get('llm_categoria_principal', 'OUTROS')
            categoria_consulta = metadados_consulta.get('categoria_principal', 'OUTROS')
            
            score_categoria = 1.0 if categoria_consulta == categoria_produto else 0.3
            
            # Score final ponderado
            score_final = (
                float(similaridade) * 0.7 +  # Semântica
                score_categoria * 0.3        # Categoria
            )
            
            candidatos.append({
                'indice': idx,
                'produto_info': produto_info,
                'metadados_consulta': metadados_consulta,
                'score_semantico': float(similaridade),
                'score_categoria': float(score_categoria),
                'score_final': float(score_final),
                'categoria_produto': categoria_produto
            })
        
        # 6. Ordenar e retornar melhores
        candidatos.sort(key=lambda x: x['score_final'], reverse=True)
        return candidatos[:MAX_SUGESTOES]
    
    def determinar_qualidade(self, score_final):
        """Determina qualidade do match"""
        if score_final >= LIMIAR_BOM:
            return "🎼 BOM", "✅"
        elif score_final >= LIMIAR_ACEITAVEL:
            return "🎶 ACEITÁVEL", "🟡"
        else:
            return "❌ BAIXO", "❌"
    
    def processar_edital(self, caminho_edital):
        """Processa um edital completo"""
        
        nome_arquivo = os.path.basename(caminho_edital)
        logger.info(f"🎼 Processando edital: {nome_arquivo}")
        
        try:
            df_edital = pd.read_excel(caminho_edital)
            resultados = []
            
            for _, row in tqdm(df_edital.iterrows(), total=len(df_edital), desc="Processando itens"):
                item_catmat = str(row.get('Item', '')).strip()
                
                if not item_catmat or item_catmat.lower() == 'nan':
                    continue
                
                # Buscar candidatos
                candidatos = self.buscar_produtos(item_catmat)
                
                # Processar resultado
                dados_resultado = row.to_dict()
                
                if candidatos:
                    melhor_candidato = candidatos[0]
                    produto_info = melhor_candidato['produto_info']
                    
                    qualidade, emoji = self.determinar_qualidade(melhor_candidato['score_final'])
                    
                    # Preencher dados
                    dados_resultado.update({
                        'Marca Sugerida': produto_info.get('Marca', ''),
                        'Produto Sugerido': produto_info.get('Modelo', ''),
                        'Descrição do Produto Sugerido': produto_info.get('Descrição', ''),
                        'Preço Produto': produto_info.get('Valor', ''),
                        '% Compatibilidade': f"{melhor_candidato['score_final']:.1%}",
                        'Qualidade Match': qualidade,
                        'Score Semântico': f"{melhor_candidato['score_semantico']:.3f}",
                        'Score Categoria': f"{melhor_candidato['score_categoria']:.3f}",
                        'Categoria Identificada': melhor_candidato['categoria_produto'],
                        'Categoria Consulta': melhor_candidato['metadados_consulta'].get('categoria_principal', ''),
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
                    # Nenhum candidato
                    dados_resultado.update({
                        'Marca Sugerida': "❌ Não encontrado",
                        'Produto Sugerido': "N/A",
                        'Descrição do Produto Sugerido': "N/A",
                        'Preço Produto': "N/A",
                        '% Compatibilidade': "0%",
                        'Qualidade Match': "❌ BAIXO",
                        'Score Semântico': "0.000",
                        'Score Categoria': "0.000",
                        'Categoria Identificada': "N/A",
                        'Categoria Consulta': "N/A",
                        'Alternativas': "Nenhuma"
                    })
                
                resultados.append(dados_resultado)
            
            # Salvar resultado
            df_resultado = pd.DataFrame(resultados)
            
            nome_base, extensao = os.path.splitext(nome_arquivo)
            caminho_saida = os.path.join(PASTA_RESULTADOS, f"{nome_base}_RESULTADO{extensao}")
            
            os.makedirs(PASTA_RESULTADOS, exist_ok=True)
            df_resultado.to_excel(caminho_saida, index=False)
            
            # Estatísticas
            total_items = len(df_resultado)
            matches_bons = len(df_resultado[df_resultado['Qualidade Match'].str.contains('BOM', na=False)])
            matches_aceitaveis = len(df_resultado[df_resultado['Qualidade Match'].str.contains('ACEITÁVEL', na=False)])
            matches_baixos = len(df_resultado[df_resultado['Qualidade Match'].str.contains('BAIXO', na=False)])
            
            try:
                compatibilidade_media = df_resultado['% Compatibilidade'].str.replace('%', '').astype(float).mean()
            except:
                compatibilidade_media = 0.0
            
            logger.info(f"✅ Resultado salvo: {caminho_saida}")
            logger.info(f"📊 Estatísticas: {total_items} itens | ✅ {matches_bons} bons | 🟡 {matches_aceitaveis} aceitáveis | ❌ {matches_baixos} baixos | Média: {compatibilidade_media:.1f}%")
            
            return {
                'arquivo': caminho_saida,
                'total': total_items,
                'bons': matches_bons,
                'aceitaveis': matches_aceitaveis,
                'baixos': matches_baixos,
                'media': compatibilidade_media
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar edital {nome_arquivo}: {e}")
            return None

def main():
    """Função principal"""
    
    print("🔍 BUSCADOR SIMPLES GROQ - VERSÃO FUNCIONAL")
    print("=" * 80)
    print("🎯 Objetivo: Buscar produtos usando índice FAISS + Groq")
    print("🚀 Foco: FUNCIONALIDADE e VELOCIDADE")
    print("=" * 80)
    
    try:
        # Verificar se índice existe
        if not os.path.exists(PASTA_INDICE):
            logger.error(f"❌ Pasta de índice não encontrada: {PASTA_INDICE}")
            logger.error("Execute primeiro: python gerador_embeddings_simples.py")
            return
        
        # Criar buscador
        buscador = BuscadorSimplesGroq()
        
        # Encontrar editais
        if not os.path.exists(PASTA_EDITAIS):
            logger.error(f"❌ Pasta de editais não encontrada: {PASTA_EDITAIS}")
            return
        
        arquivos_editais = [
            os.path.join(PASTA_EDITAIS, f) 
            for f in os.listdir(PASTA_EDITAIS) 
            if f.endswith('.xlsx')
        ]
        
        if not arquivos_editais:
            logger.error(f"❌ Nenhum arquivo .xlsx encontrado em: {PASTA_EDITAIS}")
            return
        
        logger.info(f"📁 {len(arquivos_editais)} editais encontrados")
        
        # Processar editais
        resultados_totais = []
        
        for edital in arquivos_editais:
            resultado = buscador.processar_edital(edital)
            if resultado:
                resultados_totais.append(resultado)
        
        # Salvar cache de consultas
        buscador.processador_consulta.cache.salvar()
        
        # Estatísticas finais
        if resultados_totais:
            total_geral = sum(r['total'] for r in resultados_totais)
            bons_geral = sum(r['bons'] for r in resultados_totais)
            aceitaveis_geral = sum(r['aceitaveis'] for r in resultados_totais)
            baixos_geral = sum(r['baixos'] for r in resultados_totais)
            media_geral = np.mean([r['media'] for r in resultados_totais])
            
            print("\n🎉 BUSCA CONCLUÍDA COM SUCESSO!")
            print("=" * 80)
            print(f"📊 ESTATÍSTICAS GERAIS:")
            print(f"   Total de itens: {total_geral}")
            print(f"   ✅ Bons: {bons_geral} ({bons_geral/total_geral*100:.1f}%)")
            print(f"   🟡 Aceitáveis: {aceitaveis_geral} ({aceitaveis_geral/total_geral*100:.1f}%)")
            print(f"   ❌ Baixos: {baixos_geral} ({baixos_geral/total_geral*100:.1f}%)")
            print(f"   📈 Compatibilidade média: {media_geral:.1f}%")
            print(f"📁 Resultados salvos em: {PASTA_RESULTADOS}")
            print(f"🤖 Requests Groq: {buscador.processador_consulta.total_requests}")
            print(f"💾 Cache hits: {buscador.processador_consulta.total_cache_hits}")
            print("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Erro durante busca: {e}")
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

