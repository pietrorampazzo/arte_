"""
METODOLOGIA AVANÇADA DE CÁLCULO DE COMPATIBILIDADE
Demonstração da nova abordagem para melhorar as taxas de matching
"""

import pandas as pd
import re
import json
from typing import Dict, List, Tuple, Optional
import numpy as np

class AdvancedCompatibilityCalculator:
    """
    Sistema avançado para cálculo de compatibilidade entre produtos
    baseado em especificações técnicas estruturadas
    """

    def __init__(self):
        # Especificações críticas por categoria
        self.CRITICAL_SPECS = {
            'microfone': {
                'required': ['tipo', 'padrao_polar', 'resposta_frequencia'],
                'weights': {'tipo': 0.4, 'padrao_polar': 0.3, 'resposta_frequencia': 0.3}
            },
            'amplificador': {
                'required': ['potencia', 'impedancia'],
                'weights': {'potencia': 0.6, 'impedancia': 0.4}
            },
            'instrumento_corda': {
                'required': ['tipo', 'numero_cordas'],
                'weights': {'tipo': 0.7, 'numero_cordas': 0.3}
            }
        }

        # Padrões regex para extração de especificações
        self.SPEC_PATTERNS = {
            'potencia': r'(\d+(?:\.\d+)?)\s*[wW]',  # 100W, 50.5W
            'frequencia': r'(\d+(?:-\d+)?)\s*[hH][zZ]',  # 20Hz-20kHz
            'impedancia': r'(\d+(?:\.\d+)?)\s*[oO]hms',  # 8 ohms
            'sensibilidade': r'(-?\d+(?:\.\d+)?)\s*[dD][bB]',  # -50dB
            'spl_max': r'(\d+(?:\.\d+)?)\s*[dD][bB]\s*(?:SPL|max)',  # 130dB SPL
            'tipo': r'(dinâmico|condensador|dinâmico|electret|fita)',
            'padrao_polar': r'(cardioide|omnidirecional|bidirecional|supercardioide)',
            'numero_cordas': r'(\d+)\s*cordas?',
        }

    def extract_specs(self, text: str) -> Dict[str, str]:
        """Extrai especificações técnicas de um texto usando regex"""
        specs = {}

        for spec_name, pattern in self.SPEC_PATTERNS.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                specs[spec_name] = match.group(1)

        return specs

    def normalize_spec_value(self, spec_name: str, value: str) -> float:
        """Normaliza valores de especificações para comparação"""
        if not value:
            return 0.0

        try:
            if spec_name == 'frequencia':
                # Converte "20Hz-20kHz" para média
                if '-' in value:
                    low, high = map(float, value.replace('Hz', '').replace('kHz', '000').split('-'))
                    return (low + high) / 2
                return float(value.replace('Hz', '').replace('kHz', '000'))

            elif spec_name in ['potencia', 'impedancia', 'spl_max']:
                return float(value.replace('W', '').replace('ohms', ''))

            elif spec_name == 'sensibilidade':
                return float(value.replace('dB', ''))

            elif spec_name == 'numero_cordas':
                return float(value)

            else:
                # Para especificações categóricas, retorna 1 se encontrado
                return 1.0 if value else 0.0

        except (ValueError, AttributeError):
            return 0.0

    def calculate_compatibility_score(self, edital_item: Dict, produto_base: Dict) -> Dict:
        """
        Calcula score de compatibilidade usando metodologia avançada
        """

        # 1. Extrair categoria e especificações
        categoria = edital_item.get('categoria_principal', '').lower()
        specs_edital = self.extract_specs(edital_item.get('DESCRICAO', ''))
        specs_produto = self.extract_specs(produto_base.get('DESCRICAO', ''))

        # 2. Calcular score base (subcategoria)
        base_score = 0.0
        subcategoria_edital = edital_item.get('subcategoria', '').lower()
        subcategoria_produto = produto_base.get('subcategoria', '').lower()

        if subcategoria_edital and subcategoria_produto:
            if subcategoria_edital == subcategoria_produto:
                base_score = 50.0  # Match exato de subcategoria
            elif subcategoria_edital in subcategoria_produto or subcategoria_produto in subcategoria_edital:
                base_score = 30.0  # Match parcial de subcategoria

        # 3. Calcular score técnico baseado na categoria
        technical_score = self._calculate_technical_score(categoria, specs_edital, specs_produto)

        # 4. Combinar scores (50% base + 50% técnico)
        final_score = base_score + technical_score

        # 5. Determinar nível de compatibilidade
        compatibility_level = self._determine_compatibility_level(final_score, categoria)

        return {
            'compatibility_score': min(final_score, 100.0),
            'base_score': base_score,
            'technical_score': technical_score,
            'compatibility_level': compatibility_level,
            'specs_found_edital': specs_edital,
            'specs_found_produto': specs_produto,
            'missing_specs': self._identify_missing_specs(categoria, specs_edital, specs_produto)
        }

    def _calculate_technical_score(self, categoria: str, specs_edital: Dict, specs_produto: Dict) -> float:
        """Calcula score técnico baseado nas especificações da categoria"""

        if categoria not in self.CRITICAL_SPECS:
            return 0.0

        critical_specs = self.CRITICAL_SPECS[categoria]
        total_weight = sum(critical_specs['weights'].values())
        score = 0.0

        for spec_name, weight in critical_specs['weights'].items():
            edital_value = specs_edital.get(spec_name)
            produto_value = specs_produto.get(spec_name)

            if not edital_value or not produto_value:
                continue  # Especificação não encontrada em um dos lados

            # Normalizar valores
            norm_edital = self.normalize_spec_value(spec_name, edital_value)
            norm_produto = self.normalize_spec_value(spec_name, produto_value)

            if norm_edital == 0 or norm_produto == 0:
                continue

            # Calcular similaridade
            if spec_name in ['tipo', 'padrao_polar']:  # Especificações categóricas
                similarity = 1.0 if norm_edital == norm_produto else 0.0
            else:  # Especificações numéricas
                # Calcular diferença percentual
                diff_percent = abs(norm_edital - norm_produto) / max(norm_edital, norm_produto)
                similarity = max(0, 1 - diff_percent)  # 0 a 1

            score += (similarity * weight / total_weight) * 50  # Máximo 50 pontos

        return score

    def _determine_compatibility_level(self, score: float, categoria: str) -> str:
        """Determina o nível de compatibilidade baseado no score"""

        # Thresholds ajustáveis por categoria
        thresholds = {
            'microfone': {'excelente': 85, 'bom': 70, 'aceitavel': 50},
            'amplificador': {'excelente': 80, 'bom': 65, 'aceitavel': 45},
            'default': {'excelente': 80, 'bom': 60, 'aceitavel': 40}
        }

        category_thresholds = thresholds.get(categoria, thresholds['default'])

        if score >= category_thresholds['excelente']:
            return 'MATCH_EXCELENTE'
        elif score >= category_thresholds['bom']:
            return 'MATCH_BOM'
        elif score >= category_thresholds['aceitavel']:
            return 'MATCH_ACEITAVEL'
        elif score >= 25:
            return 'MATCH_PARCIAL'
        else:
            return 'INCOMPATIVEL'

    def _identify_missing_specs(self, categoria: str, specs_edital: Dict, specs_produto: Dict) -> List[str]:
        """Identifica especificações que estão faltando no produto"""

        if categoria not in self.CRITICAL_SPECS:
            return []

        missing = []
        for spec in self.CRITICAL_SPECS[categoria]['required']:
            if spec not in specs_produto and spec in specs_edital:
                missing.append(spec)

        return missing

def demonstrar_metodologia():
    """Demonstra a nova metodologia com dados de exemplo"""

    print("=== DEMONSTRAÇÃO: METODOLOGIA AVANÇADA DE COMPATIBILIDADE ===\n")

    # Dados de exemplo
    edital_item = {
        'categoria_principal': 'EQUIPAMENTO_AUDIO',
        'subcategoria': 'microfone',
        'DESCRICAO': 'Microfone condensador cardioide com resposta de frequência 20Hz-20kHz, sensibilidade -35dB, impedância 200 ohms'
    }

    produtos_base = [
        {
            'categoria_principal': 'EQUIPAMENTO_AUDIO',
            'subcategoria': 'microfone',
            'DESCRICAO': 'Microfone condensador cardioide profissional, resposta 20Hz-20kHz, sensibilidade -35dB, impedância 200 ohms'
        },
        {
            'categoria_principal': 'EQUIPAMENTO_AUDIO',
            'subcategoria': 'microfone',
            'DESCRICAO': 'Microfone condensador cardioide, resposta 30Hz-18kHz, sensibilidade -40dB, impedância 250 ohms'
        },
        {
            'categoria_principal': 'EQUIPAMENTO_AUDIO',
            'subcategoria': 'microfone',
            'DESCRICAO': 'Microfone dinâmico cardioide, resposta 50Hz-15kHz, sensibilidade -55dB, impedância 600 ohms'
        }
    ]

    calculator = AdvancedCompatibilityCalculator()

    print("Item do Edital:")
    print(f"  Categoria: {edital_item['categoria_principal']}")
    print(f"  Subcategoria: {edital_item['subcategoria']}")
    print(f"  Descrição: {edital_item['DESCRICAO']}")
    print(f"  Specs extraídas: {calculator.extract_specs(edital_item['DESCRICAO'])}\n")

    print("Comparação com produtos da base:\n")

    for i, produto in enumerate(produtos_base, 1):
        resultado = calculator.calculate_compatibility_score(edital_item, produto)

        print(f"Produto {i}:")
        print(f"  Score: {resultado['compatibility_score']".1f"}/100")
        print(f"  Nível: {resultado['compatibility_level']}")
        print(f"  Specs encontradas: {resultado['specs_found_produto']}")
        if resultado['missing_specs']:
            print(f"  Specs faltando: {resultado['missing_specs']}")
        print()

if __name__ == "__main__":
    demonstrar_metodologia()
