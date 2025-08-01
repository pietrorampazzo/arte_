#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎯 SISTEMA DE MATCHING BASEADO NO MODELO CATMAT
Versão Especializada para Licitações Governamentais

BASEADO NO CATMAT (Catálogo de Materiais do Governo Federal):
- Estrutura padronizada de especificações técnicas
- Características organizadas por categorias
- Códigos NCM/NBS para classificação fiscal
- Unidades de medida padronizadas
- Aplicação de margem de preferência

FUNCIONALIDADES:
- Parsing de especificações no formato CATMAT
- Matching por categoria e características técnicas
- Análise de margem de preferência nacional
- Compatibilidade com editais governamentais
- Relatórios específicos para licitações

Autor: Sistema CATMAT
Data: Janeiro 2025
"""

import os
import re
import json
import pandas as pd
import numpy as np
from pathlib import Path
import warnings
from datetime import datetime
warnings.filterwarnings('ignore')
from transformers import AutoTokenizer, AutoModel
import torch

# Importações opcionais
try:
    from transformers import pipeline
    TRANSFORMERS_AVAILABLE = True
    print("✅ Transformers disponível")
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    print("⚠️ Transformers não disponível - usando análise básica")

class ConfigCATMAT:
    """Configurações baseadas no modelo CATMAT"""
    
    # 🔧 CAMINHOS DOS ARQUIVOS
    PRODUTOS_PATH = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\PRODUTOS.xlsx"
    ORCAMENTOS_PATH = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\ORCAMENTOS"
    CATMAT_JSON_PATH = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\gov_reges.json"  # Opcional
    
    # Parâmetros específicos para licitações
    MARGEM_DISPUTA = 0.53  # 53%
    MARGEM_PREFERENCIA_NACIONAL = 0.08  # 8% para produtos nacionais
    MIN_COMPATIBILIDADE = 85.0  # Rigoroso para licitações
    MIN_COMPATIBILIDADE_CATEGORIA = 90.0  # Categoria deve ser muito precisa
    MIN_COMPATIBILIDADE_CARACTERISTICAS = 75.0  # Características técnicas
    MAX_SUGESTOES = 3
    
    # Configurações do pipeline
    MODELO_PIPELINE = "sentence-transformers/all-MiniLM-L6-v2"

class ProcessadorCATMAT:
    """Processador especializado no formato CATMAT"""
    
    def __init__(self):
        print("🔄 Inicializando processador contextual...")

        self.pipeline_embeddings = None

        if TRANSFORMERS_AVAILABLE:
            try:
                print("📥 Carregando modelo para análise contextual (com truncation)...")
                self.pipeline_embeddings = pipeline(
                    "feature-extraction",
                    model=AutoModel.from_pretrained("sentence-transformers/all-MiniLM-L6-v2"),
                    tokenizer=AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2"),
                    truncation=True,
                    max_length=512,
                    return_tensors="np"
                )
                print("✅ Pipeline contextual inicializado com truncamento")
            except Exception as e:
                print("⚠️ Erro ao carregar pipeline: " + str(e))
                self.pipeline_embeddings = None
    
    def carregar_catmat(self):
        """Carrega dados do CATMAT para referência"""
        try:
            if os.path.exists(ConfigCATMAT.CATMAT_JSON_PATH):
                with open(ConfigCATMAT.CATMAT_JSON_PATH, 'r', encoding='utf-8') as f:
                    self.catmat_data = json.load(f)
                print("✅ Dados CATMAT carregados: " + str(len(self.catmat_data)) + " itens")
            else:
                print("⚠️ Arquivo CATMAT não encontrado - usando análise padrão")
        except Exception as e:
            print("⚠️ Erro ao carregar CATMAT: " + str(e))
    
    def normalizar_texto_catmat(self, texto):
        """Normalização específica para padrão CATMAT"""
        if pd.isna(texto) or not texto:
            return ""
        
        texto = str(texto).upper()
        
        # Remover acentos mantendo estrutura CATMAT
        acentos = {
            'Á': 'A', 'À': 'A', 'Ã': 'A', 'Â': 'A', 'Ä': 'A',
            'É': 'E', 'È': 'E', 'Ê': 'E', 'Ë': 'E',
            'Í': 'I', 'Ì': 'I', 'Î': 'I', 'Ï': 'I',
            'Ó': 'O', 'Ò': 'O', 'Õ': 'O', 'Ô': 'O', 'Ö': 'O',
            'Ú': 'U', 'Ù': 'U', 'Û': 'U', 'Ü': 'U',
            'Ç': 'C', 'Ñ': 'N'
        }
        
        for k, v in acentos.items():
            texto = texto.replace(k, v)
        
        # Preservar estrutura de características CATMAT
        texto = re.sub(r'[^\w\s\-\+\(\)\[\]:,/]', ' ', texto)
        texto = re.sub(r'\s+', ' ', texto).strip()
        
        return texto
    
    def extrair_categoria_catmat(self, texto):
        """Extrai categoria principal no formato CATMAT"""
        texto_norm = self.normalizar_texto_catmat(texto)
        
        # Categorias baseadas no CATMAT analisado
        categorias_catmat = {
            # Instrumentos Musicais
            'AMPLIFICADOR_SOM': ['AMPLIFICADOR', 'AMPLIFIER'],
            'MICROFONE': ['MICROFONE', 'MICROPHONE'],
            'PIANO': ['PIANO', 'TECLADO', 'KEYBOARD'],
            'ESTANTE_PARTITURA': ['ESTANTE', 'PARTITURA', 'MUSIC_STAND'],
            'INSTRUMENTO_PERCUSSAO': ['PERCUSSAO', 'PERCUSSION', 'BATERIA', 'TAMBOR', 'PANDEIRO', 'TRIANGULO', 'PRATO', 'SURDO', 'CAJON'],
            'INSTRUMENTO_SOPRO': ['SOPRO', 'WIND', 'FLAUTA', 'SAXOFONE', 'TROMPETE', 'TROMBONE', 'CLARINETE', 'BOMBARDINO'],
            'INSTRUMENTO_CORDA': ['CORDA', 'STRING', 'VIOLAO', 'GUITARRA', 'BAIXO', 'VIOLINO', 'VIOLA'],
            'PECAS_ACESSORIOS': ['PECAS', 'ACESSORIOS', 'ENCORDOAMENTO', 'PELE', 'PALHETA', 'BOQUILHA'],
            'MESA_AUDIO': ['MESA', 'AUDIO', 'MIXER', 'SWITCHER'],
            'CAIXA_SOM': ['CAIXA', 'SOM', 'SPEAKER', 'ALTO_FALANTE'],
            
            # Equipamentos de TI
            'CONECTOR_CABO': ['CONECTOR', 'CABO', 'RJ45', 'CONNECTOR'],
            'CABO_REDE': ['CABO', 'REDE', 'NETWORK', 'UTP'],
            
            # Outros
            'MATERIAL_CONSUMO': ['MATERIAL', 'CONSUMO'],
            'EQUIPAMENTO_ELETRONICO': ['EQUIPAMENTO', 'ELETRONICO', 'ELECTRONIC']
        }
        
        categorias_encontradas = []
        for categoria, palavras_chave in categorias_catmat.items():
            for palavra in palavras_chave:
                if palavra in texto_norm:
                    categorias_encontradas.append(categoria)
                    break
        
        return list(set(categorias_encontradas))
    
    def extrair_caracteristicas_catmat(self, texto):
        """Extrai características no formato CATMAT (#Característica: Valor)"""
        caracteristicas = {}
        texto_norm = self.normalizar_texto_catmat(texto)
        
        # Padrões específicos do CATMAT
        padroes_catmat = {
            'TIPO': [
                r'TIPO\s*:?\s*([^,|#]+)',
                r'#TIPO\s*:\s*([^|]+)'
            ],
            'MATERIAL': [
                r'MATERIAL\s*:?\s*([^,|#]+)',
                r'#MATERIAL\s*:\s*([^|]+)'
            ],
            'TAMANHO': [
                r'TAMANHO\s*:?\s*([^,|#]+)',
                r'#TAMANHO\s*:\s*([^|]+)',
                r'(\d+)\s*(CM|MM|M|POL|POLEGADAS?)'
            ],
            'POTENCIA': [
                r'POTENCIA\s*:?\s*([^,|#]+)',
                r'#POTENCIA\s*:\s*([^|]+)',
                r'(\d+)\s*(W|WATTS?)'
            ],
            'TENSAO': [
                r'TENSAO\s*:?\s*([^,|#]+)',
                r'#TENSAO\s*:\s*([^|]+)',
                r'(\d+)\s*(V|VOLTS?)'
            ],
            'FREQUENCIA': [
                r'FREQUENCIA\s*:?\s*([^,|#]+)',
                r'#FREQUENCIA\s*:\s*([^|]+)',
                r'(\d+)\s*(HZ|KHZ|MHZ)'
            ],
            'QUANTIDADE': [
                r'QUANTIDADE\s*:?\s*([^,|#]+)',
                r'#QUANTIDADE\s*:\s*([^|]+)',
                r'(\d+)\s*(UN|UNIDADES?|PECAS?)'
            ],
            'ACABAMENTO': [
                r'ACABAMENTO\s*:?\s*([^,|#]+)',
                r'#ACABAMENTO\s*:\s*([^|]+)'
            ],
            'COR': [
                r'COR\s*:?\s*([^,|#]+)',
                r'#COR\s*:\s*([^|]+)'
            ],
            'APLICACAO': [
                r'APLICACAO\s*:?\s*([^,|#]+)',
                r'#APLICACAO\s*:\s*([^|]+)'
            ],
            'COMPONENTES': [
                r'COMPONENTES\s*:?\s*([^,|#]+)',
                r'#COMPONENTES\s*:\s*([^|]+)'
            ],
            'CARACTERISTICAS_ADICIONAIS': [
                r'CARACTERISTICAS\s+ADICIONAIS\s*:?\s*([^,|#]+)',
                r'#CARACTERISTICAS\s+ADICIONAIS\s*:\s*([^|]+)'
            ]
        }
        
        for categoria, padroes in padroes_catmat.items():
            valores_encontrados = []
            for padrao in padroes:
                matches = re.findall(padrao, texto_norm)
                for match in matches:
                    if isinstance(match, tuple):
                        valor = ' '.join(str(m) for m in match if m).strip()
                    else:
                        valor = str(match).strip()
                    
                    if valor and len(valor) > 1:
                        valores_encontrados.append(valor)
            
            if valores_encontrados:
                caracteristicas[categoria] = list(set(valores_encontrados))
        
        return caracteristicas
    
    def calcular_compatibilidade_catmat(self, desc_edital, produto):
        """Calcula compatibilidade usando metodologia CATMAT"""
        
        # Preparar texto do produto
        texto_produto = ""
        for campo in ['MODELO', 'DESCRIÇÃO', 'DESCRICAO', 'DESCRIPTION']:
            if campo in produto and pd.notna(produto[campo]):
                texto_produto += " " + str(produto[campo])
        
        if not texto_produto.strip():
            return 0.0, {}
        
        # 1. ANÁLISE DE CATEGORIA (40%) - Baseada no CATMAT
        categorias_edital = self.extrair_categoria_catmat(desc_edital)
        categorias_produto = self.extrair_categoria_catmat(texto_produto)
        
        score_categoria = 0.0
        if categorias_edital and categorias_produto:
            categorias_comuns = set(categorias_edital) & set(categorias_produto)
            if categorias_comuns:
                score_categoria = (len(categorias_comuns) / len(categorias_edital)) * 100
            else:
                # Categoria incompatível - rejeitar
                return 0.0, {
                    'categoria': 0.0,
                    'caracteristicas': 0.0,
                    'semantico': 0.0,
                    'motivo_rejeicao': 'Categoria CATMAT incompatível',
                    'categorias_edital': categorias_edital,
                    'categorias_produto': categorias_produto
                }
        else:
            score_categoria = 30.0  # Score neutro se não identificar categoria
        
        # 2. ANÁLISE DE CARACTERÍSTICAS CATMAT (35%)
        carac_edital = self.extrair_caracteristicas_catmat(desc_edital)
        carac_produto = self.extrair_caracteristicas_catmat(texto_produto)
        
        score_caracteristicas = 0.0
        detalhes_caracteristicas = {}
        
        if carac_edital:
            total_caracteristicas = len(carac_edital)
            caracteristicas_atendidas = 0
            
            for categoria_carac, valores_edital in carac_edital.items():
                if categoria_carac in carac_produto:
                    valores_produto = carac_produto[categoria_carac]
                    
                    # Verificar compatibilidade dos valores
                    compativel = self.verificar_compatibilidade_valores(valores_edital, valores_produto)
                    
                    if compativel:
                        caracteristicas_atendidas += 1
                        detalhes_caracteristicas[categoria_carac] = {
                            'edital': valores_edital,
                            'produto': valores_produto,
                            'status': 'COMPATIVEL'
                        }
                    else:
                        detalhes_caracteristicas[categoria_carac] = {
                            'edital': valores_edital,
                            'produto': valores_produto,
                            'status': 'INCOMPATIVEL'
                        }
                else:
                    detalhes_caracteristicas[categoria_carac] = {
                        'edital': valores_edital,
                        'produto': [],
                        'status': 'NAO_INFORMADO'
                    }
            
            score_caracteristicas = (caracteristicas_atendidas / total_caracteristicas) * 100
        
        # 3. ANÁLISE SEMÂNTICA (25%)
        score_semantico = self.calcular_similaridade_semantica(desc_edital, texto_produto)
        
        # 4. VERIFICAÇÃO DE CRITÉRIOS MÍNIMOS
        if score_categoria < ConfigCATMAT.MIN_COMPATIBILIDADE_CATEGORIA:
            return 0.0, {
                'categoria': round(score_categoria, 2),
                'caracteristicas': round(score_caracteristicas, 2),
                'semantico': round(score_semantico, 2),
                'motivo_rejeicao': 'Categoria insuficiente (< ' + str(ConfigCATMAT.MIN_COMPATIBILIDADE_CATEGORIA) + '%)',
                'categorias_edital': categorias_edital,
                'categorias_produto': categorias_produto,
                'detalhes_caracteristicas': detalhes_caracteristicas
            }
        
        if score_caracteristicas < ConfigCATMAT.MIN_COMPATIBILIDADE_CARACTERISTICAS:
            return 0.0, {
                'categoria': round(score_categoria, 2),
                'caracteristicas': round(score_caracteristicas, 2),
                'semantico': round(score_semantico, 2),
                'motivo_rejeicao': 'Características insuficientes (< ' + str(ConfigCATMAT.MIN_COMPATIBILIDADE_CARACTERISTICAS) + '%)',
                'categorias_edital': categorias_edital,
                'categorias_produto': categorias_produto,
                'detalhes_caracteristicas': detalhes_caracteristicas
            }
        
        # 5. SCORE FINAL PONDERADO
        score_final = (
            score_categoria * 0.40 +
            score_caracteristicas * 0.35 +
            score_semantico * 0.25
        )
        
        detalhes = {
            'categoria': round(score_categoria, 2),
            'caracteristicas': round(score_caracteristicas, 2),
            'semantico': round(score_semantico, 2),
            'final': round(score_final, 2),
            'categorias_edital': categorias_edital,
            'categorias_produto': categorias_produto,
            'detalhes_caracteristicas': detalhes_caracteristicas,
            'aprovado': score_final >= ConfigCATMAT.MIN_COMPATIBILIDADE
        }
        
        return round(score_final, 2), detalhes
    
    def verificar_compatibilidade_valores(self, valores_edital, valores_produto):
        """Verifica se os valores são compatíveis"""
        for val_edital in valores_edital:
            for val_produto in valores_produto:
                # Normalizar valores
                val_e_norm = self.normalizar_texto_catmat(val_edital)
                val_p_norm = self.normalizar_texto_catmat(val_produto)
                
                # Verificar compatibilidade exata ou parcial
                if val_e_norm == val_p_norm:
                    return True
                elif val_e_norm in val_p_norm or val_p_norm in val_e_norm:
                    return True
                elif self.verificar_compatibilidade_numerica(val_e_norm, val_p_norm):
                    return True
        
        return False
    
    def verificar_compatibilidade_numerica(self, val1, val2):
        """Verifica compatibilidade de valores numéricos"""
        # Extrair números e unidades
        match1 = re.search(r'(\d+(?:\.\d+)?)\s*([A-Z]*)', val1)
        match2 = re.search(r'(\d+(?:\.\d+)?)\s*([A-Z]*)', val2)
        
        if match1 and match2:
            num1, unit1 = match1.groups()
            num2, unit2 = match2.groups()
            
            # Se unidades são iguais, verificar tolerância numérica
            if unit1 == unit2:
                try:
                    n1, n2 = float(num1), float(num2)
                    # Tolerância de 10%
                    return abs(n1 - n2) / max(n1, n2) <= 0.1
                except:
                    pass
        
        return False
        
    def calcular_similaridade_semantica(self, texto1, texto2):
        """Calcula similaridade semântica"""
        if self.pipeline_embeddings:
            try:
                texto1_norm = self.normalizar_texto_catmat(texto1)
                texto2_norm = self.normalizar_texto_catmat(texto2)

                if not texto1_norm or not texto2_norm:
                    return 0.0

                emb1 = self.pipeline_embeddings(texto1_norm)
                emb2 = self.pipeline_embeddings(texto2_norm)

                emb1_mean = np.array(emb1).mean(axis=1).flatten()
                emb2_mean = np.array(emb2).mean(axis=1).flatten()

                dot_product = np.dot(emb1_mean, emb2_mean)
                norm1 = np.linalg.norm(emb1_mean)
                norm2 = np.linalg.norm(emb2_mean)

                if norm1 == 0 or norm2 == 0:
                    return 0.0

                similarity = dot_product / (norm1 * norm2)
                return float(similarity * 100)

            except Exception as e:
                print("⚠️ Erro no pipeline semântico:", e)

        return self.calcular_similaridade_palavras_contextuais(texto1, texto2)

    
    def calcular_jaccard_melhorado(self, texto1, texto2):
        """Jaccard com peso para palavras importantes"""
        palavras1 = set(self.normalizar_texto_catmat(texto1).split())
        palavras2 = set(self.normalizar_texto_catmat(texto2).split())
        
        if not palavras1 or not palavras2:
            return 0.0
        
        # Palavras importantes (> 3 caracteres)
        importantes1 = set(p for p in palavras1 if len(p) > 3)
        importantes2 = set(p for p in palavras2 if len(p) > 3)
        
        # Jaccard básico
        intersecao = palavras1.intersection(palavras2)
        uniao = palavras1.union(palavras2)
        jaccard_basico = (len(intersecao) / len(uniao)) * 100 if uniao else 0.0
        
        # Bônus para palavras importantes
        if importantes1 and importantes2:
            intersecao_imp = importantes1.intersection(importantes2)
            bonus = (len(intersecao_imp) / len(importantes1)) * 25
        else:
            bonus = 0
        
        return min(jaccard_basico + bonus, 100.0)

class AnalisadorLicitacao:
    """Análise específica para licitações governamentais"""
    
    def __init__(self, processador):
        self.processador = processador
    
    def analisar_edital(self, descricao):
        """Análise completa do edital"""
        texto = descricao.upper()
        
        # Verificar margem de preferência
        tem_margem_preferencia = self.verificar_margem_preferencia(texto)
        
        # Verificar direcionamento
        analise_direcionamento = self.analisar_direcionamento(texto)
        
        # Verificar sustentabilidade
        criterios_sustentabilidade = self.verificar_criterios_sustentabilidade(texto)
        
        return {
            'margem_preferencia': tem_margem_preferencia,
            'direcionamento': analise_direcionamento,
            'sustentabilidade': criterios_sustentabilidade,
            'recomendacao_geral': self.gerar_recomendacao(analise_direcionamento, tem_margem_preferencia)
        }
    
    def verificar_margem_preferencia(self, texto):
        """Verifica se aplica margem de preferência nacional"""
        indicadores_preferencia = [
            'MARGEM.*PREFERENCIA',
            'PRODUTO.*NACIONAL',
            'FABRICACAO.*NACIONAL',
            'ORIGEM.*NACIONAL',
            'MPB.*MANUFATURADO',
            'DECRETO.*7174'
        ]
        
        for indicador in indicadores_preferencia:
            if re.search(indicador, texto):
                return True
        
        return False
    
    def analisar_direcionamento(self, texto):
        """Análise rigorosa de direcionamento para licitações"""
        
        # Padrões críticos
        padroes_criticos = [
            (r'\bMARCA\s+([A-Z][A-Z0-9]*)', 'CRITICO', 'Especificação de marca específica'),
            (r'\bEXCLUSIVAMENTE\b', 'CRITICO', 'Uso de termo exclusivo'),
            (r'\bAPENAS\s+([A-Z]+)', 'CRITICO', 'Limitação a fornecedor específico'),
            (r'\bUNICAMENTE\b', 'CRITICO', 'Restrição única'),
            (r'\bSOMENTE\s+([A-Z]+)', 'CRITICO', 'Limitação restritiva')
        ]
        
        # Padrões de alerta
        padroes_alerta = [
            (r'\bREFERENCIA\s+([A-Z]+)', 'ALERTA', 'Referência a marca específica'),
            (r'\bMODELO\s+([A-Z0-9]+)', 'ALERTA', 'Modelo específico mencionado'),
            (r'\bFABRICANTE\s+([A-Z]+)', 'ALERTA', 'Fabricante específico')
        ]
        
        # Cláusulas de proteção
        clausulas_protecao = [
            r'\bOU\s+EQUIVALENTE\b',
            r'\bOU\s+SIMILAR\b',
            r'\bOU\s+COMPATIVEL\b',
            r'\bDE\s+QUALIDADE\s+EQUIVALENTE\b'
        ]
        
        problemas_criticos = []
        problemas_alerta = []
        tem_protecao = False
        
        # Verificar padrões críticos
        for padrao, nivel, descricao in padroes_criticos:
            if re.search(padrao, texto):
                problemas_criticos.append(descricao)
        
        # Verificar padrões de alerta
        for padrao, nivel, descricao in padroes_alerta:
            if re.search(padrao, texto):
                problemas_alerta.append(descricao)
        
        # Verificar cláusulas de proteção
        for clausula in clausulas_protecao:
            if re.search(clausula, texto):
                tem_protecao = True
                break
        
        # Determinar risco
        if problemas_criticos and not tem_protecao:
            risco = 'CRITICO'
            acao = 'IMPUGNAR_IMEDIATAMENTE'
            observacao = 'Direcionamento crítico identificado sem cláusula de equivalência. IMPUGNAÇÃO OBRIGATÓRIA conforme Lei 14.133/21 (Art. 7º §5º).'
        elif problemas_criticos and tem_protecao:
            risco = 'MEDIO'
            acao = 'ANALISAR_JURIDICAMENTE'
            observacao = 'Direcionamento identificado, mas com cláusula de equivalência. Avaliar se a cláusula é suficiente.'
        elif problemas_alerta:
            risco = 'BAIXO'
            acao = 'MONITORAR'
            observacao = 'Especificações com referências, mas dentro dos padrões aceitáveis.'
        else:
            risco = 'NENHUM'
            acao = 'PARTICIPAR'
            observacao = 'Especificação técnica adequada para competição.'
        
        return {
            'risco': risco,
            'acao_recomendada': acao,
            'observacao': observacao,
            'problemas_criticos': problemas_criticos,
            'problemas_alerta': problemas_alerta,
            'tem_clausula_protecao': tem_protecao
        }
    
    def verificar_criterios_sustentabilidade(self, texto):
        """Verifica critérios de sustentabilidade"""
        criterios = {
            'eficiencia_energetica': bool(re.search(r'EFICIENCIA.*ENERGETICA|SELO.*PROCEL|ENERGY.*STAR', texto)),
            'material_reciclado': bool(re.search(r'MATERIAL.*RECICLADO|RECICLAVEL', texto)),
            'certificacao_ambiental': bool(re.search(r'ISO.*14001|CERTIFICACAO.*AMBIENTAL', texto)),
            'reducao_residuos': bool(re.search(r'REDUCAO.*RESIDUOS|MENOS.*EMBALAGEM', texto))
        }
        
        return criterios
    
    def gerar_recomendacao(self, analise_direcionamento, tem_margem_preferencia):
        """Gera recomendação geral"""
        if analise_direcionamento['risco'] == 'CRITICO':
            return 'NÃO PARTICIPAR - IMPUGNAR EDITAL'
        elif analise_direcionamento['risco'] == 'MEDIO':
            return 'PARTICIPAR COM CAUTELA - ANÁLISE JURÍDICA'
        elif tem_margem_preferencia:
            return 'PARTICIPAR - CONSIDERAR MARGEM DE PREFERÊNCIA'
        else:
            return 'PARTICIPAR NORMALMENTE'

class MatchingCATMAT:
    """Sistema principal baseado no modelo CATMAT"""
    
    def __init__(self):
        print("🎯 SISTEMA DE MATCHING BASEADO NO MODELO CATMAT")
        print("=" * 70)
        print("Especializado para Licitações Governamentais")
        print("Baseado no Catálogo de Materiais do Governo Federal")
        print("=" * 70)
        print("🚀 Inicializando sistema CATMAT...")
        
        self.processador = ProcessadorCATMAT()
        self.analisador = AnalisadorLicitacao(self.processador)
        self.produtos_df = None
        self.resultados = []
        self.estatisticas = {
            'total_analisados': 0,
            'rejeitados_categoria': 0,
            'rejeitados_caracteristicas': 0,
            'aprovados': 0,
            'com_margem_preferencia': 0
        }
    
    def verificar_caminhos(self):
        """Verifica caminhos dos arquivos"""
        print("\n🔍 Verificando caminhos...")
        
        caminhos_produtos = [
            ConfigCATMAT.PRODUTOS_PATH,
            r"C:\Users\pietr\Meu Drive\ARTE\PRODUTOS.xlsx",
            r"C:\Users\pietr\.vscode\arte_comercial\PRODUTOS.xlsx"
        ]
        
        caminhos_orcamentos = [
            ConfigCATMAT.ORCAMENTOS_PATH,
            r"C:\Users\pietr\Meu Drive\ARTE\AUTO\ORCAMENTOS",
            r"C:\Users\pietr\.vscode\arte_comercial\ORCAMENTOS"
        ]
        
        produto_encontrado = None
        for caminho in caminhos_produtos:
            if os.path.exists(caminho):
                produto_encontrado = caminho
                print("✅ Produtos: " + caminho)
                break
        
        orcamento_encontrado = None
        for caminho in caminhos_orcamentos:
            if os.path.exists(caminho):
                orcamento_encontrado = caminho
                print("✅ Orçamentos: " + caminho)
                break
        
        return produto_encontrado, orcamento_encontrado
    
    def carregar_dados(self):
        """Carrega dados"""
        print("\n📂 Carregando dados...")
        
        try:
            produto_path, orcamento_path = self.verificar_caminhos()
            
            if not produto_path:
                print("❌ Arquivo PRODUTOS.xlsx não encontrado")
                return False
            
            if not orcamento_path:
                print("❌ Pasta ORCAMENTOS não encontrada")
                return False
            
            # Carregar produtos
            self.produtos_df = pd.read_excel(produto_path)
            self.produtos_df.columns = self.produtos_df.columns.str.strip()
            print("✅ " + str(len(self.produtos_df)) + " produtos carregados")
            
            # Listar orçamentos
            pasta = Path(orcamento_path)
            self.arquivos = list(pasta.glob("*.xlsx"))
            print("✅ " + str(len(self.arquivos)) + " arquivos encontrados")
            
            return len(self.arquivos) > 0
            
        except Exception as e:
            print("❌ Erro: " + str(e))
            return False
    
    def extrair_valor(self, valor):
        """Extrai valor numérico"""
        if pd.isna(valor):
            return 0.0
        
        valor_str = str(valor).replace('.', '').replace(',', '.')
        try:
            match = re.search(r'[\d\.]+', valor_str)
            return float(match.group()) if match else 0.0
        except:
            return 0.0
    
    def processar_tudo(self):
        """Processa todos os arquivos com metodologia CATMAT"""
        if not self.carregar_dados():
            return False
        
        print("\n🔍 Processando com metodologia CATMAT...")
        print("📋 Critérios: Categoria ≥" + str(ConfigCATMAT.MIN_COMPATIBILIDADE_CATEGORIA) + "%, Características ≥" + str(ConfigCATMAT.MIN_COMPATIBILIDADE_CARACTERISTICAS) + "%")
        
        for arquivo in self.arquivos:
            print("\n📄 Processando: " + arquivo.name)
            
            try:
                df_edital = pd.read_excel(arquivo)
                matches_arquivo = 0
                
                for _, item in df_edital.iterrows():
                    self.estatisticas['total_analisados'] += 1
                    matches = self.processar_item(item, arquivo.name)
                    matches_arquivo += matches
                
                print("   ✅ " + str(matches_arquivo) + " matches CATMAT encontrados")
                
            except Exception as e:
                print("   ❌ Erro: " + str(e))
                continue
        
        self.imprimir_estatisticas()
        return True
    
    def processar_item(self, item, arquivo):
        """Processa item com metodologia CATMAT"""
        # Extrair dados
        num_item = item.get('Número do Item', 'N/A')
        desc_edital = str(item.get('Item', ''))
        unidade = item.get('Unidade de Fornecimento', 'UN')
        qtd = float(item.get('Quantidade Total', 0))
        valor_ref = self.extrair_valor(item.get('Valor Unitário (R$)', 0))
        
        if not desc_edital or valor_ref <= 0:
            return 0
        
        # Análise do edital
        analise_edital = self.analisador.analisar_edital(desc_edital)
        
        # Buscar matches com metodologia CATMAT
        matches_encontrados = []
        
        for _, produto in self.produtos_df.iterrows():
            # Análise CATMAT
            score, detalhes = self.processador.calcular_compatibilidade_catmat(desc_edital, produto)
            
            # Aplicar critérios CATMAT
            if score == 0.0:
                if 'motivo_rejeicao' in detalhes:
                    if 'Categoria' in detalhes['motivo_rejeicao']:
                        self.estatisticas['rejeitados_categoria'] += 1
                    elif 'Características' in detalhes['motivo_rejeicao']:
                        self.estatisticas['rejeitados_caracteristicas'] += 1
                continue
            
            if score < ConfigCATMAT.MIN_COMPATIBILIDADE:
                continue
            
            # Verificar preço com margem de preferência
            valor_produto = self.extrair_valor(produto.get('VALOR', produto.get('Valor', 0)))
            
            if valor_produto > 0:
                # Aplicar margem de preferência se aplicável
                margem_final = ConfigCATMAT.MARGEM_DISPUTA
                
                if analise_edital['margem_preferencia']:
                    # Verificar se produto é nacional
                    origem = str(produto.get('ORIGEM', produto.get('Origem', ''))).upper()
                    if 'NACIONAL' in origem or 'BRASIL' in origem:
                        margem_final += ConfigCATMAT.MARGEM_PREFERENCIA_NACIONAL
                        self.estatisticas['com_margem_preferencia'] += 1
                
                valor_disputa = valor_produto * (1 + margem_final)
                
                if valor_disputa <= valor_ref:
                    self.estatisticas['aprovados'] += 1
                    matches_encontrados.append({
                        'produto': produto,
                        'score': score,
                        'detalhes': detalhes,
                        'valor_produto': valor_produto,
                        'valor_disputa': valor_disputa,
                        'margem_aplicada': margem_final,
                        'tem_preferencia': analise_edital['margem_preferencia']
                    })
        
        # Ordenar por score CATMAT
        matches_encontrados.sort(key=lambda x: (-x['score'], x['valor_disputa']))
        
        for match in matches_encontrados[:ConfigCATMAT.MAX_SUGESTOES]:
            self.adicionar_resultado(num_item, desc_edital, unidade, qtd, valor_ref, match, analise_edital, arquivo)
        
        return len(matches_encontrados[:ConfigCATMAT.MAX_SUGESTOES])
    
    def adicionar_resultado(self, num_item, desc_edital, unidade, qtd, valor_ref, match, analise_edital, arquivo):
        """Adiciona resultado com análise CATMAT"""
        produto = match['produto']
        score = match['score']
        detalhes = match['detalhes']
        valor_produto = match['valor_produto']
        valor_disputa = match['valor_disputa']
        margem_aplicada = match['margem_aplicada']
        
        # Justificativa CATMAT
        justificativa = "ANÁLISE CATMAT: "
        justificativa += "Categoria: " + str(detalhes['categoria']) + "% | "
        justificativa += "Características: " + str(detalhes['caracteristicas']) + "% | "
        justificativa += "Semântico: " + str(detalhes['semantico']) + "%"
        
        if detalhes.get('categorias_edital'):
            justificativa += " | Cat: " + ', '.join(detalhes['categorias_edital'])
        
        # Características atendidas
        carac_atendidas = []
        if 'detalhes_caracteristicas' in detalhes:
            for carac, info in detalhes['detalhes_caracteristicas'].items():
                if info['status'] == 'COMPATIVEL':
                    carac_atendidas.append(carac)
        
        # Classificação CATMAT
        if score >= 95:
            classificacao_catmat = "EXCELENTE"
        elif score >= 90:
            classificacao_catmat = "OTIMO"
        elif score >= 85:
            classificacao_catmat = "BOM"
        else:
            classificacao_catmat = "ACEITAVEL"
        
        resultado = {
            'Arquivo': arquivo,
            'Item': num_item,
            'Descrição Edital': desc_edital,
            'Unidade': unidade,
            'Quantidade': qtd,
            'Valor Ref. Unitário': valor_ref,
            'Valor Ref. Total': valor_ref * qtd,
            'Marca sugerida': produto.get('MARCA', 'N/A'),
            'Produto Sugerido': produto.get('MODELO', 'N/A'),
            'Descrição Produto': str(produto.get('DESCRIÇÃO', produto.get('DESCRICAO', 'N/A')))[:150],
            'Preço Fornecedor': valor_produto,
            'Margem Aplicada (%)': round(margem_aplicada * 100, 1),
            'Preço com Margem': valor_disputa,
            'Economia Estimada': max(0, (valor_ref - valor_disputa) * qtd),
            'Score CATMAT': round(score, 2),
            'Score Categoria': detalhes['categoria'],
            'Score Características': detalhes['caracteristicas'],
            'Score Semântico': detalhes['semantico'],
            'Classificação CATMAT': classificacao_catmat,
            'Características Atendidas': ', '.join(carac_atendidas[:3]),
            'Justificativa CATMAT': justificativa,
            'Categorias Identificadas': ', '.join(detalhes.get('categorias_edital', [])),
            'Tem Margem Preferência?': 'Sim' if match['tem_preferencia'] else 'Não',
            'Risco Jurídico': analise_edital['direcionamento']['risco'],
            'Ação Recomendada': analise_edital['direcionamento']['acao_recomendada'],
            'Recomendação Geral': analise_edital['recomendacao_geral'],
            'Observação Jurídica': analise_edital['direcionamento']['observacao'],
            'Fornecedor': produto.get('FORNECEDOR', 'N/A')
        }
        
        self.resultados.append(resultado)
    
    def imprimir_estatisticas(self):
        """Imprime estatísticas CATMAT"""
        print("\n📊 ESTATÍSTICAS CATMAT:")
        print("=" * 50)
        print("Total analisados: " + str(self.estatisticas['total_analisados']))
        print("Rejeitados por categoria: " + str(self.estatisticas['rejeitados_categoria']))
        print("Rejeitados por características: " + str(self.estatisticas['rejeitados_caracteristicas']))
        print("Aprovados: " + str(self.estatisticas['aprovados']))
        print("Com margem de preferência: " + str(self.estatisticas['com_margem_preferencia']))
        
        if self.estatisticas['total_analisados'] > 0:
            taxa_aprovacao = (self.estatisticas['aprovados'] / self.estatisticas['total_analisados']) * 100
            print("Taxa de aprovação CATMAT: " + str(round(taxa_aprovacao, 1)) + "%")
    
    def gerar_relatorios(self):
        """Gera relatórios especializados para licitações"""
        if not self.resultados:
            print("❌ Nenhum resultado CATMAT encontrado")
            return False
        
        print("\n📊 Gerando relatórios CATMAT...")
        
        df_final = pd.DataFrame(self.resultados)
        
        # Estatísticas
        total_items = df_final['Item'].nunique()
        matches_excelentes = len(df_final[df_final['Score CATMAT'] >= 95])
        economia_total = df_final['Economia Estimada'].sum()
        itens_margem_preferencia = len(df_final[df_final['Tem Margem Preferência?'] == 'Sim'])
        
        # Pasta de saída
        if hasattr(self, 'arquivos') and self.arquivos:
            pasta_saida = self.arquivos[0].parent
        else:
            pasta_saida = Path(ConfigCATMAT.ORCAMENTOS_PATH)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        try:
            # Arquivos principais
            arquivo_csv = pasta_saida / "RESULTADO_MATCHING_INTELIGENTE.csv"
            arquivo_excel = pasta_saida / "RELATORIO_MATCHING_COMPLETO.xlsx"
            
            df_final.to_csv(arquivo_csv, index=False, encoding='utf-8-sig')
            df_final.to_excel(arquivo_excel, index=False)
            
            # Arquivo CATMAT específico
            arquivo_catmat = pasta_saida / ("MATCHING_CATMAT_" + timestamp + ".csv")
            df_final.to_csv(arquivo_catmat, index=False, encoding='utf-8-sig')
            
            # Relatório executivo CATMAT
            resumo = """# 📊 RELATÓRIO CATMAT - LICITAÇÕES GOVERNAMENTAIS

**Data**: """ + datetime.now().strftime('%d/%m/%Y %H:%M') + """
**Sistema**: Matching baseado no modelo CATMAT
**Metodologia**: Análise por categoria + características técnicas + semântica

## 📈 ESTATÍSTICAS CATMAT

- **Itens Analisados**: """ + str(total_items) + """
- **Matches CATMAT**: """ + str(len(df_final)) + """
- **Matches Excelentes (≥95%)**: """ + str(matches_excelentes) + """
- **Economia Total**: R$ """ + "{:,.2f}".format(economia_total) + """
- **Itens com Margem Preferência**: """ + str(itens_margem_preferencia) + """

## 🏆 TOP 10 MELHORES MATCHES CATMAT

""" + df_final.nlargest(10, 'Score CATMAT')[['Item', 'Produto Sugerido', 'Score CATMAT', 'Classificação CATMAT']].to_string(index=False) + """

## ⚖️ ANÁLISE JURÍDICA PARA LICITAÇÕES

- **Risco Crítico**: """ + str(len(df_final[df_final['Risco Jurídico'] == 'CRITICO'])) + """ itens
- **Risco Médio**: """ + str(len(df_final[df_final['Risco Jurídico'] == 'MEDIO'])) + """ itens
- **Risco Baixo/Nenhum**: """ + str(len(df_final[df_final['Risco Jurídico'].isin(['BAIXO', 'NENHUM'])])) + """ itens

## 🇧🇷 MARGEM DE PREFERÊNCIA NACIONAL

- **Produtos com Preferência**: """ + str(itens_margem_preferencia) + """
- **Margem Aplicada**: """ + str(ConfigCATMAT.MARGEM_PREFERENCIA_NACIONAL * 100) + """% adicional

## 🔬 METODOLOGIA CATMAT

1. **Análise de Categoria (40%)**: Compatibilidade com categorias CATMAT
2. **Análise de Características (35%)**: Especificações técnicas detalhadas
3. **Análise Semântica (25%)**: Compreensão contextual do produto

## 💡 RECOMENDAÇÕES PARA LICITAÇÕES

1. **Priorizar matches com Score CATMAT ≥ 90%**
2. **Verificar itens com risco jurídico crítico antes da participação**
3. **Aproveitar margem de preferência para produtos nacionais**
4. **Considerar características técnicas atendidas na proposta**

---
*Relatório gerado com metodologia CATMAT para máxima precisão em licitações*
"""
            
            arquivo_md = pasta_saida / ("RELATORIO_CATMAT_" + timestamp + ".md")
            with open(arquivo_md, 'w', encoding='utf-8') as f:
                f.write(resumo)
            
            print("✅ Relatórios CATMAT gerados!")
            print("📁 Pasta: " + str(pasta_saida))
            print("📄 CSV Principal: RESULTADO_MATCHING_INTELIGENTE.csv")
            print("📊 Excel Principal: RELATORIO_MATCHING_COMPLETO.xlsx")
            print("📄 CATMAT CSV: " + arquivo_catmat.name)
            print("📝 Relatório: " + arquivo_md.name)
            print("💰 Economia total: R$ " + "{:,.2f}".format(economia_total))
            print("🎯 Matches excelentes: " + str(matches_excelentes))
            print("🇧🇷 Com margem preferência: " + str(itens_margem_preferencia))
            
            return True
            
        except Exception as e:
            print("❌ Erro ao gerar relatórios: " + str(e))
            return False

def main():
    """Função principal"""
    print("🎯 SISTEMA DE MATCHING BASEADO NO MODELO CATMAT")
    print("=" * 70)
    print("🏛️ ESPECIALIZADO PARA LICITAÇÕES GOVERNAMENTAIS")
    print("📋 Baseado no Catálogo de Materiais do Governo Federal")
    print("⚖️ Análise jurídica específica para editais públicos")
    print("🇧🇷 Suporte à margem de preferência nacional")
    print("=" * 70)
    
    # Executar
    matcher = MatchingCATMAT()
    
    try:
        if matcher.processar_tudo():
            if matcher.gerar_relatorios():
                print("\n🎉 SUCESSO! Sistema CATMAT executado com êxito.")
                print("📁 Relatórios especializados para licitações gerados")
                print("🏛️ Pronto para participação em editais governamentais!")
            else:
                print("\n⚠️ Processamento OK, mas erro nos relatórios")
        else:
            print("\n❌ Erro no processamento")
    
    except Exception as e:
        print("\n💥 Erro: " + str(e))
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()