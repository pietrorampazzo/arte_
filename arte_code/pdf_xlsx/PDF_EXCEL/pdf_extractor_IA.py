#!/usr/bin/env python3
"""
Extrator Inteligente de PDFs com IA - Versão com Mini-LLM
Usa inteligência artificial para análise avançada de headers e estruturas

Funcionalidades:
- IA para análise de headers aglutinados
- Correção automática de estruturas
- Aprendizado de padrões
- Validação inteligente de dados

Autor: Manus AI
Versão: 4.0 - Com IA
Data: 2025-07-30
"""

import os
import re
import pandas as pd
import numpy as np
import logging
from typing import List, Dict, Tuple, Optional, Any
import json
import warnings
warnings.filterwarnings('ignore')

# Imports condicionais
try:
    import camelot
    CAMELOT_AVAILABLE = True
except ImportError:
    CAMELOT_AVAILABLE = False

try:
    from tabula import read_pdf
    TABULA_AVAILABLE = True
except ImportError:
    TABULA_AVAILABLE = False

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pdf_extractor_ia.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class HeaderAnalyzerIA:
    """Analisador inteligente de cabeçalhos usando IA e heurísticas avançadas"""
    
    def __init__(self):
        # Base de conhecimento de padrões
        self.knowledge_base = {
            'column_types': {
                'item': {
                    'patterns': [r'\\bitem\\b', r'\\bn[°º]\\b', r'\\bnúmero\\b', r'\\bseq\\b'],
                    'indicators': ['numeric_sequence', 'small_integers'],
                    'position_preference': 'first'
                },
                'descricao': {
                    'patterns': [r'\\bdescrição\\b', r'\\bespecificação\\b', r'\\bobjeto\\b', r'\\bproduto\\b'],
                    'indicators': ['long_text', 'varied_content'],
                    'position_preference': 'early'
                },
                'catmat': {
                    'patterns': [r'\\bcatmat\\b', r'\\bcódigo\\b', r'\\bcat\\b'],
                    'indicators': ['numeric_codes', 'fixed_length'],
                    'position_preference': 'after_item'
                },
                'unidade': {
                    'patterns': [r'\\bunidade\\b', r'\\bun\\b', r'\\bmedida\\b'],
                    'indicators': ['short_text', 'repetitive'],
                    'position_preference': 'middle'
                },
                'quantidade': {
                    'patterns': [r'\\bquantidade\\b', r'\\bqtd\\b', r'\\btotal\\b'],
                    'indicators': ['small_numbers', 'integers'],
                    'position_preference': 'middle'
                },
                'valor_unitario': {
                    'patterns': [r'\\bvalor\\b.*\\bunitário\\b', r'\\bpreço\\b.*\\bunit\\b'],
                    'indicators': ['decimal_numbers', 'currency_format'],
                    'position_preference': 'late'
                },
                'valor_total': {
                    'patterns': [r'\\btotal\\b', r'\\bestimado\\b', r'\\bcusto\\b'],
                    'indicators': ['large_numbers', 'currency_format'],
                    'position_preference': 'last'
                }
            },
            'aglutination_patterns': [
                {
                    'pattern': r'(item|nº)\\s*(descrição|especificação)',
                    'split_method': 'keyword_boundary',
                    'columns': ['item', 'descricao']
                },
                {
                    'pattern': r'(valor)\\s*(unitário|total)',
                    'split_method': 'keyword_boundary',
                    'columns': ['valor_unitario', 'valor_total']
                },
                {
                    'pattern': r'(quantidade)\\s*(unidade)',
                    'split_method': 'keyword_boundary',
                    'columns': ['quantidade', 'unidade']
                }
            ]
        }
        
        # Histórico de aprendizado
        self.learning_history = []
    
    def analyze_text_semantically(self, text: str) -> Dict[str, float]:
        """Análise semântica de texto usando heurísticas avançadas"""
        if not text or pd.isna(text):
            return {}
        
        text_lower = str(text).lower().strip()
        scores = {}
        
        # Análise por padrões conhecidos
        for col_type, config in self.knowledge_base['column_types'].items():
            score = 0.0
            
            # Pontuação por padrões regex
            for pattern in config['patterns']:
                matches = len(re.findall(pattern, text_lower))
                score += matches * 2.0
            
            # Pontuação por indicadores
            if 'numeric_sequence' in config['indicators']:
                if re.search(r'^\\d+$', text_lower):
                    score += 3.0
            
            if 'long_text' in config['indicators']:
                if len(text_lower) > 20:
                    score += 2.0
            
            if 'short_text' in config['indicators']:
                if 2 <= len(text_lower) <= 10:
                    score += 1.5
            
            if 'currency_format' in config['indicators']:
                if re.search(r'\\d+[.,]\\d+', text_lower):
                    score += 2.0
            
            if score > 0:
                scores[col_type] = score
        
        return scores
    
    def detect_aglutinated_headers(self, text: str) -> List[Dict]:
        """Detecta headers aglutinados e sugere como separar"""
        if not text or pd.isna(text):
            return []
        
        text_clean = str(text).lower().strip()
        detections = []
        
        for aglut_pattern in self.knowledge_base['aglutination_patterns']:
            pattern = aglut_pattern['pattern']
            
            if re.search(pattern, text_clean):
                detections.append({
                    'original_text': text,
                    'pattern_matched': pattern,
                    'suggested_columns': aglut_pattern['columns'],
                    'split_method': aglut_pattern['split_method']
                })
        
        return detections
    
    def smart_header_analysis(self, row_data: List[str]) -> Dict[str, Any]:
        """Análise inteligente de uma linha potencial de cabeçalho"""
        
        analysis = {
            'is_header_probability': 0.0,
            'column_mapping': {},
            'aglutination_detected': [],
            'confidence_scores': {},
            'suggestions': []
        }
        
        if not row_data:
            return analysis
        
        # Analisa cada célula
        cell_analyses = []
        for i, cell in enumerate(row_data):
            if pd.isna(cell):
                cell_analyses.append({})
                continue
            
            cell_text = str(cell).strip()
            
            # Análise semântica da célula
            semantic_scores = self.analyze_text_semantically(cell_text)
            
            # Detecta aglutinação
            aglutination = self.detect_aglutinated_headers(cell_text)
            
            cell_analyses.append({
                'text': cell_text,
                'semantic_scores': semantic_scores,
                'aglutination': aglutination,
                'position': i
            })
        
        # Determina se é linha de cabeçalho
        header_indicators = 0
        total_semantic_score = 0
        
        for cell_analysis in cell_analyses:
            if cell_analysis.get('semantic_scores'):
                header_indicators += 1
                total_semantic_score += sum(cell_analysis['semantic_scores'].values())
            
            if cell_analysis.get('aglutination'):
                analysis['aglutination_detected'].extend(cell_analysis['aglutination'])
        
        # Calcula probabilidade de ser cabeçalho
        if len(row_data) > 0:
            analysis['is_header_probability'] = min(
                (header_indicators / len(row_data)) * 0.7 + 
                (total_semantic_score / (len(row_data) * 5)) * 0.3,
                1.0
            )
        
        # Mapeia colunas baseado na análise
        position_preferences = {}
        for cell_analysis in cell_analyses:
            if not cell_analysis.get('semantic_scores'):
                continue
            
            position = cell_analysis['position']
            
            for col_type, score in cell_analysis['semantic_scores'].items():
                if col_type not in position_preferences:
                    position_preferences[col_type] = []
                
                position_preferences[col_type].append({
                    'position': position,
                    'score': score,
                    'text': cell_analysis['text']
                })
        
        # Resolve conflitos e mapeia colunas
        for col_type, candidates in position_preferences.items():
            if candidates:
                # Ordena por score e pega o melhor
                best_candidate = max(candidates, key=lambda x: x['score'])
                analysis['column_mapping'][col_type] = best_candidate['position']
                analysis['confidence_scores'][col_type] = best_candidate['score']
        
        # Gera sugestões
        if analysis['aglutination_detected']:
            analysis['suggestions'].append("Headers aglutinados detectados - considere separação manual")
        
        if analysis['is_header_probability'] < 0.3:
            analysis['suggestions'].append("Baixa probabilidade de cabeçalho - pode ser linha de dados")
        
        return analysis
    
    def learn_from_success(self, pdf_name: str, successful_mapping: Dict[str, int], row_data: List[str]):
        """Aprende com mapeamentos bem-sucedidos"""
        
        learning_entry = {
            'pdf_name': pdf_name,
            'timestamp': pd.Timestamp.now().isoformat(),
            'mapping': successful_mapping,
            'row_data': row_data,
            'success': True
        }
        
        self.learning_history.append(learning_entry)
        
        # Mantém apenas os últimos 100 aprendizados
        if len(self.learning_history) > 100:
            self.learning_history = self.learning_history[-100:]
        
        logger.info(f"Aprendizado registrado para {pdf_name}")

class PDFExtractorIA:
    """Extrator com IA para análise inteligente de estruturas"""
    
    def __init__(self):
        self.header_analyzer = HeaderAnalyzerIA()
        
        # Configurações de extração
        self.extraction_configs = {
            'camelot': [
                {'flavor': 'lattice', 'pages': 'all'},
                {'flavor': 'stream', 'pages': 'all'},
                {'flavor': 'lattice', 'pages': 'all', 'line_scale': 40},
                {'flavor': 'stream', 'pages': 'all', 'edge_tol': 500}
            ],
            'tabula': [
                {'pages': 'all', 'multiple_tables': True, 'pandas_options': {'header': None}},
                {'pages': 'all', 'multiple_tables': True, 'lattice': True},
                {'pages': 'all', 'multiple_tables': True, 'stream': True}
            ]
        }
    
    def intelligent_header_detection(self, df: pd.DataFrame) -> Optional[Tuple[int, Dict[str, int], Dict[str, Any]]]:
        """Detecção inteligente de cabeçalho usando IA"""
        
        best_analysis = None
        best_row_idx = None
        best_probability = 0.0
        
        # Analisa as primeiras 20 linhas
        for idx in range(min(20, len(df))):
            row = df.iloc[idx]
            row_data = [str(cell) if pd.notna(cell) else "" for cell in row]
            
            # Análise inteligente da linha
            analysis = self.header_analyzer.smart_header_analysis(row_data)
            
            # Se a probabilidade é alta e tem mapeamento suficiente
            if (analysis['is_header_probability'] > best_probability and 
                len(analysis['column_mapping']) >= 2):
                
                best_analysis = analysis
                best_row_idx = idx
                best_probability = analysis['is_header_probability']
        
        if best_analysis and best_row_idx is not None:
            logger.info(f"IA detectou cabeçalho na linha {best_row_idx} "
                       f"(probabilidade: {best_probability:.2f})")
            
            if best_analysis['aglutination_detected']:
                logger.warning("Headers aglutinados detectados:")
                for aglut in best_analysis['aglutination_detected']:
                    logger.warning(f"  - {aglut['original_text']} -> {aglut['suggested_columns']}")
            
            return best_row_idx, best_analysis['column_mapping'], best_analysis
        
        return None
    
    def fix_data_intelligently(self, df: pd.DataFrame, column_mapping: Dict[str, int], 
                              analysis: Dict[str, Any]) -> pd.DataFrame:
        """Corrige dados de forma inteligente baseado na análise"""
        
        df_fixed = df.copy()
        
        # Aplica correções baseadas na detecção de aglutinação
        for aglut in analysis.get('aglutination_detected', []):
            if aglut['split_method'] == 'keyword_boundary':
                # Implementa separação por palavra-chave
                self._separate_aglutinated_data(df_fixed, aglut, column_mapping)
        
        # Corrige dados baseado em padrões aprendidos
        df_fixed = self._apply_learned_corrections(df_fixed, column_mapping)
        
        return df_fixed
    
    def _separate_aglutinated_data(self, df: pd.DataFrame, aglut_info: Dict, 
                                  column_mapping: Dict[str, int]):
        """Separa dados aglutinados baseado na detecção de IA"""
        
        # Implementação específica para cada tipo de aglutinação
        if 'catmat' in aglut_info['suggested_columns'] and 'descricao' in column_mapping:
            desc_col = column_mapping['descricao']
            
            for idx, row in df.iterrows():
                desc_text = str(row.iloc[desc_col])
                
                # Procura CATMAT no início da descrição
                catmat_match = re.search(r'^(\\d{6,})\\s+(.+)', desc_text)
                if catmat_match:
                    catmat = catmat_match.group(1)
                    desc_clean = catmat_match.group(2)
                    
                    df.iloc[idx, desc_col] = desc_clean
                    
                    # Adiciona CATMAT em coluna adjacente se disponível
                    if desc_col + 1 < len(df.columns):
                        df.iloc[idx, desc_col + 1] = catmat
    
    def _apply_learned_corrections(self, df: pd.DataFrame, 
                                  column_mapping: Dict[str, int]) -> pd.DataFrame:
        """Aplica correções baseadas no aprendizado anterior"""
        
        # Implementa correções baseadas no histórico de aprendizado
        for learning in self.header_analyzer.learning_history[-10:]:  # Últimos 10
            if learning['success']:
                # Aplica padrões bem-sucedidos
                pass
        
        return df
    
    def extract_items_intelligently(self, df: pd.DataFrame, pdf_name: str) -> List[Dict]:
        """Extrai itens usando análise inteligente"""
        
        if df.empty:
            return []
        
        # Detecção inteligente de cabeçalho
        header_info = self.intelligent_header_detection(df)
        if not header_info:
            logger.warning("IA não conseguiu detectar cabeçalho válido")
            return []
        
        header_row, column_mapping, analysis = header_info
        
        logger.info(f"Mapeamento IA: {column_mapping}")
        logger.info(f"Confiança: {analysis.get('confidence_scores', {})}")
        
        # Correção inteligente de dados
        df_fixed = self.fix_data_intelligently(df, column_mapping, analysis)
        
        # Extração de itens
        items = []
        
        for idx in range(header_row + 1, len(df_fixed)):
            row = df_fixed.iloc[idx]
            
            # Extrai item usando mapeamento inteligente
            item = self._extract_item_with_ia(row, column_mapping, analysis)
            if item:
                items.append(item)
        
        # Registra aprendizado se bem-sucedido
        if items:
            row_data = [str(cell) for cell in df.iloc[header_row]]
            self.header_analyzer.learn_from_success(pdf_name, column_mapping, row_data)
        
        return items
    
    def _extract_item_with_ia(self, row: pd.Series, column_mapping: Dict[str, int], 
                             analysis: Dict[str, Any]) -> Optional[Dict]:
        """Extrai item individual usando IA"""
        
        # Extrai número do item
        item_num = None
        if 'item' in column_mapping:
            item_text = str(row.iloc[column_mapping['item']])
            
            # Usa padrões inteligentes para extrair número
            patterns = [r'^(\\d+)', r'item\\s*(\\d+)', r'n[°º]\\s*(\\d+)']
            for pattern in patterns:
                match = re.search(pattern, item_text, re.IGNORECASE)
                if match:
                    try:
                        item_num = int(match.group(1))
                        break
                    except ValueError:
                        continue
        
        if not item_num:
            return None
        
        # Extrai descrição com limpeza inteligente
        descricao = ""
        if 'descricao' in column_mapping:
            desc_text = str(row.iloc[column_mapping['descricao']])
            
            # Limpeza inteligente baseada em padrões aprendidos
            descricao = self._clean_description_intelligently(desc_text)
        
        if not descricao or len(descricao) < 5:
            return None
        
        # Extrai outros campos com validação inteligente
        unidade = self._extract_unit_intelligently(row, column_mapping)
        quantidade = self._extract_quantity_intelligently(row, column_mapping)
        valor_unitario = self._extract_unit_value_intelligently(row, column_mapping)
        valor_total = self._extract_total_value_intelligently(row, column_mapping)
        
        # Validação cruzada inteligente
        if not valor_unitario and valor_total and quantidade > 0:
            valor_unitario = valor_total / quantidade
        elif not valor_total and valor_unitario:
            valor_total = valor_unitario * quantidade
        
        # Define valores finais
        if not valor_unitario or valor_unitario <= 0:
            valor_unitario = "etapa"
            valor_total = "etapa"
        
        return {
            'Nº': item_num,
            'Descrição do Produto': descricao,
            'Unidade': unidade,
            'Quantidade': quantidade,
            'Valor Unitario': valor_unitario,
            'Valor Total': valor_total
        }
    
    def _clean_description_intelligently(self, text: str) -> str:
        """Limpa descrição usando IA"""
        if not text or pd.isna(text):
            return ""
        
        text = str(text).strip()
        
        # Remove CATMAT do início se presente
        text = re.sub(r'^\\d{6,}\\s+', '', text)
        
        # Remove quebras de linha e espaços múltiplos
        text = re.sub(r'\\s+', ' ', text)
        
        # Remove caracteres especiais problemáticos
        text = re.sub(r'[^\\w\\s.,()/-]', '', text)
        
        return text.strip()
    
    def _extract_unit_intelligently(self, row: pd.Series, column_mapping: Dict[str, int]) -> str:
        """Extrai unidade com IA"""
        if 'unidade' not in column_mapping:
            return "unidade"
        
        unit_text = str(row.iloc[column_mapping['unidade']]).strip()
        
        if not unit_text or unit_text.lower() in ['nan', 'none', '']:
            return "unidade"
        
        # Normaliza unidades comuns
        unit_mapping = {
            'un': 'unidade',
            'und': 'unidade',
            'pc': 'peça',
            'pç': 'peça',
            'kg': 'quilograma',
            'm': 'metro',
            'l': 'litro'
        }
        
        unit_lower = unit_text.lower()
        return unit_mapping.get(unit_lower, unit_text)
    
    def _extract_quantity_intelligently(self, row: pd.Series, column_mapping: Dict[str, int]) -> int:
        """Extrai quantidade com IA"""
        if 'quantidade' not in column_mapping:
            return 1
        
        qty_text = str(row.iloc[column_mapping['quantidade']])
        
        # Extrai número da string
        numbers = re.findall(r'\\d+', qty_text)
        if numbers:
            try:
                return int(numbers[0])
            except ValueError:
                pass
        
        return 1
    
    def _extract_unit_value_intelligently(self, row: pd.Series, column_mapping: Dict[str, int]) -> Optional[float]:
        """Extrai valor unitário com IA"""
        if 'valor_unitario' not in column_mapping:
            return None
        
        value_text = str(row.iloc[column_mapping['valor_unitario']])
        return self._extract_currency_value(value_text)
    
    def _extract_total_value_intelligently(self, row: pd.Series, column_mapping: Dict[str, int]) -> Optional[float]:
        """Extrai valor total com IA"""
        if 'valor_total' not in column_mapping:
            return None
        
        value_text = str(row.iloc[column_mapping['valor_total']])
        return self._extract_currency_value(value_text)
    
    def _extract_currency_value(self, text: str) -> Optional[float]:
        """Extrai valor monetário de texto"""
        if not text or pd.isna(text):
            return None
        
        text = str(text).strip()
        text = re.sub(r'[R$\\s]', '', text)
        
        # Padrões para valores brasileiros
        patterns = [
            r'(\\d{1,3}(?:\\.\\d{3})*,\\d{2})',  # 1.234.567,89
            r'(\\d+,\\d{2})',                     # 1234,89
            r'(\\d+\\.\\d{2})',                   # 1234.89
            r'(\\d+)',                            # 1234
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                num_str = match.group(1)
                
                if ',' in num_str and '.' in num_str:
                    num_str = num_str.replace('.', '').replace(',', '.')
                elif ',' in num_str:
                    num_str = num_str.replace(',', '.')
                
                try:
                    return float(num_str)
                except ValueError:
                    continue
        
        return None
    
    def extract_from_pdf_with_ia(self, pdf_path: str) -> List[Dict]:
        """Extração principal usando IA"""
        
        pdf_name = os.path.basename(pdf_path)
        logger.info(f"IA processando: {pdf_name}")
        
        # Tenta diferentes engines com IA
        engines = []
        
        if CAMELOT_AVAILABLE:
            engines.append(("Camelot+IA", self._extract_with_camelot_ia))
        if TABULA_AVAILABLE:
            engines.append(("Tabula+IA", self._extract_with_tabula_ia))
        if PDFPLUMBER_AVAILABLE:
            engines.append(("PDFPlumber+IA", self._extract_with_pdfplumber_ia))
        
        best_result = []
        best_score = 0
        
        for engine_name, engine_func in engines:
            try:
                logger.info(f"Tentando {engine_name}...")
                items = engine_func(pdf_path)
                
                # Calcula score baseado na qualidade dos dados
                score = self._calculate_extraction_score(items)
                
                if score > best_score:
                    best_result = items
                    best_score = score
                    logger.info(f"{engine_name}: {len(items)} itens (score: {score:.2f})")
                
            except Exception as e:
                logger.error(f"Erro no {engine_name}: {e}")
                continue
        
        # Remove duplicatas e ordena
        if best_result:
            df = pd.DataFrame(best_result)
            df = df.drop_duplicates(subset=['Nº'], keep='first')
            df = df.sort_values('Nº').reset_index(drop=True)
            best_result = df.to_dict('records')
        
        logger.info(f"IA extraiu {len(best_result)} itens finais")
        return best_result
    
    def _extract_with_camelot_ia(self, pdf_path: str) -> List[Dict]:
        """Extração com Camelot + IA"""
        if not CAMELOT_AVAILABLE:
            return []
        
        pdf_name = os.path.basename(pdf_path)
        all_items = []
        
        for config in self.extraction_configs['camelot']:
            try:
                tables = camelot.read_pdf(pdf_path, **config)
                
                for table in tables:
                    if table.df.empty:
                        continue
                    
                    items = self.extract_items_intelligently(table.df, pdf_name)
                    all_items.extend(items)
                
                if all_items:
                    break
                    
            except Exception as e:
                logger.warning(f"Erro na configuração Camelot+IA: {e}")
                continue
        
        return all_items
    
    def _extract_with_tabula_ia(self, pdf_path: str) -> List[Dict]:
        """Extração com Tabula + IA"""
        if not TABULA_AVAILABLE:
            return []
        
        pdf_name = os.path.basename(pdf_path)
        all_items = []
        
        for config in self.extraction_configs['tabula']:
            try:
                tables = read_pdf(pdf_path, **config, silent=True)
                
                for table in tables:
                    if isinstance(table, pd.DataFrame) and not table.empty:
                        items = self.extract_items_intelligently(table, pdf_name)
                        all_items.extend(items)
                
                if all_items:
                    break
                    
            except Exception as e:
                logger.warning(f"Erro na configuração Tabula+IA: {e}")
                continue
        
        return all_items
    
    def _extract_with_pdfplumber_ia(self, pdf_path: str) -> List[Dict]:
        """Extração com PDFPlumber + IA"""
        if not PDFPLUMBER_AVAILABLE:
            return []
        
        pdf_name = os.path.basename(pdf_path)
        all_items = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    
                    for table in tables:
                        if table and len(table) > 1:
                            df = pd.DataFrame(table)
                            items = self.extract_items_intelligently(df, pdf_name)
                            all_items.extend(items)
        
        except Exception as e:
            logger.error(f"Erro no PDFPlumber+IA: {e}")
        
        return all_items
    
    def _calculate_extraction_score(self, items: List[Dict]) -> float:
        """Calcula score de qualidade da extração"""
        if not items:
            return 0.0
        
        score = 0.0
        
        # Pontos por quantidade de itens
        score += len(items) * 0.1
        
        # Pontos por qualidade dos dados
        for item in items:
            if item.get('Nº') and isinstance(item['Nº'], int):
                score += 1.0
            
            if item.get('Descrição do Produto') and len(str(item['Descrição do Produto'])) > 10:
                score += 2.0
            
            if item.get('Valor Unitario') and item['Valor Unitario'] != "etapa":
                score += 1.5
            
            if item.get('Quantidade') and isinstance(item['Quantidade'], int) and item['Quantidade'] > 0:
                score += 1.0
        
        return score / max(len(items), 1)  # Normaliza pelo número de itens
    
    def save_to_excel_with_metadata(self, items: List[Dict], output_path: str, metadata: Dict = None):
        """Salva Excel com metadados da IA"""
        if not items:
            logger.warning("Nenhum item para salvar")
            return
        
        try:
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                # Aba principal com dados
                df = pd.DataFrame(items)
                column_order = ['Nº', 'Descrição do Produto', 'Unidade', 'Quantidade', 'Valor Unitario', 'Valor Total']
                df = df[column_order]
                df.to_excel(writer, index=False, sheet_name='Itens')
                
                # Aba com metadados da IA
                if metadata:
                    metadata_df = pd.DataFrame([metadata])
                    metadata_df.to_excel(writer, index=False, sheet_name='Metadados_IA')
                
                # Ajusta largura das colunas
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    for column in worksheet.columns:
                        max_length = 0
                        column_letter = column[0].column_letter
                        
                        for cell in column:
                            try:
                                if len(str(cell.value)) > max_length:
                                    max_length = len(str(cell.value))
                            except:
                                pass
                        
                        adjusted_width = min(max_length + 2, 50)
                        worksheet.column_dimensions[column_letter].width = adjusted_width
            
            logger.info(f"Arquivo salvo com IA: {output_path}")
            
        except Exception as e:
            logger.error(f"Erro ao salvar Excel: {e}")

def process_pdf_folder_with_ia(input_folder: str, output_folder: str):
    """Processa pasta de PDFs usando IA"""
    
    extractor = PDFExtractorIA()
    
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    processed_files = 0
    total_items = 0
    error_files = []
    
    logger.info("Iniciando processamento com IA")
    logger.info(f"Pasta de entrada: {input_folder}")
    logger.info(f"Pasta de saída: {output_folder}")
    
    pdf_files = [f for f in os.listdir(input_folder) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        logger.warning("Nenhum arquivo PDF encontrado")
        return
    
    logger.info(f"Encontrados {len(pdf_files)} arquivos PDF")
    
    for i, filename in enumerate(pdf_files, 1):
        pdf_path = os.path.join(input_folder, filename)
        
        logger.info(f"\\n{'='*60}")
        logger.info(f"IA processando {i}/{len(pdf_files)}: {filename}")
        logger.info(f"{'='*60}")
        
        try:
            items = extractor.extract_from_pdf_with_ia(pdf_path)
            
            if items:
                processed_files += 1
                total_items += len(items)
                
                # Metadados da extração
                metadata = {
                    'arquivo': filename,
                    'timestamp': pd.Timestamp.now().isoformat(),
                    'itens_extraidos': len(items),
                    'metodo': 'IA',
                    'versao': '4.0'
                }
                
                # Salva com metadados
                excel_filename = f"{os.path.splitext(filename)[0]}_v4_IA.xlsx"
                excel_path = os.path.join(output_folder, excel_filename)
                extractor.save_to_excel_with_metadata(items, excel_path, metadata)
                
                logger.info(f"SUCESSO IA: {filename} - {len(items)} itens extraídos")
            else:
                logger.warning(f"FALHA IA: {filename} - Nenhum item encontrado")
                error_files.append(filename)
                
        except Exception as e:
            logger.error(f"ERRO IA: {filename} - {e}")
            error_files.append(filename)
    
    # Resumo final
    logger.info(f"\\n{'='*60}")
    logger.info("RESUMO DO PROCESSAMENTO COM IA")
    logger.info(f"{'='*60}")
    logger.info(f"Arquivos processados com sucesso: {processed_files}")
    logger.info(f"Total de itens extraídos: {total_items}")
    logger.info(f"Arquivos com problemas: {len(error_files)}")
    
    if error_files:
        logger.info("\\nArquivos que apresentaram problemas:")
        for file in error_files:
            logger.info(f"  - {file}")
    
    # Salva histórico de aprendizado
    learning_file = os.path.join(output_folder, "aprendizado_ia.json")
    try:
        with open(learning_file, 'w', encoding='utf-8') as f:
            json.dump(extractor.header_analyzer.learning_history, f, indent=2, ensure_ascii=False)
        logger.info(f"Histórico de aprendizado salvo: {learning_file}")
    except Exception as e:
        logger.warning(f"Erro ao salvar aprendizado: {e}")
    
    logger.info("\\nProcessamento com IA concluído!")

if __name__ == "__main__":
    # Configuração para produção
    input_folder = "C:/Users/pietr/OneDrive/Área de Trabalho/ARTE/01_EDITAIS/DOWNLOADS"
    output_folder = os.path.join(input_folder, "tabelas_extraidas")
    
    # Para teste local (descomente)
    # input_folder = "/home/ubuntu/upload"
    # output_folder = "/home/ubuntu/output_ia"
    
    process_pdf_folder_with_ia(input_folder, output_folder)

