#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎯 INDEXADOR MELHORADO - BASEADO NA ANÁLISE DA BASE DE DADOS
Versão Otimizada para Embeddings de Alta Qualidade

MELHORIAS IMPLEMENTADAS:
✅ Extração de especificações técnicas específicas da base
✅ Normalização de termos técnicos encontrados
✅ Identificação automática de categorias
✅ Correção de erros comuns identificados
✅ Texto de embedding estruturado e contextual

BASEADO NA ANÁLISE:
- 3.707 produtos, 18 marcas principais
- Categorias: Caixas de Som, Microfones, Amplificadores, etc.
- Specs: Potência (W), Polegadas ("), Voltagem (V), Bluetooth, etc.
- Problemas: Erros de digitação ("toca" → "potência")

Autor: Sistema Melhorado
Data: Janeiro 2025
"""

import pandas as pd
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import os
import re
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

# --- CONFIGURAÇÕES ---
CAMINHO_BASE_PRODUTOS = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\data_base.xlsx"
PASTA_INDICE = "indice_faiss_melhorado"
ARQUIVO_INDICE = os.path.join(PASTA_INDICE, "produtos_melhorado.index")
ARQUIVO_MAPEAMENTO = os.path.join(PASTA_INDICE, "mapeamento_produtos_melhorado.csv")

# Modelo otimizado para português técnico
NOME_MODELO = 'all-mpnet-base-v2'  # Mais rápido e eficiente que o anterior

class ProcessadorEspecificacoes:
    """Processador especializado para extrair e normalizar especificações técnicas"""
    
    def __init__(self):
        # Padrões baseados na análise real da base de dados
        self.specs_patterns = {
            'POTENCIA': [
                r'(\d+)\s*W\b',
                r'(\d+)\s*watts?\b',
                r'potencia[:\s]*(\d+)'
            ],
            'POLEGADAS': [
                r'(\d+)\"',
                r'(\d+)\s*pol\b',
                r'(\d+)\s*polegadas?\b'
            ],
            'VOLTAGEM': [
                r'(\d+)V\b',
                r'(\d+)\s*volts?\b',
                r'(\d+)/(\d+)V'
            ],
            'FREQUENCIA': [
                r'(\d+)\s*Hz\b',
                r'(\d+)\s*KHz\b'
            ],
            'OHMS': [
                r'(\d+)\s*ohms?\b'
            ],
            'CANAIS': [
                r'(\d+)\s*canais?\b',
                r'(\d+)\s*ch\b'
            ],
            'DIMENSAO': [  # Novo: para comprimentos como baquetas/surdos
                r'(\d+)mm',
                r'(\d+)cm',
                r'(\d+)x(\d+)',
                r'(\d+)\s*X\s*(\d+)'
            ],
            'COR': [  # Novo: para cores em descrições
                r'cor (\w+)',
                r'preto',
                r'branco',
                r'azul',
                r'amarelo',
                r'vermelho',
                r'verde',
                r'champanhe'
            ],
            'AFINADORES': [  # Novo: para afinadores em surdos/pandeiros
                r'(\d+)\s*afina',
                r'(\d+)\s*tirantes',
                r'(\d+)\s*AF'
            ],
            'MATERIAL': [  # Novo: materiais comuns em baquetas/peles
                r'madeira',
                r'nylon',
                r'borracha',
                r'alumínio',
                r'aço',
                r'plástico',
                r'formica',
                r'couro',
                r'caprino',
                r'napa',
                r'hickory',
                r'feltro',
                r'pelúcia'
            ],
            'ESTEIRA': [  # Novo: fios em esteiras
                r'(\d+)\s*fios'
            ],
            'PELE_TIPO': [  # Novo: tipos de pele
                r'leitosa',
                r'animal',
                r'napa',
                r'preta',
                r'metalizada',
                r'porosa',
                r'grossa',
                r'super grossa',
                r'P(\d+)'
            ],
            'NUM_UNIDADES': [  # Novo: unidades em kits/baquetas
                r'(\d+)\s*unidades',
                r'Caixa com (\d+) peças'
            ],
            'BLUETOOTH': [r'bluetooth'],  # Manter/expandir
            'WIRELESS': [r'sem fio', r'wireless'],
            'USB': [r'usb'],
            'PHANTOM': [r'phantom'],
            'DRIVES': [r'(\d+)\s*drives'],  # Para ear phones
            'NOTAS': [r'(\d+)\s*notas'],  # Para carrilhão
            'MOLAS': [r'(\d+)\s*molas']  # Para reco reco
        }
        
        # Categorias baseadas na análise real
        
        self.categorias_patterns = {
            'CAIXA_ATIVA': [r'caixa.*ativ[ao]', r'ativ[ao].*caixa', r'monitor.*ativ[ao]'],
            'CAIXA_PASSIVA': [r'caixa.*passiv[ao]', r'passiv[ao].*caixa', r'monitor.*passiv[ao]'],
            'CAIXA_SOM': [r'\bcaixa\b(?!.*ativ|.*passiv)', r'monitor(?!.*ativ|.*passiv)', r'alto.*falante'],
            'MICROFONE': [r'\bmicrofone\b', r'\bmic\b', r'headset', r'lapela', r'shotgun', r'condenser', r'dinamico', r'podcast', r'gooseneck'],
            'AMPLIFICADOR': [r'amplificador', r'\bamp\b'],
            'CUBO_AMPLIFICADO': [r'\bcubo\b', r'combo'],
            'MESA_SOM': [r'mesa.*som', r'mesa.*audio', r'mixer'],
            'CABO_CONECTOR': [r'\bcabo\b', r'conector', r'plug', r'maçaneta cabo'],
            'SUBWOOFER': [r'sub.*woofer', r'subwoofer'],
            'BAQUETA': [r'baqueta', r'baq\.', r'vassourinha', r'maçaneta', r'brush'],  # Novo: baquetas e variantes
            'PELE': [r'pele', r'batedeira', r'resposta', r'animal', r'leitosa', r'napa', r'metalizada', r'porosa'],  # Novo: peles de instrumentos
            'SURDO': [r'surdo', r'surdão'],  # Novo: surdos
            'REPIQUE': [r'repique', r'repinique'],  # Novo: repiques
            'PANDEIRO': [r'pandeiro'],  # Novo: pandeiros
            'TALABARTE': [r'talabarte', r'tal'],  # Novo: talabartes
            'CARRILHAO': [r'carrilhão', r'carrilhao'],  # Novo: carrilhões
            'VASSOURINHA': [r'vassourinha'],  # Novo: vassourinhas
            'MACANETA': [r'maçaneta', r'macaneta'],  # Novo: maçanetas
            'TAMBORIM': [r'tamborim'],  # Novo: tamborins
            'CUICA': [r'cuica'],  # Novo: cuicas
            'ZABUMBA': [r'zabumba'],  # Novo: zabumbas
            'TIMBAL': [r'timbal'],  # Novo: timbais
            'REBOLO': [r'rebolo'],  # Novo: rebolos
            'MALACACHETA': [r'malacacheta'],  # Novo: malacachetas
            'TAROL': [r'tarol'],  # Novo: tarols
            'BUMBO': [r'bumbo'],  # Novo: bumbos
            'RECO_RECO': [r'reco reco', r'reco-reco'],  # Novo: reco-recos
            'TRIANGULO': [r'triangulo', r'triângulo'],  # Novo: triângulos
            'BLOCO_SONORO': [r'bloco sonoro'],  # Novo: blocos sonoros
            'PRACTICE_PAD': [r'practice pad'],  # Novo: practice pads
            'FONE_OUVIDO': [r'fone de ouvido', r'ear phone'],  # Novo: fones
            'HEADSET': [r'headset'],  # Novo: headsets
            'GOOSENECK': [r'gooseneck'],  # Novo: goosenecks
            'PODCAST_MIC': [r'podcast'],  # Novo: mics de podcast
            'SHOTGUN_MIC': [r'shotgun'],  # Novo: mics shotgun
            'CONDENSER_MIC': [r'condenser'],  # Novo: mics condenser
            'DINAMICO_MIC': [r'dinamico'],  # Novo: mics dinâmicos
            'LAPELA_MIC': [r'lapela']  # Novo: mics lapela
        }
        
        # Características especiais baseadas na análise
        self.caracteristicas_especiais = {
            'BLUETOOTH': [r'bluetooth', r'bt\b'],
            'USB': [r'\busb\b'],
            'WIRELESS': [r'wireless', r'sem.*fio'],
            'RACK': [r'\brack\b', r'padrão.*rack'],
            'PHANTOM': [r'phantom.*power', r'phantom'],
            'XLR': [r'\bxlr\b'],
            'P10': [r'\bp10\b', r'plug.*p10']
        }
        
        # Correções de erros comuns encontrados na base
        self.correcoes_texto = {
            'potenciatoca': 'potencia',
            'toca': 'potencia',
            'AmplifiCador': 'Amplificador',
            'SOW': 'W',
            'SOOW': 'W'
        }
    
    def corrigir_texto(self, texto):
        """Corrige erros comuns identificados na base"""
        if pd.isna(texto):
            return ""
        
        texto_corrigido = str(texto)
        for erro, correcao in self.correcoes_texto.items():
            texto_corrigido = texto_corrigido.replace(erro, correcao)
        
        return texto_corrigido
    
    def extrair_especificacoes(self, texto):
        """Extrai especificações técnicas do texto"""
        if pd.isna(texto):
            return {}
        
        texto = self.corrigir_texto(texto).upper()
        specs = {}
        
        for spec_name, patterns in self.specs_patterns.items():
            valores = []
            for pattern in patterns:
                matches = re.findall(pattern, texto, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        # Para padrões como 110/220V
                        valores.extend([v for v in match if v])
                    else:
                        valores.append(match)
            
            if valores:
                # Pegar valores únicos e mais relevantes
                valores_unicos = list(set(valores))
                specs[spec_name] = valores_unicos[:3]  # Máximo 3 valores por spec
        
        return specs
    
    def identificar_categoria(self, texto):
        """Identifica a categoria principal do produto"""
        if pd.isna(texto):
            return "OUTROS"
        
        texto = self.corrigir_texto(texto).upper()
        
        # Verificar categorias em ordem de prioridade
        for categoria, patterns in self.categorias_patterns.items():
            for pattern in patterns:
                if re.search(pattern, texto, re.IGNORECASE):
                    return categoria
        
        return "OUTROS"
    
    def extrair_caracteristicas_especiais(self, texto):
        """Extrai características especiais (Bluetooth, USB, etc.)"""
        if pd.isna(texto):
            return []
        
        texto = self.corrigir_texto(texto).upper()
        caracteristicas = []
        
        for caracteristica, patterns in self.caracteristicas_especiais.items():
            for pattern in patterns:
                if re.search(pattern, texto, re.IGNORECASE):
                    caracteristicas.append(caracteristica)
                    break
        
        return caracteristicas
    
    def normalizar_marca_modelo(self, marca, modelo):
        """Normaliza marca e modelo para melhor matching"""
        marca_norm = str(marca).upper().strip() if pd.notna(marca) else ""
        modelo_norm = str(modelo).upper().strip() if pd.notna(modelo) else ""
        
        # Remover caracteres especiais desnecessários
        marca_norm = re.sub(r'[^\w\s]', ' ', marca_norm)
        modelo_norm = re.sub(r'[^\w\s]', ' ', modelo_norm)
        
        return marca_norm, modelo_norm

def criar_texto_embedding_melhorado(row, processador):
    """
    Cria texto otimizado para embedding baseado na análise da base de dados
    
    ESTRUTURA DO TEXTO:
    1. Categoria principal
    2. Marca e modelo normalizados
    3. Especificações técnicas estruturadas
    4. Características especiais
    5. Descrição original corrigida
    """
    
    # 1. Extrair e processar dados
    marca_orig = row.get('Marca', '')
    modelo_orig = row.get('Modelo', '')
    descricao_orig = row.get('Descrição', '')
    
    # 2. Normalizar marca e modelo
    marca_norm, modelo_norm = processador.normalizar_marca_modelo(marca_orig, modelo_orig)
    
    # 3. Corrigir descrição
    descricao_corrigida = processador.corrigir_texto(descricao_orig)
    
    # 4. Identificar categoria
    categoria = processador.identificar_categoria(descricao_corrigida)
    
    # 5. Extrair especificações
    specs = processador.extrair_especificacoes(descricao_corrigida)
    
    # 6. Extrair características especiais
    caracteristicas = processador.extrair_caracteristicas_especiais(descricao_corrigida)
    
    # 7. Construir texto estruturado para embedding
    partes_texto = []
    
    # Categoria (peso alto no embedding)
    partes_texto.append(f"CATEGORIA: {categoria}")
    
    # Marca e modelo
    if marca_norm:
        partes_texto.append(f"MARCA: {marca_norm}")
    if modelo_norm:
        partes_texto.append(f"MODELO: {modelo_norm}")
    
    # Especificações técnicas estruturadas
    if specs:
        specs_texto = []
        for spec_name, valores in specs.items():
            if valores:
                specs_texto.append(f"{spec_name}: {' '.join(valores)}")
        if specs_texto:
            partes_texto.append(f"ESPECIFICACOES: {' | '.join(specs_texto)}")
    
    # Características especiais
    if caracteristicas:
        partes_texto.append(f"RECURSOS: {' '.join(caracteristicas)}")
    
    # Descrição original (corrigida)
    if descricao_corrigida:
        partes_texto.append(f"DESCRICAO: {descricao_corrigida}")
    
    # Juntar tudo com separadores claros
    texto_final = " | ".join(partes_texto)
    
    return texto_final

# --- SCRIPT PRINCIPAL ---
if __name__ == "__main__":
    print("🎯 INDEXADOR MELHORADO - BASEADO NA ANÁLISE DA BASE DE DADOS")
    print("=" * 70)
    print("✅ Extração de especificações técnicas específicas")
    print("✅ Normalização de termos técnicos")
    print("✅ Identificação automática de categorias")
    print("✅ Correção de erros comuns")
    print("✅ Texto de embedding estruturado")
    print("=" * 70)

    # 1. Criar pasta para o índice
    if not os.path.exists(PASTA_INDICE):
        os.makedirs(PASTA_INDICE)
        print(f"📁 Pasta criada: {PASTA_INDICE}")

    # 2. Carregar a base de produtos
    try:
        print("📂 Carregando base de produtos...")
        df_produtos = pd.read_excel(CAMINHO_BASE_PRODUTOS)
        print(f"✅ {len(df_produtos)} produtos carregados")
        print(f"📊 {df_produtos['Marca'].nunique()} marcas únicas")
    except FileNotFoundError:
        print(f"❌ ERRO: Arquivo '{CAMINHO_BASE_PRODUTOS}' não encontrado.")
        exit()

    # 3. Inicializar processador especializado
    print("🔧 Inicializando processador de especificações...")
    processador = ProcessadorEspecificacoes()

    # 4. Gerar textos melhorados para embedding
    print("📝 Gerando textos otimizados para embedding...")
    df_produtos['texto_embedding_melhorado'] = df_produtos.apply(
        lambda row: criar_texto_embedding_melhorado(row, processador), 
        axis=1
    )

    # 5. Mostrar exemplos dos textos gerados
    print("\n📋 EXEMPLOS DE TEXTOS GERADOS:")
    print("-" * 50)
    for i in range(min(3, len(df_produtos))):
        print(f"ORIGINAL: {df_produtos.iloc[i]['Marca']} | {df_produtos.iloc[i]['Modelo']} | {df_produtos.iloc[i]['Descrição']}")
        print(f"MELHORADO: {df_produtos.iloc[i]['texto_embedding_melhorado']}")
        print("-" * 50)

    # 6. Carregar modelo de embedding
    print(f"🤖 Carregando modelo '{NOME_MODELO}'...")
    model = SentenceTransformer(NOME_MODELO)

    # 7. Gerar embeddings
    print("🧠 Gerando embeddings melhorados...")
    textos_para_embedding = df_produtos['texto_embedding_melhorado'].tolist()
    
    embeddings_produtos = model.encode(
        textos_para_embedding, 
        show_progress_bar=True,
        batch_size=32  # Otimização de performance
    )
    embeddings_produtos = np.array(embeddings_produtos).astype('float32')
    
    # Normalizar para similaridade de cosseno
    faiss.normalize_L2(embeddings_produtos)

    # 8. Criar índice FAISS otimizado
    print("🔍 Criando índice FAISS...")
    dimensao_vetor = embeddings_produtos.shape[1]
    
    # IndexFlatIP para similaridade de cosseno
    index = faiss.IndexFlatIP(dimensao_vetor)
    index = faiss.IndexIDMap(index)
    
    # Adicionar vetores com IDs
    index.add_with_ids(embeddings_produtos, df_produtos.index.values)

    # 9. Salvar índice e mapeamento melhorado
    print("💾 Salvando índice melhorado...")
    faiss.write_index(index, ARQUIVO_INDICE)

    # Mapeamento com informações adicionais
    df_mapeamento_melhorado = df_produtos[[
        'Marca', 'Modelo', 'Descrição', 'Valor', 'texto_embedding_melhorado'
    ]].copy()
    
    # Adicionar metadados do processamento
    df_mapeamento_melhorado['categoria_identificada'] = df_produtos.apply(
        lambda row: processador.identificar_categoria(row['Descrição']), axis=1
    )
    
    df_mapeamento_melhorado.to_csv(ARQUIVO_MAPEAMENTO, index=True)

    # 10. Estatísticas finais
    print("\n📊 ESTATÍSTICAS DO PROCESSAMENTO:")
    print("=" * 50)
    
    # Distribuição de categorias
    categorias_stats = df_mapeamento_melhorado['categoria_identificada'].value_counts()
    print("Distribuição de categorias:")
    for categoria, count in categorias_stats.head(10).items():
        print(f"  {categoria}: {count} produtos")
    
    # Qualidade dos embeddings
    print(f"\nQualidade dos embeddings:")
    print(f"  Dimensão dos vetores: {dimensao_vetor}")
    print(f"  Total de produtos indexados: {index.ntotal}")
    print(f"  Modelo utilizado: {NOME_MODELO}")
    
    print("\n🎉 INDEXAÇÃO MELHORADA CONCLUÍDA!")
    print("=" * 50)
    print(f"📁 Índice salvo em: {ARQUIVO_INDICE}")
    print(f"📄 Mapeamento salvo em: {ARQUIVO_MAPEAMENTO}")
    print("🚀 Execute agora o 'buscador_melhorado.py'")
    print("=" * 50)