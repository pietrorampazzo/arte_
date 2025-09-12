"""
Configurações do Sistema de Matching para Licitações
===================================================

Baseado na análise do catmat.json e estrutura real dos editais.
Configurações centralizadas para todo o sistema modular.

Autor: Sistema Manus
Data: Janeiro 2025
Versão: 1.0 Produção
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass

# ============================================================================
# CONFIGURAÇÕES DE CAMINHOS
# ============================================================================

@dataclass
class CaminhosSistema:
    """Configuração centralizada de caminhos do sistema"""
    
    # Caminhos base do usuário
    BASE_ARTE: str = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE"
    CATALOGOS: str = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\CATALOGOS"
    EDITAIS_ORCAMENTOS: str = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\ORCAMENTOS"
    EDITAIS_DOWNLOADS: str = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\DOWNLOADS"
    
    # Caminhos de saída
    RESULTADOS: str = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\RESULTADOS"
    LOGS: str = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\LOGS"
    TEMP: str = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\TEMP"
    
    def __post_init__(self):
        """Cria diretórios se não existirem"""
        for caminho in [self.RESULTADOS, self.LOGS, self.TEMP]:
            Path(caminho).mkdir(parents=True, exist_ok=True)

# Instância global dos caminhos
CAMINHOS = CaminhosSistema()

# ============================================================================
# PADRÕES REGEX ESPECIALIZADOS PARA LICITAÇÕES
# ============================================================================

class PadroesRegex:
    """
    Padrões regex especializados baseados na análise do catmat.json
    e estrutura real dos editais brasileiros
    """
    
    # Padrões para identificação de itens em editais
    ITEM_EDITAL = {
        'numero_item': r'(?:item|ítem)\s*(?:n[ºo°]?)?\s*(\d+)',
        'item_completo': r'(\d+)\s*[-–]\s*([^0-9]+?)(?=\d+\s*[-–]|$)',
        'sequencial': r'(?:sequencial|seq)[:.]?\s*(\d+)',
    }
    
    # Padrões para extração de características técnicas
    CARACTERISTICAS = {
        'tipo': r'(?:tipo|categoria)[:.]?\s*([^,;|]+)',
        'modelo': r'(?:modelo|model)[:.]?\s*([^,;|]+)',
        'marca': r'(?:marca|fabricante|brand)[:.]?\s*([^,;|]+)',
        'material': r'(?:material|feito\s+de)[:.]?\s*([^,;|]+)',
        'acabamento': r'(?:acabamento|finish)[:.]?\s*([^,;|]+)',
        'cor': r'(?:cor|color)[:.]?\s*([^,;|]+)',
        'aplicacao': r'(?:aplicação|aplicacao|uso|application)[:.]?\s*([^,;|]+)',
        'acessorios': r'(?:acessórios|acessorios|accessories)[:.]?\s*([^,;|]+)',
        'componentes': r'(?:componentes|components)[:.]?\s*([^,;|]+)',
        'caracteristicas_adicionais': r'(?:características?\s+adicionais?|additional\s+features?)[:.]?\s*([^,;|]+)',
    }
    
    # Padrões para dimensões e medidas
    DIMENSOES = {
        'tamanho_geral': r'(?:tamanho|size|dimensão|dimensao)[:.]?\s*([^,;|]+)',
        'dimensoes_3d': r'(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*(?:[x×]\s*(\d+(?:\.\d+)?))?\s*(cm|mm|m|pol|polegadas?|\")',
        'diametro': r'(?:diâmetro|diametro|diameter)[:.]?\s*(\d+(?:\.\d+)?)\s*(cm|mm|m|pol|polegadas?|\")',
        'comprimento': r'(?:comprimento|length)[:.]?\s*(\d+(?:\.\d+)?)\s*(cm|mm|m|pol|polegadas?|\")',
        'largura': r'(?:largura|width)[:.]?\s*(\d+(?:\.\d+)?)\s*(cm|mm|m|pol|polegadas?|\")',
        'altura': r'(?:altura|height)[:.]?\s*(\d+(?:\.\d+)?)\s*(cm|mm|m|pol|polegadas?|\")',
        'profundidade': r'(?:profundidade|depth)[:.]?\s*(\d+(?:\.\d+)?)\s*(cm|mm|m|pol|polegadas?|\")',
    }
    
    # Padrões para especificações técnicas
    ESPECIFICACOES_TECNICAS = {
        'potencia': r'(?:potência|potencia|power)[:.]?\s*(\d+(?:\.\d+)?)\s*(w|watts?|kw)',
        'voltagem': r'(?:voltagem|tensão|tensao|voltage)[:.]?\s*(\d+(?:/\d+)?)\s*v',
        'frequencia': r'(?:frequência|frequencia|frequency)[:.]?\s*(\d+(?:\.\d+)?)\s*(?:hz|khz|mhz)',
        'impedancia': r'(?:impedância|impedancia|impedance)[:.]?\s*(\d+(?:\.\d+)?)\s*(?:ohms?|Ω)',
        'alcance': r'(?:alcance|range)[:.]?\s*(\d+(?:\.\d+)?)\s*(m|metros?|km)',
        'sensibilidade': r'(?:sensibilidade|sensitivity)[:.]?\s*([^,;|]+)',
        'resposta_frequencia': r'(?:resposta\s+frequência|response\s+frequency)[:.]?\s*([^,;|]+)',
        'teclas': r'(\d+)\s*teclas?',
        'canais': r'(?:quantidade\s+canais?|canais?)[:.]?\s*(\d+)',
        'polifonia': r'(?:polifonia|polyphony)[:.]?\s*(\d+)',
    }
    
    # Padrões para valores e quantidades
    VALORES = {
        'quantidade': r'(?:quantidade|qtd|quant)[:.]?\s*(\d+(?:\.\d+)?)',
        'valor_unitario': r'(?:valor|preço)\s*(?:unitário|unit)[:.]?\s*r?\$?\s*(\d+(?:\.\d+)?(?:,\d{2})?)',
        'valor_total': r'(?:valor|preço)\s*(?:total|ref)[:.]?\s*r?\$?\s*(\d+(?:\.\d+)?(?:,\d{2})?)',
        'intervalo_lance': r'(?:intervalo\s+mínimo|lance)[:.]?\s*r?\$?\s*(\d+(?:\.\d+)?(?:,\d{2})?)',
    }
    
    # Padrões para unidades de medida
    UNIDADES = {
        'unidade': r'\b(?:unidade|un|pç|peça|peças)\b',
        'jogo': r'\b(?:jogo|set|kit)\b',
        'par': r'\b(?:par|pair)\b',
        'metro': r'\b(?:metro|m|mt)\b',
        'caixa': r'\b(?:caixa|box|cx)\b',
        'pacote': r'\b(?:pacote|pack|pct)\b',
    }

# ============================================================================
# TAXONOMIA DE PRODUTOS BASEADA NO CATMAT
# ============================================================================

class TaxonomiaProdutos:
    """
    Taxonomia hierárquica de produtos baseada na análise do catmat.json
    Estrutura: Categoria Principal → Subcategoria → Tipos Específicos
    """
    
    # Categorias principais identificadas no catmat
    CATEGORIAS_PRINCIPAIS = {
        'instrumento_musical': {
            'termos': ['instrumento', 'musical', 'music'],
            'subcategorias': {
                'percussao': {
                    'termos': ['percussão', 'percussao', 'percussion', 'tambor', 'bateria', 'prato'],
                    'tipos': [
                        'tambor', 'bateria', 'pandeiro', 'surdo', 'caixa', 'prato', 
                        'triângulo', 'agogo', 'tamborim', 'zabumba', 'cajon', 
                        'quadriton', 'sinos', 'caixa de guerra', 'caixa half shell'
                    ]
                },
                'sopro': {
                    'termos': ['sopro', 'wind', 'flauta', 'saxofone', 'trompete'],
                    'tipos': [
                        'flauta', 'saxofone', 'clarinete', 'trompete', 'trombone', 
                        'tuba', 'bombardino', 'trompa', 'sousafone', 'cornet',
                        'saxhorn', 'clarone', 'flauta doce'
                    ]
                },
                'cordas': {
                    'termos': ['cordas', 'strings', 'piano', 'violão', 'guitarra'],
                    'tipos': [
                        'piano', 'violão', 'guitarra', 'baixo', 'viola', 'violino',
                        'contrabaixo', 'teclado'
                    ]
                }
            }
        },
        'equipamento_audio': {
            'termos': ['áudio', 'audio', 'som', 'sound'],
            'subcategorias': {
                'amplificacao': {
                    'termos': ['amplificador', 'amplifier', 'amp', 'potência'],
                    'tipos': ['amplificador', 'mesa de som', 'mixer', 'switcher']
                },
                'captacao': {
                    'termos': ['microfone', 'microphone', 'mic', 'captação'],
                    'tipos': [
                        'microfone', 'microfone sem fio', 'microfone de mão',
                        'microfone de lapela', 'microfone condensador', 'microfone dinâmico',
                        'microfone gooseneck', 'microfone de cabeça'
                    ]
                },
                'reproducao': {
                    'termos': ['caixa', 'som', 'speaker', 'alto-falante'],
                    'tipos': ['caixa de som', 'monitor', 'subwoofer', 'line array']
                }
            }
        },
        'acessorios': {
            'termos': ['acessórios', 'acessorios', 'accessories', 'peças'],
            'subcategorias': {
                'suportes': {
                    'termos': ['suporte', 'estante', 'stand', 'tripé'],
                    'tipos': [
                        'estante partitura', 'suporte microfone', 'tripé',
                        'suporte teclado', 'suporte guitarra'
                    ]
                },
                'cabos': {
                    'termos': ['cabo', 'cable', 'conector'],
                    'tipos': [
                        'cabo xlr', 'cabo p10', 'cabo rca', 'cabo usb',
                        'cabo rede', 'conector', 'adaptador'
                    ]
                },
                'pecas_reposicao': {
                    'termos': ['peças', 'pele', 'corda', 'palheta'],
                    'tipos': [
                        'encordoamento', 'pele bateria', 'palheta', 'boquilha',
                        'talabarte', 'kit pele', 'pele hidráulica'
                    ]
                }
            }
        }
    }
    
    # Materiais comuns identificados
    MATERIAIS = {
        'madeira': ['madeira', 'wood', 'grenadilha', 'jatobá'],
        'metal': ['metal', 'alumínio', 'aço', 'bronze', 'latão', 'cromado'],
        'plastico': ['plástico', 'resina', 'abs', 'pvc', 'polietileno'],
        'couro': ['couro', 'pele', 'leather', 'nylon'],
        'tecido': ['tecido', 'fabric', 'nylon', 'cordura'],
        'eletronico': ['eletrônico', 'digital', 'electronic']
    }
    
    # Acabamentos identificados
    ACABAMENTOS = {
        'laqueado': ['laqueado', 'lacquer', 'verniz'],
        'cromado': ['cromado', 'chrome', 'prateado'],
        'fosco': ['fosco', 'matte', 'mate'],
        'brilhante': ['brilhante', 'glossy', 'polido'],
        'natural': ['natural', 'cru', 'sem acabamento']
    }
    
    # Cores identificadas
    CORES = {
        'preto': ['preto', 'black', 'preta'],
        'branco': ['branco', 'white', 'branca'],
        'cinza': ['cinza', 'gray', 'grey'],
        'azul': ['azul', 'blue'],
        'vermelho': ['vermelho', 'red'],
        'amarelo': ['amarelo', 'yellow'],
        'verde': ['verde', 'green'],
        'marrom': ['marrom', 'brown'],
        'dourado': ['dourado', 'gold', 'ouro'],
        'prateado': ['prateado', 'silver', 'prata']
    }

# ============================================================================
# CONFIGURAÇÕES DE MATCHING
# ============================================================================

class ConfiguracaoMatching:
    """Configurações para o algoritmo de matching"""
    
    # Pesos para cálculo de similaridade
    PESOS_SIMILARIDADE = {
        'categoria_principal': 0.35,      # Peso maior para categoria
        'subcategoria': 0.25,            # Subcategoria importante
        'tipo_especifico': 0.20,         # Tipo específico
        'material': 0.10,                # Material compatível
        'dimensoes': 0.05,               # Dimensões similares
        'caracteristicas_tecnicas': 0.05  # Características técnicas
    }
    
    # Thresholds para matching
    THRESHOLDS = {
        'match_minimo': 0.4,             # Score mínimo para considerar match
        'match_bom': 0.6,                # Score para match bom
        'match_excelente': 0.8,          # Score para match excelente
        'similaridade_textual': 0.3,     # Threshold para similaridade textual
        'palavras_chave_minimas': 2       # Mínimo de palavras-chave para match
    }
    
    # Estratégias de busca (em ordem de prioridade)
    ESTRATEGIAS_BUSCA = [
        'categoria_subcategoria_exata',   # Match exato por categoria e subcategoria
        'tipo_especifico',               # Match por tipo específico
        'palavras_chave_multiplas',      # Match por múltiplas palavras-chave
        'similaridade_textual_alta',     # Match por alta similaridade textual
        'categoria_ampla'                # Match por categoria ampla
    ]
    
    # Associações proibidas (evitar matches inadequados)
    ASSOCIACOES_PROIBIDAS = {
        ('flauta', 'piano'),
        ('tambor', 'piano'),
        ('microfone', 'piano'),
        ('amplificador', 'flauta'),
        ('caixa som', 'flauta'),
        ('suporte', 'microfone'),  # Suporte não é microfone
        ('cabo', 'instrumento'),   # Cabo não é instrumento
    }

# ============================================================================
# CONFIGURAÇÕES DE ANÁLISE ECONÔMICA
# ============================================================================

class ConfiguracaoEconomica:
    """Configurações para análise econômica"""
    
    # Margens dinâmicas por faixa de valor
    MARGENS_DINAMICAS = {
        'baixo_valor': {'limite': 1000, 'margem': 0.60},      # Até R$ 1.000 - 60%
        'medio_valor': {'limite': 5000, 'margem': 0.55},      # R$ 1.001 a R$ 5.000 - 55%
        'alto_valor': {'limite': 20000, 'margem': 0.50},      # R$ 5.001 a R$ 20.000 - 50%
        'muito_alto_valor': {'limite': float('inf'), 'margem': 0.45}  # Acima R$ 20.000 - 45%
    }
    
    # Fatores de ajuste por categoria
    FATORES_CATEGORIA = {
        'instrumento_musical': 1.0,       # Sem ajuste
        'equipamento_audio': 0.95,        # 5% de desconto
        'acessorios': 1.1,               # 10% de acréscimo (menor volume)
    }
    
    # Configurações de vantajosidade
    VANTAJOSIDADE = {
        'economia_minima_percentual': 5,   # Mínimo 5% de economia
        'economia_minima_absoluta': 50,    # Mínimo R$ 50 de economia
        'limite_preco_maximo': 2.0,        # Máximo 2x o preço de referência
    }

# ============================================================================
# CONFIGURAÇÕES DE LOGGING E MONITORAMENTO
# ============================================================================

class ConfiguracaoLogging:
    """Configurações para logging e monitoramento"""
    
    # Níveis de log
    NIVEL_LOG = 'INFO'  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    
    # Formato de log
    FORMATO_LOG = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Arquivos de log
    ARQUIVOS_LOG = {
        'geral': 'sistema_matching.log',
        'extracoes': 'extracoes.log',
        'matching': 'matching.log',
        'erros': 'erros.log'
    }
    
    # Rotação de logs
    ROTACAO_LOG = {
        'max_bytes': 10 * 1024 * 1024,  # 10MB
        'backup_count': 5
    }

# ============================================================================
# CONFIGURAÇÕES DE PERFORMANCE
# ============================================================================

class ConfiguracaoPerformance:
    """Configurações para otimização de performance"""
    
    # Limites de processamento
    MAX_ARQUIVOS_SIMULTANEOS = 5        # Máximo de PDFs processados simultaneamente
    MAX_TAMANHO_ARQUIVO_MB = 50         # Máximo 50MB por arquivo
    TIMEOUT_PROCESSAMENTO = 300         # 5 minutos timeout por arquivo
    
    # Cache
    USAR_CACHE = True
    TAMANHO_CACHE_MB = 100
    TEMPO_CACHE_HORAS = 24
    
    # Paralelização
    USAR_MULTIPROCESSING = True
    NUM_PROCESSOS = 4  # Para i5 com 4 cores

# ============================================================================
# CONFIGURAÇÕES DE VALIDAÇÃO
# ============================================================================

class ConfiguracaoValidacao:
    """Configurações para validação de dados"""
    
    # Validações obrigatórias
    CAMPOS_OBRIGATORIOS_EDITAL = [
        'numero_item', 'descricao', 'quantidade', 'unidade'
    ]
    
    CAMPOS_OBRIGATORIOS_PRODUTO = [
        'codigo', 'descricao', 'marca', 'preco'
    ]
    
    # Limites de validação
    LIMITES = {
        'quantidade_minima': 1,
        'quantidade_maxima': 10000,
        'preco_minimo': 0.01,
        'preco_maximo': 1000000,
        'descricao_min_chars': 10,
        'descricao_max_chars': 1000
    }

# ============================================================================
# EXPORTAÇÃO DAS CONFIGURAÇÕES
# ============================================================================

# Instâncias globais das configurações
PADROES = PadroesRegex()
TAXONOMIA = TaxonomiaProdutos()
MATCHING = ConfiguracaoMatching()
ECONOMICA = ConfiguracaoEconomica()
LOGGING = ConfiguracaoLogging()
PERFORMANCE = ConfiguracaoPerformance()
VALIDACAO = ConfiguracaoValidacao()

# Função para validar configurações
def validar_configuracoes():
    """Valida se todas as configurações estão corretas"""
    erros = []
    
    # Validar caminhos
    if not Path(CAMINHOS.CATALOGOS).exists():
        erros.append(f"Pasta de catálogos não encontrada: {CAMINHOS.CATALOGOS}")
    
    if not Path(CAMINHOS.EDITAIS_ORCAMENTOS).exists():
        erros.append(f"Pasta de orçamentos não encontrada: {CAMINHOS.EDITAIS_ORCAMENTOS}")
    
    # Validar pesos de similaridade
    soma_pesos = sum(MATCHING.PESOS_SIMILARIDADE.values())
    if abs(soma_pesos - 1.0) > 0.01:
        erros.append(f"Soma dos pesos de similaridade deve ser 1.0, atual: {soma_pesos}")
    
    return erros

# Validação automática na importação
_erros_config = validar_configuracoes()
if _erros_config:
    print("⚠️  AVISOS DE CONFIGURAÇÃO:")
    for erro in _erros_config:
        print(f"   - {erro}")

if __name__ == "__main__":
    print("CONFIGURAÇÕES DO SISTEMA DE MATCHING")
    print("=" * 50)
    print(f"Catálogos: {CAMINHOS.CATALOGOS}")
    print(f"Orçamentos: {CAMINHOS.EDITAIS_ORCAMENTOS}")
    print(f"Resultados: {CAMINHOS.RESULTADOS}")
    print(f"Categorias principais: {len(TAXONOMIA.CATEGORIAS_PRINCIPAIS)}")
    print(f"Estratégias de busca: {len(MATCHING.ESTRATEGIAS_BUSCA)}")
    print("=" * 50)
