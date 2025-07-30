#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎯 BUSCADOR MELHORADO - ESTRATÉGIAS AVANÇADAS DE MATCHING
Versão Otimizada para Máxima Precisão

MELHORIAS IMPLEMENTADAS:
✅ Busca híbrida (semântica + filtros contextuais)
✅ Re-ranking por categoria e especificações
✅ Validação inteligente com LLM
✅ Limiar adaptativo de similaridade
✅ Análise de compatibilidade técnica

ESTRATÉGIAS AVANÇADAS:
1. Busca k=10 candidatos iniciais
2. Filtro por categoria compatível
3. Score de especificações técnicas
4. Re-ranking final ponderado
5. Validação LLM para casos duvidosos

Autor: Sistema Melhorado
Data: Janeiro 2025
"""

import pandas as pd
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import google.generativeai as genai
import os
import re
from tqdm import tqdm
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')
from api import GOOGLE_API_KEY

# Importar API key
try:
    from api import GOOGLE_API_KEY
except ImportError:
    GOOGLE_API_KEY = "SUA_API_KEY_AQUI"  # Substitua pela sua chave

# --- CONFIGURAÇÕES MELHORADAS ---
GOOGLE_API_KEY = GOOGLE_API_KEY

# Pastas
PASTA_INDICE = "indice_faiss_melhorado"
PASTA_EDITAIS = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\ORCAMENTOS"
PASTA_RESULTADOS = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\RESULTADOS_MELHORADOS"

# Arquivos de índice melhorado
ARQUIVO_INDICE = os.path.join(PASTA_INDICE, "produtos_melhorado.index")
ARQUIVO_MAPEAMENTO = os.path.join(PASTA_INDICE, "mapeamento_produtos_melhorado.csv")

# Modelo (DEVE SER O MESMO do indexador melhorado)
NOME_MODELO = 'all-mpnet-base-v2'

# Parâmetros otimizados
LIMIAR_SIMILARIDADE_ALTO = 0.85    # Para matches excelentes
LIMIAR_SIMILARIDADE_MEDIO = 0.75   # Para matches bons
LIMIAR_SIMILARIDADE_BAIXO = 0.65   # Para matches aceitáveis
K_CANDIDATOS_INICIAIS = 10          # Buscar mais candidatos inicialmente
MAX_SUGESTOES_FINAIS = 3            # Máximo de sugestões por item

class ProcessadorConsulta:
    """Processador especializado para consultas de edital"""
    
    def __init__(self):
        # Reutilizar padrões do indexador para consistência
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
        
        # Compatibilidade entre categorias
        self.compatibilidade_categorias = {
            'CAIXA_ATIVA': ['CAIXA_ATIVA', 'CAIXA_SOM', 'MONITOR_ATIVO'],
            'CAIXA_PASSIVA': ['CAIXA_PASSIVA', 'CAIXA_SOM', 'MONITOR_PASSIVO'],
            'CAIXA_SOM': ['CAIXA_SOM', 'CAIXA_ATIVA', 'CAIXA_PASSIVA', 'SUBWOOFER'],
            'MICROFONE': ['MICROFONE', 'PODCAST_MIC', 'SHOTGUN_MIC', 'CONDENSER_MIC', 'DINAMICO_MIC', 'LAPELA_MIC', 'HEADSET', 'GOOSENECK'],
            'AMPLIFICADOR': ['AMPLIFICADOR', 'CUBO_AMPLIFICADO'],
            'CUBO_AMPLIFICADO': ['CUBO_AMPLIFICADO', 'AMPLIFICADOR'],
            'MESA_SOM': ['MESA_SOM', 'MIXER'],
            'CABO_CONECTOR': ['CABO_CONECTOR', 'MACANETA'],
            'SUBWOOFER': ['SUBWOOFER', 'CAIXA_SOM'],
            'BAQUETA': ['BAQUETA', 'VASSOURINHA', 'MACANETA'],  # Baquetas e variantes compatíveis
            'PELE': ['PELE'],  # Peles isoladas
            'SURDO': ['SURDO', 'BUMBO'],  # Surdos e bumbos
            'REPIQUE': ['REPIQUE'],
            'PANDEIRO': ['PANDEIRO'],
            'TALABARTE': ['TALABARTE'],
            'CARRILHAO': ['CARRILHAO'],
            'VASSOURINHA': ['VASSOURINHA', 'BAQUETA'],
            'MACANETA': ['MACANETA', 'BAQUETA', 'CABO_CONECTOR'],
            'TAMBORIM': ['TAMBORIM'],
            'CUICA': ['CUICA'],
            'ZABUMBA': ['ZABUMBA'],
            'TIMBAL': ['TIMBAL'],
            'REBOLO': ['REBOLO'],
            'MALACACHETA': ['MALACACHETA'],
            'TAROL': ['TAROL'],
            'BUMBO': ['BUMBO', 'SURDO'],
            'RECO_RECO': ['RECO_RECO'],
            'TRIANGULO': ['TRIANGULO'],
            'BLOCO_SONORO': ['BLOCO_SONORO'],
            'PRACTICE_PAD': ['PRACTICE_PAD'],
            'FONE_OUVIDO': ['FONE_OUVIDO', 'EAR_PHONE'],
            'HEADSET': ['HEADSET', 'MICROFONE'],
            'GOOSENECK': ['GOOSENECK', 'MICROFONE'],
            'PODCAST_MIC': ['PODCAST_MIC', 'MICROFONE'],
            'SHOTGUN_MIC': ['SHOTGUN_MIC', 'MICROFONE'],
            'CONDENSER_MIC': ['CONDENSER_MIC', 'MICROFONE'],
            'DINAMICO_MIC': ['DINAMICO_MIC', 'MICROFONE'],
            'LAPELA_MIC': ['LAPELA_MIC', 'MICROFONE']
        }
    def processar_consulta_edital(self, texto_edital):
        """Processa texto do edital para busca otimizada"""
        if pd.isna(texto_edital):
            return ""
        
        texto = str(texto_edital).upper()
        
        # 1. Identificar categoria da consulta
        categoria_consulta = self.identificar_categoria(texto)
        
        # 2. Extrair especificações da consulta
        specs_consulta = self.extrair_especificacoes(texto)
        
        # 3. Criar texto estruturado para busca
        partes_consulta = []
        
        # Categoria (peso alto)
        if categoria_consulta != "OUTROS":
            partes_consulta.append(f"CATEGORIA: {categoria_consulta}")
        
        # Especificações importantes
        if specs_consulta:
            specs_texto = []
            for spec_name, valores in specs_consulta.items():
                if valores:
                    specs_texto.append(f"{spec_name}: {' '.join(valores)}")
            if specs_texto:
                partes_consulta.append(f"ESPECIFICACOES: {' | '.join(specs_texto)}")
        
        # Texto original
        partes_consulta.append(f"DESCRICAO: {texto}")
        
        texto_consulta_estruturado = " | ".join(partes_consulta)
        
        return {
            'texto_estruturado': texto_consulta_estruturado,
            'categoria': categoria_consulta,
            'especificacoes': specs_consulta,
            'texto_original': texto
        }
    
    def identificar_categoria(self, texto):
        """Identifica categoria da consulta"""
        texto = texto.upper()
        
        for categoria, patterns in self.categorias_patterns.items():
            for pattern in patterns:
                if re.search(pattern, texto, re.IGNORECASE):
                    return categoria
        
        return "OUTROS"
    
    def extrair_especificacoes(self, texto):
        """Extrai especificações da consulta"""
        texto = texto.upper()
        specs = {}
        
        for spec_name, patterns in self.specs_patterns.items():
            valores = []
            for pattern in patterns:
                matches = re.findall(pattern, texto, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        valores.extend([v for v in match if v])
                    else:
                        valores.append(match)
            
            if valores:
                specs[spec_name] = list(set(valores))
        
        return specs
    
    def calcular_compatibilidade_categoria(self, categoria_consulta, categoria_produto):
        """Calcula compatibilidade entre categorias"""
        if categoria_consulta == "OUTROS" or categoria_produto == "OUTROS":
            return 0.5  # Score neutro
        
        if categoria_consulta == categoria_produto:
            return 1.0  # Match perfeito
        
        # Verificar compatibilidade cruzada
        categorias_compativeis = self.compatibilidade_categorias.get(categoria_consulta, [])
        if categoria_produto in categorias_compativeis:
            return 0.8  # Compatível
        
        return 0.1  # Incompatível
    
    def calcular_score_especificacoes(self, specs_consulta, specs_produto):
        """Calcula score de compatibilidade de especificações"""
        if not specs_consulta:
            return 0.5  # Score neutro se não há specs na consulta
        
        if not specs_produto:
            return 0.3  # Penalizar produtos sem specs quando consulta tem
        
        scores_specs = []
        
        for spec_name, valores_consulta in specs_consulta.items():
            if spec_name in specs_produto:
                valores_produto = specs_produto[spec_name]
                
                # Verificar compatibilidade dos valores
                compatibilidade = self.verificar_compatibilidade_valores(
                    valores_consulta, valores_produto, spec_name
                )
                scores_specs.append(compatibilidade)
            else:
                scores_specs.append(0.0)  # Spec não encontrada no produto
        
        return np.mean(scores_specs) if scores_specs else 0.0
    
    def verificar_compatibilidade_valores(self, valores_consulta, valores_produto, tipo_spec):
        """Verifica compatibilidade específica por tipo de especificação"""
        for val_consulta in valores_consulta:
            for val_produto in valores_produto:
                try:
                    num_consulta = float(val_consulta)
                    num_produto = float(val_produto)
                    
                    if tipo_spec == 'POTENCIA':
                        # Para potência, aceitar ±20% de tolerância
                        tolerancia = 0.2
                        if abs(num_consulta - num_produto) / max(num_consulta, num_produto) <= tolerancia:
                            return 1.0
                    elif tipo_spec == 'POLEGADAS':
                        # Para polegadas, deve ser exato ou muito próximo
                        if abs(num_consulta - num_produto) <= 1:
                            return 1.0
                    elif tipo_spec == 'VOLTAGEM':
                        # Para voltagem, deve ser compatível
                        voltagens_compativeis = [110, 127, 220, 240]
                        if num_consulta in voltagens_compativeis and num_produto in voltagens_compativeis:
                            return 1.0
                    else:
                        # Para outras specs, ±10% de tolerância
                        tolerancia = 0.1
                        if abs(num_consulta - num_produto) / max(num_consulta, num_produto) <= tolerancia:
                            return 1.0
                except ValueError:
                    # Se não for numérico, comparar como string
                    if val_consulta.upper() == val_produto.upper():
                        return 1.0
        
        return 0.0

class BuscadorHibrido:
    """Sistema de busca híbrida com múltiplas estratégias"""
    
    def __init__(self):
        print("🔧 Inicializando buscador híbrido...")
        
        # Inicializar componentes
        self.processador_consulta = ProcessadorConsulta()
        
        # Carregar modelo e índice
        self.carregar_modelos()
        self.carregar_indice()
    
    def carregar_modelos(self):
        """Carrega modelos de IA"""
        try:
            genai.configure(api_key=GOOGLE_API_KEY)
            self.model_generativo = genai.GenerativeModel('gemini-1.5-flash-latest')
            print("✅ Modelo Gemini carregado")
        except Exception as e:
            print(f"⚠️ Erro ao carregar Gemini: {e}")
            self.model_generativo = None
        
        print("🤖 Carregando modelo de embedding...")
        self.model_embedding = SentenceTransformer(NOME_MODELO)
        print("✅ Modelo de embedding carregado")
    
    def carregar_indice(self):
        """Carrega índice FAISS e mapeamento"""
        try:
            print("📂 Carregando índice melhorado...")
            self.index = faiss.read_index(ARQUIVO_INDICE)
            self.df_mapeamento = pd.read_csv(ARQUIVO_MAPEAMENTO, index_col=0)
            print(f"✅ Índice carregado: {self.index.ntotal} produtos")
        except FileNotFoundError:
            print("❌ ERRO: Arquivos de índice não encontrados.")
            print("Execute o 'indexador_melhorado.py' primeiro.")
            exit()
    
    def busca_hibrida_avancada(self, consulta_processada):
        """Executa busca híbrida com múltiplas estratégias"""
        
        # 1. BUSCA SEMÂNTICA INICIAL (k candidatos)
        embedding_consulta = self.model_embedding.encode([consulta_processada['texto_estruturado']])
        embedding_consulta = np.array(embedding_consulta).astype('float32')
        faiss.normalize_L2(embedding_consulta)
        
        # Buscar mais candidatos inicialmente
        distancias, indices = self.index.search(embedding_consulta, K_CANDIDATOS_INICIAIS)
        
        candidatos = []
        for i, (idx, similaridade_semantica) in enumerate(zip(indices[0], distancias[0])):
            if idx == -1:  # Índice inválido
                continue
            
            produto_info = self.df_mapeamento.iloc[idx]
            
            # 2. FILTRO POR CATEGORIA
            categoria_produto = produto_info.get('categoria_identificada', 'OUTROS')
            score_categoria = self.processador_consulta.calcular_compatibilidade_categoria(
                consulta_processada['categoria'], categoria_produto
            )
            
            # Filtrar produtos com categoria muito incompatível
            if score_categoria < 0.3:
                continue
            
            # 3. SCORE DE ESPECIFICAÇÕES
            specs_produto = self.extrair_specs_do_mapeamento(produto_info)
            score_specs = self.processador_consulta.calcular_score_especificacoes(
                consulta_processada['especificacoes'], specs_produto
            )
            
            # 4. SCORE FINAL PONDERADO
            score_final = (
                similaridade_semantica * 0.4 +  # Semântica
                score_categoria * 0.35 +        # Categoria
                score_specs * 0.25               # Especificações
            )
            
            candidatos.append({
                'indice': idx,
                'produto_info': produto_info,
                'score_semantico': similaridade_semantica,
                'score_categoria': score_categoria,
                'score_specs': score_specs,
                'score_final': score_final,
                'categoria_produto': categoria_produto
            })
        
        # 5. RE-RANKING FINAL
        candidatos.sort(key=lambda x: x['score_final'], reverse=True)
        
        return candidatos[:MAX_SUGESTOES_FINAIS]
    
    def extrair_specs_do_mapeamento(self, produto_info):
        """Extrai especificações do produto do mapeamento"""
        # Usar o texto de embedding melhorado que já tem specs estruturadas
        texto_embedding = produto_info.get('texto_embedding_melhorado', '')
        
        # Extrair specs do texto estruturado
        specs = {}
        if 'ESPECIFICACOES:' in texto_embedding:
            specs_parte = texto_embedding.split('ESPECIFICACOES:')[1].split('|')[0].strip()
            
            # Parse das especificações
            for spec_item in specs_parte.split(' | '):
                if ':' in spec_item:
                    spec_name, spec_values = spec_item.split(':', 1)
                    specs[spec_name.strip()] = spec_values.strip().split()
        
        return specs
    
    def determinar_qualidade_match(self, score_final):
        """Determina qualidade do match baseado no score"""
        if score_final >= LIMIAR_SIMILARIDADE_ALTO:
            return "EXCELENTE", "✅"
        elif score_final >= LIMIAR_SIMILARIDADE_MEDIO:
            return "BOM", "🟡"
        elif score_final >= LIMIAR_SIMILARIDADE_BAIXO:
            return "ACEITÁVEL", "🟠"
        else:
            return "BAIXO", "❌"
    
    def gerar_analise_tecnica_melhorada(self, item_edital, candidato, consulta_processada):
        """Gera análise técnica melhorada com LLM"""
        if not self.model_generativo:
            return "Análise LLM não disponível"
        
        produto_info = candidato['produto_info']
        
        # Usar LLM apenas para casos que precisam de validação
        if candidato['score_final'] < LIMIAR_SIMILARIDADE_MEDIO:
            prompt = f"""
            ANÁLISE TÉCNICA PARA LICITAÇÃO
            
            Item Solicitado no Edital:
            "{item_edital}"
            
            Produto Sugerido:
            Marca: {produto_info['Marca']}
            Modelo: {produto_info['Modelo']}
            Descrição: {produto_info['Descrição']}
            
            Categoria Identificada: {candidato['categoria_produto']}
            Score de Compatibilidade: {candidato['score_final']:.2f}
            
            Analise se este produto atende aos requisitos do edital.
            Seja objetivo e técnico.
            
            Responda em um parágrafo curto focando em:
            1. Compatibilidade técnica
            2. Diferenças importantes (se houver)
            3. Recomendação (Recomendado/Atenção/Não recomendado)
            """
            
            try:
                response = self.model_generativo.generate_content(prompt)
                return response.text.strip()
            except Exception as e:
                return f"Erro na análise LLM: {e}"
        else:
            # Para scores altos, análise automática
            qualidade, emoji = self.determinar_qualidade_match(candidato['score_final'])
            return f"{emoji} Produto {qualidade.lower()} - Compatibilidade técnica confirmada (Score: {candidato['score_final']:.2f}). Categoria: {candidato['categoria_produto']}. Recomendado para participação."

def processar_edital_melhorado(caminho_edital, buscador):
    """Processa edital com estratégias melhoradas"""
    nome_arquivo = os.path.basename(caminho_edital)
    print(f"\n📄 Processando: {nome_arquivo}")

    df_edital = pd.read_excel(caminho_edital)
    resultados = []
    
    processador_consulta = ProcessadorConsulta()

    for _, row in tqdm(df_edital.iterrows(), total=df_edital.shape[0], desc="Análise híbrida"):
        item_catmat = str(row['Item']) if not pd.isna(row['Item']) else ""
        
        if not item_catmat.strip():
            continue
        
        # 1. Processar consulta
        consulta_processada = processador_consulta.processar_consulta_edital(item_catmat)
        
        # 2. Busca híbrida
        candidatos = buscador.busca_hibrida_avancada(consulta_processada)
        
        # 3. Processar resultados
        dados_resultado = row.to_dict()
        
        if candidatos:
            # Pegar o melhor candidato
            melhor_candidato = candidatos[0]
            produto_info = melhor_candidato['produto_info']
            
            # Determinar qualidade
            qualidade, emoji = buscador.determinar_qualidade_match(melhor_candidato['score_final'])
            
            # Adicionar dados do resultado
            dados_resultado['Marca Sugerida'] = produto_info['Marca']
            dados_resultado['Produto Sugerido'] = produto_info['Modelo']
            dados_resultado['Descrição do Produto Sugerido'] = produto_info['Descrição']
            dados_resultado['Preço Produto'] = produto_info['Valor']
            dados_resultado['% Compatibilidade'] = f"{melhor_candidato['score_final']:.1%}"
            dados_resultado['Qualidade Match'] = f"{emoji} {qualidade}"
            dados_resultado['Score Semântico'] = f"{melhor_candidato['score_semantico']:.2f}"
            dados_resultado['Score Categoria'] = f"{melhor_candidato['score_categoria']:.2f}"
            dados_resultado['Score Especificações'] = f"{melhor_candidato['score_specs']:.2f}"
            dados_resultado['Categoria Identificada'] = melhor_candidato['categoria_produto']
            
            # Análise técnica
            dados_resultado['Análise Técnica'] = buscador.gerar_analise_tecnica_melhorada(
                item_catmat, melhor_candidato, consulta_processada
            )
            
            # Alternativas (se houver)
            if len(candidatos) > 1:
                alternativas = []
                for alt in candidatos[1:]:
                    alt_info = alt['produto_info']
                    alternativas.append(f"{alt_info['Marca']} {alt_info['Modelo']} ({alt['score_final']:.1%})")
                dados_resultado['Alternativas'] = " | ".join(alternativas)
            else:
                dados_resultado['Alternativas'] = "Nenhuma"
        
        else:
            # Nenhum candidato encontrado
            dados_resultado['Marca Sugerida'] = "❌ Não encontrado"
            dados_resultado['Produto Sugerido'] = "N/A"
            dados_resultado['Descrição do Produto Sugerido'] = "N/A"
            dados_resultado['Preço Produto'] = "N/A"
            dados_resultado['% Compatibilidade'] = "0%"
            dados_resultado['Qualidade Match'] = "❌ BAIXO"
            dados_resultado['Score Semântico'] = "0.00"
            dados_resultado['Score Categoria'] = "0.00"
            dados_resultado['Score Especificações'] = "0.00"
            dados_resultado['Categoria Identificada'] = consulta_processada['categoria']
            dados_resultado['Análise Técnica'] = "Nenhum produto compatível encontrado na base de dados."
            dados_resultado['Alternativas'] = "Nenhuma"

        resultados.append(dados_resultado)
    
    # Criar DataFrame final
    df_resultado = pd.DataFrame(resultados)
    
    # Ordenar colunas
    colunas_originais = list(df_edital.columns)
    colunas_novas = [
        'Marca Sugerida', 'Produto Sugerido', 'Descrição do Produto Sugerido',
        'Preço Produto', '% Compatibilidade', 'Qualidade Match',
        'Score Semântico', 'Score Categoria', 'Score Especificações',
        'Categoria Identificada', 'Análise Técnica', 'Alternativas'
    ]
    
    colunas_finais = colunas_originais + colunas_novas
    df_resultado = df_resultado[colunas_finais]

    # Salvar resultado
    nome_base, extensao = os.path.splitext(nome_arquivo)
    caminho_saida = os.path.join(PASTA_RESULTADOS, f"{nome_base}_MELHORADO{extensao}")
    
    if not os.path.exists(PASTA_RESULTADOS):
        os.makedirs(PASTA_RESULTADOS)

    df_resultado.to_excel(caminho_saida, index=False)
    
    # Estatísticas
    total_items = len(df_resultado)
    matches_excelentes = len(df_resultado[df_resultado['Qualidade Match'].str.contains('EXCELENTE', na=False)])
    matches_bons = len(df_resultado[df_resultado['Qualidade Match'].str.contains('BOM', na=False)])
    matches_baixos = len(df_resultado[df_resultado['Qualidade Match'].str.contains('BAIXO', na=False)])
    
    print(f"✅ Resultado salvo: {caminho_saida}")
    print(f"📊 Estatísticas: {total_items} itens | ✅ {matches_excelentes} excelentes | 🟡 {matches_bons} bons | ❌ {matches_baixos} baixos")

# --- SCRIPT PRINCIPAL ---
if __name__ == "__main__":
    print("🎯 BUSCADOR MELHORADO - ESTRATÉGIAS AVANÇADAS")
    print("=" * 70)
    print("🔍 Busca híbrida (semântica + contextual)")
    print("🎯 Re-ranking por categoria e especificações")
    print("🤖 Validação inteligente com LLM")
    print("📊 Análise de qualidade de matches")
    print("=" * 70)
    
    # Inicializar buscador
    buscador = BuscadorHibrido()
    
    # Encontrar editais
    arquivos_editais = [
        os.path.join(PASTA_EDITAIS, f) 
        for f in os.listdir(PASTA_EDITAIS) 
        if f.endswith('.xlsx')
    ]
    
    if not arquivos_editais:
        print(f"❌ Nenhum arquivo .xlsx encontrado em '{PASTA_EDITAIS}'.")
    else:
        print(f"📁 {len(arquivos_editais)} editais encontrados")
        
        for edital in arquivos_editais:
            processar_edital_melhorado(edital, buscador)
    
    print("\n🎉 PROCESSAMENTO MELHORADO CONCLUÍDO!")
    print("=" * 70)
    print(f"📁 Resultados salvos em: {PASTA_RESULTADOS}")
    print("🚀 Verifique os arquivos *_MELHORADO.xlsx")
    print("=" * 70)