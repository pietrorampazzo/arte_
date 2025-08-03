#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧠 GERADOR DE EMBEDDINGS SIMPLES - FUNCIONAL
Versão: Simplificada - Janeiro 2025

OBJETIVO: Gerar embeddings dos textos processados
✅ Lê textos do processador Groq
✅ Gera embeddings com Sentence Transformers
✅ Cria índice FAISS
✅ Salva mapeamento completo
✅ Pronto para busca

FOCO: SIMPLICIDADE E FUNCIONALIDADE
Complementa o processador_simples_groq.py

Autor: Sistema Simplificado
"""

import pandas as pd
import numpy as np
import faiss
import os
import logging
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import pickle

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# === CONFIGURAÇÕES ===
PASTA_DADOS = "dados_processados"
PASTA_INDICE = "indice_simples"

# Arquivos de entrada (gerados pelo processador)
ARQUIVO_PRODUTOS = os.path.join(PASTA_DADOS, "produtos_processados.xlsx")
ARQUIVO_TEXTOS = os.path.join(PASTA_DADOS, "textos_para_embedding.txt")

# Arquivos de saída
ARQUIVO_INDICE_FAISS = os.path.join(PASTA_INDICE, "produtos.index")
ARQUIVO_MAPEAMENTO = os.path.join(PASTA_INDICE, "mapeamento.xlsx")
ARQUIVO_EMBEDDINGS = os.path.join(PASTA_INDICE, "embeddings.npy")

# Modelo de embeddings
MODELO_EMBEDDING = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
BATCH_SIZE_EMBEDDING = 32

class GeradorEmbeddingsSimples:
    """Gerador de embeddings super simples que funciona"""
    
    def __init__(self):
        logger.info("🧠 Inicializando gerador de embeddings...")
        
        try:
            self.model = SentenceTransformer(MODELO_EMBEDDING)
            logger.info(f"✅ Modelo carregado: {MODELO_EMBEDDING}")
        except Exception as e:
            logger.error(f"❌ Erro ao carregar modelo: {e}")
            raise
        
        # Criar pasta de índice
        os.makedirs(PASTA_INDICE, exist_ok=True)
    
    def carregar_dados(self):
        """Carrega dados processados"""
        
        logger.info("📂 Carregando dados processados...")
        
        # Verificar se arquivos existem
        if not os.path.exists(ARQUIVO_PRODUTOS):
            raise FileNotFoundError(f"Arquivo não encontrado: {ARQUIVO_PRODUTOS}")
        
        if not os.path.exists(ARQUIVO_TEXTOS):
            raise FileNotFoundError(f"Arquivo não encontrado: {ARQUIVO_TEXTOS}")
        
        # Carregar DataFrame
        self.df_produtos = pd.read_excel(ARQUIVO_PRODUTOS)
        logger.info(f"✅ DataFrame carregado: {len(self.df_produtos)} produtos")
        
        # Carregar textos para embedding
        with open(ARQUIVO_TEXTOS, 'r', encoding='utf-8') as f:
            self.textos_embedding = [linha.strip() for linha in f.readlines()]
        
        logger.info(f"✅ Textos carregados: {len(self.textos_embedding)} textos")
        
        # Verificar consistência
        if len(self.df_produtos) != len(self.textos_embedding):
            logger.warning(f"⚠️ Inconsistência: {len(self.df_produtos)} produtos vs {len(self.textos_embedding)} textos")
            # Ajustar para o menor
            min_len = min(len(self.df_produtos), len(self.textos_embedding))
            self.df_produtos = self.df_produtos.iloc[:min_len]
            self.textos_embedding = self.textos_embedding[:min_len]
            logger.info(f"✅ Ajustado para: {min_len} itens")
    
    def gerar_embeddings(self):
        """Gera embeddings dos textos"""
        
        logger.info("🧠 Gerando embeddings...")
        
        # Filtrar textos vazios
        textos_validos = []
        indices_validos = []
        
        for i, texto in enumerate(self.textos_embedding):
            if texto and texto.strip():
                textos_validos.append(texto.strip())
                indices_validos.append(i)
            else:
                logger.warning(f"⚠️ Texto vazio no índice {i}")
        
        logger.info(f"📝 Textos válidos: {len(textos_validos)}")
        
        # Gerar embeddings em batches
        embeddings_list = []
        
        for i in tqdm(range(0, len(textos_validos), BATCH_SIZE_EMBEDDING), desc="Gerando embeddings"):
            batch_textos = textos_validos[i:i + BATCH_SIZE_EMBEDDING]
            
            try:
                batch_embeddings = self.model.encode(
                    batch_textos,
                    batch_size=BATCH_SIZE_EMBEDDING,
                    show_progress_bar=False,
                    convert_to_numpy=True
                )
                embeddings_list.append(batch_embeddings)
                
            except Exception as e:
                logger.error(f"❌ Erro ao gerar embeddings do batch {i}: {e}")
                # Criar embeddings zeros como fallback
                fallback_embeddings = np.zeros((len(batch_textos), self.model.get_sentence_embedding_dimension()))
                embeddings_list.append(fallback_embeddings)
        
        # Concatenar todos os embeddings
        if embeddings_list:
            self.embeddings = np.vstack(embeddings_list).astype('float32')
            logger.info(f"✅ Embeddings gerados: {self.embeddings.shape}")
        else:
            raise ValueError("Nenhum embedding foi gerado")
        
        # Ajustar DataFrame para corresponder aos embeddings válidos
        self.df_produtos = self.df_produtos.iloc[indices_validos].reset_index(drop=True)
        self.textos_embedding = [self.textos_embedding[i] for i in indices_validos]
        
        logger.info(f"✅ Dados ajustados: {len(self.df_produtos)} produtos finais")
    
    def criar_indice_faiss(self):
        """Cria índice FAISS"""
        
        logger.info("🔍 Criando índice FAISS...")
        
        # Normalizar embeddings para similaridade de cosseno
        faiss.normalize_L2(self.embeddings)
        
        # Criar índice
        dimensao = self.embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dimensao)  # Inner Product (cosseno após normalização)
        
        # Adicionar embeddings com IDs
        ids = np.arange(len(self.embeddings)).astype('int64')
        self.index = faiss.IndexIDMap(self.index)
        self.index.add_with_ids(self.embeddings, ids)
        
        logger.info(f"✅ Índice FAISS criado: {self.index.ntotal} vetores, dimensão {dimensao}")
    
    def salvar_resultados(self):
        """Salva todos os resultados"""
        
        logger.info("💾 Salvando resultados...")
        
        # Salvar índice FAISS
        faiss.write_index(self.index, ARQUIVO_INDICE_FAISS)
        logger.info(f"✅ Índice FAISS salvo: {ARQUIVO_INDICE_FAISS}")
        
        # Salvar embeddings como numpy array
        np.save(ARQUIVO_EMBEDDINGS, self.embeddings)
        logger.info(f"✅ Embeddings salvos: {ARQUIVO_EMBEDDINGS}")
        
        # Preparar mapeamento completo
        df_mapeamento = self.df_produtos.copy()
        df_mapeamento['texto_embedding'] = self.textos_embedding
        df_mapeamento['embedding_id'] = range(len(df_mapeamento))
        
        # Salvar mapeamento
        df_mapeamento.to_excel(ARQUIVO_MAPEAMENTO, index=False)
        logger.info(f"✅ Mapeamento salvo: {ARQUIVO_MAPEAMENTO}")
        
        return {
            'total_produtos': len(df_mapeamento),
            'dimensao_embeddings': self.embeddings.shape[1],
            'arquivo_indice': ARQUIVO_INDICE_FAISS,
            'arquivo_mapeamento': ARQUIVO_MAPEAMENTO,
            'arquivo_embeddings': ARQUIVO_EMBEDDINGS
        }
    
    def testar_busca(self, texto_teste="trompete em Bb"):
        """Testa busca no índice criado"""
        
        logger.info(f"🧪 Testando busca com: '{texto_teste}'")
        
        try:
            # Gerar embedding da consulta
            embedding_consulta = self.model.encode([texto_teste], convert_to_numpy=True)
            embedding_consulta = embedding_consulta.astype('float32')
            faiss.normalize_L2(embedding_consulta)
            
            # Buscar
            k = 5
            distancias, indices = self.index.search(embedding_consulta, k)
            
            logger.info("🔍 Resultados da busca:")
            for i, (idx, dist) in enumerate(zip(indices[0], distancias[0])):
                if idx != -1:
                    produto = self.df_produtos.iloc[idx]
                    logger.info(f"   {i+1}. {produto.get('Marca', 'N/A')} {produto.get('Modelo', 'N/A')} (similaridade: {dist:.3f})")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro no teste de busca: {e}")
            return False

def main():
    """Função principal"""
    
    print("🧠 GERADOR DE EMBEDDINGS SIMPLES - VERSÃO FUNCIONAL")
    print("=" * 80)
    print("🎯 Objetivo: Gerar embeddings dos dados processados pelo Groq")
    print("🚀 Foco: FUNCIONALIDADE e SIMPLICIDADE")
    print("=" * 80)
    
    try:
        # Verificar se dados processados existem
        if not os.path.exists(PASTA_DADOS):
            logger.error(f"❌ Pasta não encontrada: {PASTA_DADOS}")
            logger.error("Execute primeiro: python processador_simples_groq.py")
            return
        
        # Criar gerador
        gerador = GeradorEmbeddingsSimples()
        
        # 1. Carregar dados
        gerador.carregar_dados()
        
        # 2. Gerar embeddings
        gerador.gerar_embeddings()
        
        # 3. Criar índice FAISS
        gerador.criar_indice_faiss()
        
        # 4. Salvar resultados
        resultados = gerador.salvar_resultados()
        
        # 5. Testar busca
        sucesso_teste = gerador.testar_busca()
        
        # 6. Estatísticas finais
        print("\n🎉 GERAÇÃO DE EMBEDDINGS CONCLUÍDA!")
        print("=" * 80)
        print(f"📊 ESTATÍSTICAS:")
        print(f"   Total de produtos: {resultados['total_produtos']}")
        print(f"   Dimensão embeddings: {resultados['dimensao_embeddings']}")
        print(f"   Teste de busca: {'✅ Sucesso' if sucesso_teste else '❌ Falhou'}")
        print(f"\n📁 ARQUIVOS GERADOS:")
        print(f"   Índice FAISS: {resultados['arquivo_indice']}")
        print(f"   Mapeamento: {resultados['arquivo_mapeamento']}")
        print(f"   Embeddings: {resultados['arquivo_embeddings']}")
        print("=" * 80)
        print("🚀 PRÓXIMO PASSO: Use o buscador para fazer consultas!")
        print("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Erro durante geração: {e}")
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

