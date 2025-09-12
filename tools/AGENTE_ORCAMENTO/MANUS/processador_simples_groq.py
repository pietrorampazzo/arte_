#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎼 PROCESSADOR SIMPLES GROQ - FUNCIONAL E DIRETO
Versão: Simplificada - Janeiro 2025

OBJETIVO: Script simples que FUNCIONA
✅ Lê data_base.xlsx
✅ Processa com Groq em batches
✅ Gera dados prontos para embedding
✅ Cache simples para economia
✅ Rate limiting básico mas eficaz

FOCO: SIMPLICIDADE E FUNCIONALIDADE
Sem complicações, só o que funciona!

Autor: Sistema Simplificado
"""

import pandas as pd
import numpy as np
import json
import os
import time
import logging
import requests
import pickle
import hashlib
from datetime import datetime
from typing import List, Dict, Any
from tqdm import tqdm

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# === CONFIGURAÇÕES ===
CAMINHO_DADOS = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\FORNECEDORES\data_base.xlsx"
PASTA_SAIDA = "dados_processados"
ARQUIVO_CACHE = os.path.join(PASTA_SAIDA, "cache_groq.pkl")
ARQUIVO_RESULTADOS = os.path.join(PASTA_SAIDA, "produtos_processados.xlsx")
ARQUIVO_EMBEDDINGS = os.path.join(PASTA_SAIDA, "textos_para_embedding.txt")

# API Groq
GROQ_API_KEY = "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"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODELO = "gemma2-9b-itb"  # Modelo mais estável

# Parâmetros
BATCH_SIZE = 1000  # Começar pequeno para garantir funcionamento
DELAY_ENTRE_BATCHES = 2  # Segundos
MAX_RETRIES = 3

class CacheSimples:
    """Cache super simples que funciona"""
    
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
                logger.info(f"Cache carregado: {len(self.cache)} entradas")
        except Exception as e:
            logger.warning(f"Erro ao carregar cache: {e}")
            self.cache = {}
    
    def salvar(self):
        """Salva cache"""
        try:
            os.makedirs(os.path.dirname(self.arquivo_cache), exist_ok=True)
            with open(self.arquivo_cache, 'wb') as f:
                pickle.dump(self.cache, f)
        except Exception as e:
            logger.error(f"Erro ao salvar cache: {e}")
    
    def get(self, chave):
        """Busca no cache"""
        hash_chave = hashlib.md5(str(chave).encode()).hexdigest()
        return self.cache.get(hash_chave)
    
    def set(self, chave, valor):
        """Adiciona ao cache"""
        hash_chave = hashlib.md5(str(chave).encode()).hexdigest()
        self.cache[hash_chave] = valor

class ProcessadorGroqSimples:
    """Processador Groq super simples que funciona"""
    
    def __init__(self):
        self.cache = CacheSimples(ARQUIVO_CACHE)
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GROQ_API_KEY}"
        }
        self.total_requests = 0
        self.total_cache_hits = 0
        
        logger.info("🚀 Processador Groq inicializado")
    
    def criar_prompt_batch(self, descricoes_batch):
        """Cria prompt para batch de descrições"""
        
        prompt_sistema = """Você é um especialista em instrumentos musicais e equipamentos de áudio.

TAREFA: Para cada descrição, extraia metadados em formato JSON.

CATEGORIAS PRINCIPAIS:
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
- subcategoria: tipo específico (ex: TROMPETE, CAIXA_ATIVA)
- afinacao: afinação musical (ex: Bb, Eb) ou null
- dimensao: medidas (ex: "15 polegadas") ou null
- material: material principal ou null
- potencia: potência elétrica (ex: "400W") ou null
- marca: marca identificada ou null
- modelo: modelo identificado ou null
- especificacoes_extras: dict com specs extras ou {}

FORMATO: Retorne APENAS um array JSON válido, sem texto adicional.
Exemplo: [{"categoria_principal": "INSTRUMENTO_SOPRO_METAL", "subcategoria": "TROMPETE", ...}]"""

        # Criar lista numerada das descrições
        descricoes_numeradas = []
        for i, desc in enumerate(descricoes_batch, 1):
            descricoes_numeradas.append(f"{i}. {desc}")
        
        prompt_usuario = "DESCRIÇÕES PARA ANÁLISE:\n" + "\n".join(descricoes_numeradas)
        
        return prompt_sistema, prompt_usuario
    
    def processar_batch_groq(self, descricoes_batch):
        """Processa batch com Groq"""
        
        # Verificar cache primeiro
        resultados_cache = []
        descricoes_para_processar = []
        indices_originais = []
        
        for i, desc in enumerate(descricoes_batch):
            resultado_cache = self.cache.get(desc)
            if resultado_cache:
                resultados_cache.append((i, resultado_cache))
                self.total_cache_hits += 1
            else:
                descricoes_para_processar.append(desc)
                indices_originais.append(i)
        
        # Se tudo está no cache, retornar
        if not descricoes_para_processar:
            logger.info(f"✅ Batch completo no cache: {len(descricoes_batch)} itens")
            return [resultado for _, resultado in sorted(resultados_cache)]
        
        logger.info(f"🔄 Processando {len(descricoes_para_processar)} itens (cache: {len(resultados_cache)})")
        
        # Processar com Groq
        prompt_sistema, prompt_usuario = self.criar_prompt_batch(descricoes_para_processar)
        
        payload = {
            "model": MODELO,
            "messages": [
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario}
            ],
            "temperature": 0.1,
            "max_tokens": 6000
        }
        
        for tentativa in range(MAX_RETRIES):
            try:
                logger.info(f"📡 Enviando para Groq (tentativa {tentativa + 1})")
                
                response = requests.post(
                    GROQ_URL,
                    headers=self.headers,
                    json=payload,
                    timeout=60
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result['choices'][0]['message']['content'].strip()
                    
                    # Extrair JSON da resposta
                    try:
                        # Encontrar array JSON
                        start_idx = content.find('[')
                        end_idx = content.rfind(']') + 1
                        
                        if start_idx != -1 and end_idx != -1:
                            json_text = content[start_idx:end_idx]
                            metadados_list = json.loads(json_text)
                            
                            # Validar número de resultados
                            if len(metadados_list) == len(descricoes_para_processar):
                                # Adicionar ao cache
                                for desc, metadados in zip(descricoes_para_processar, metadados_list):
                                    self.cache.set(desc, metadados)
                                
                                # Combinar com resultados do cache
                                resultados_finais = [{}] * len(descricoes_batch)
                                
                                # Preencher cache hits
                                for idx, resultado in resultados_cache:
                                    resultados_finais[idx] = resultado
                                
                                # Preencher novos resultados
                                for idx_original, metadados in zip(indices_originais, metadados_list):
                                    resultados_finais[idx_original] = metadados
                                
                                self.total_requests += 1
                                logger.info(f"✅ Batch processado com sucesso")
                                return resultados_finais
                            
                            else:
                                logger.warning(f"⚠️ Número incorreto de resultados: {len(metadados_list)} vs {len(descricoes_para_processar)}")
                        
                        else:
                            logger.warning("⚠️ JSON não encontrado na resposta")
                    
                    except json.JSONDecodeError as e:
                        logger.warning(f"⚠️ Erro ao decodificar JSON: {e}")
                        logger.debug(f"Resposta recebida: {content[:500]}")
                
                elif response.status_code == 429:
                    wait_time = 60
                    logger.warning(f"⏳ Rate limit atingido. Aguardando {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                
                else:
                    logger.error(f"❌ Erro HTTP {response.status_code}: {response.text}")
            
            except Exception as e:
                logger.error(f"❌ Erro na tentativa {tentativa + 1}: {e}")
            
            # Aguardar antes da próxima tentativa
            if tentativa < MAX_RETRIES - 1:
                time.sleep(5)
        
        # Se chegou aqui, falhou
        logger.error("❌ Falha ao processar batch após todas as tentativas")
        
        # Retornar metadados vazios para manter consistência
        resultados_finais = [{}] * len(descricoes_batch)
        for idx, resultado in resultados_cache:
            resultados_finais[idx] = resultado
        
        return resultados_finais
    
    def processar_todos_produtos(self, df_produtos):
        """Processa todos os produtos em batches"""
        
        logger.info(f"🔄 Iniciando processamento de {len(df_produtos)} produtos")
        
        # Preparar dados
        descricoes = []
        for _, row in df_produtos.iterrows():
            desc = str(row.get('Descrição', '')).strip()
            if desc and desc.lower() != 'nan':
                descricoes.append(desc)
            else:
                descricoes.append("")
        
        # Processar em batches
        todos_metadados = []
        total_batches = (len(descricoes) + BATCH_SIZE - 1) // BATCH_SIZE
        
        for i in tqdm(range(0, len(descricoes), BATCH_SIZE), desc="Processando batches"):
            batch = descricoes[i:i + BATCH_SIZE]
            
            logger.info(f"📦 Processando batch {i//BATCH_SIZE + 1}/{total_batches}")
            
            metadados_batch = self.processar_batch_groq(batch)
            todos_metadados.extend(metadados_batch)
            
            # Salvar cache periodicamente
            if i % (BATCH_SIZE * 5) == 0:
                self.cache.salvar()
            
            # Delay entre batches
            if i + BATCH_SIZE < len(descricoes):
                time.sleep(DELAY_ENTRE_BATCHES)
        
        # Salvar cache final
        self.cache.salvar()
        
        logger.info(f"✅ Processamento concluído!")
        logger.info(f"📊 Estatísticas:")
        logger.info(f"   Total requests: {self.total_requests}")
        logger.info(f"   Cache hits: {self.total_cache_hits}")
        logger.info(f"   Taxa cache: {self.total_cache_hits/(self.total_requests + self.total_cache_hits)*100:.1f}%")
        
        return todos_metadados
    
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
        
        # Categoria (peso alto para matching)
        if categoria != 'OUTROS':
            partes.append(f"CATEGORIA: {categoria}")
        
        if subcategoria:
            partes.append(f"TIPO: {subcategoria}")
        
        # Marca e modelo
        if marca and marca.lower() != 'nan':
            partes.append(f"MARCA: {marca}")
        if modelo and modelo.lower() != 'nan':
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
        if descricao and descricao.lower() != 'nan':
            partes.append(f"DESC: {descricao}")
        
        return " || ".join(partes)

def main():
    """Função principal"""
    
    print("🎼 PROCESSADOR SIMPLES GROQ - VERSÃO FUNCIONAL")
    print("=" * 80)
    print("🎯 Objetivo: Processar data_base.xlsx com Groq de forma simples")
    print("🚀 Foco: FUNCIONALIDADE acima de tudo")
    print("=" * 80)
    
    try:
        # Criar pasta de saída
        os.makedirs(PASTA_SAIDA, exist_ok=True)
        
        # 1. Carregar dados
        logger.info("📂 Carregando dados...")
        if not os.path.exists(CAMINHO_DADOS):
            logger.error(f"❌ Arquivo não encontrado: {CAMINHO_DADOS}")
            return
        
        df_produtos = pd.read_excel(CAMINHO_DADOS)
        logger.info(f"✅ Dados carregados: {len(df_produtos)} produtos")
        
        # Limpar dados básicos
        df_produtos = df_produtos.dropna(subset=['Descrição'])
        df_produtos = df_produtos[df_produtos['Descrição'].astype(str).str.strip() != '']
        logger.info(f"✅ Após limpeza: {len(df_produtos)} produtos válidos")
        
        # 2. Processar com Groq
        processador = ProcessadorGroqSimples()
        metadados_list = processador.processar_todos_produtos(df_produtos)
        
        # 3. Criar DataFrame final
        logger.info("📊 Criando DataFrame final...")
        df_final = df_produtos.copy().reset_index(drop=True)
        
        # Adicionar metadados
        for i, metadados in enumerate(metadados_list):
            if i < len(df_final):
                for key, value in metadados.items():
                    df_final.loc[i, f'llm_{key}'] = value
        
        # 4. Criar textos para embedding
        logger.info("📝 Criando textos para embedding...")
        textos_embedding = []
        
        for i, row in df_final.iterrows():
            metadados = metadados_list[i] if i < len(metadados_list) else {}
            texto = processador.criar_texto_embedding(row, metadados)
            textos_embedding.append(texto)
        
        df_final['texto_embedding'] = textos_embedding
        
        # 5. Salvar resultados
        logger.info("💾 Salvando resultados...")
        
        # Salvar Excel completo
        df_final.to_excel(ARQUIVO_RESULTADOS, index=False)
        logger.info(f"✅ Excel salvo: {ARQUIVO_RESULTADOS}")
        
        # Salvar textos para embedding
        with open(ARQUIVO_EMBEDDINGS, 'w', encoding='utf-8') as f:
            for texto in textos_embedding:
                f.write(texto + '\n')
        logger.info(f"✅ Textos para embedding salvos: {ARQUIVO_EMBEDDINGS}")
        
        # 6. Estatísticas finais
        categorias = df_final['llm_categoria_principal'].value_counts()
        
        print("\n🎉 PROCESSAMENTO CONCLUÍDO COM SUCESSO!")
        print("=" * 80)
        print(f"📊 ESTATÍSTICAS:")
        print(f"   Total de produtos: {len(df_final)}")
        print(f"   Requests Groq: {processador.total_requests}")
        print(f"   Cache hits: {processador.total_cache_hits}")
        print(f"   Taxa de cache: {processador.total_cache_hits/(processador.total_requests + processador.total_cache_hits)*100:.1f}%")
        print(f"\n📋 CATEGORIAS IDENTIFICADAS:")
        for categoria, count in categorias.head(10).items():
            print(f"   {categoria}: {count}")
        print(f"\n📁 ARQUIVOS GERADOS:")
        print(f"   Excel completo: {ARQUIVO_RESULTADOS}")
        print(f"   Textos embedding: {ARQUIVO_EMBEDDINGS}")
        print(f"   Cache: {ARQUIVO_CACHE}")
        print("=" * 80)
        print("🚀 PRÓXIMO PASSO: Use os textos para gerar embeddings!")
        print("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Erro durante processamento: {e}")
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

