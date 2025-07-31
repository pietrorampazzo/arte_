#!/usr/bin/env python3
"""
Extrator Robusto de PDFs de Editais - Versão Corrigida
Resolve problemas específicos identificados nos testes:
- Headers aglutinados ou ausentes
- Dados truncados/aglutinados entre colunas
- Problemas de encoding no Windows
- Múltiplos engines de extração

Autor: Manus AI
Versão: 2.1 - Robusta
Data: 2025-07-30
"""

import os
import re
import pandas as pd
import numpy as np
import logging
from typing import List, Dict, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

# Imports condicionais
try:
    import camelot
    CAMELOT_AVAILABLE = True
except ImportError:
    CAMELOT_AVAILABLE = False
    print("Camelot não disponível. Instale com: pip install camelot-py[cv]")

try:
    from tabula import read_pdf
    TABULA_AVAILABLE = True
except ImportError:
    TABULA_AVAILABLE = False
    print("Tabula não disponível. Instale com: pip install tabula-py")

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    print("PDFPlumber não disponível. Instale com: pip install pdfplumber")

# Configurar logging sem emojis (compatibilidade Windows)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pdf_extractor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PDFExtractorRobusto:
    """Extrator robusto que resolve problemas específicos identificados"""
    
    def __init__(self):
        # Padrões mais específicos baseados nos testes
        self.column_patterns = {
            'item': [
                r'^\s*(\d+)\s*$',  # Apenas números
                r'item\s*(\d+)',
                r'n[°º]\s*(\d+)',
                r'seq\s*(\d+)'
            ],
            'descricao_keywords': [
                'descrição', 'descriçao', 'especificação', 'especificacao',
                'objeto', 'produto', 'material', 'servico', 'serviço',
                'denominação', 'denominacao', 'detalhamento'
            ],
            'unidade_keywords': [
                'unidade', 'un', 'und', 'medida', 'fornecimento',
                'unid', 'unity', 'unit'
            ],
            'quantidade_keywords': [
                'quantidade', 'qtd', 'qtde', 'quant', 'total', 'estimada',
                'qty', 'qnt', 'volume'
            ],
            'valor_keywords': [
                'valor', 'preço', 'preco', 'unitário', 'unitario',
                'total', 'estimado', 'custo', 'price'
            ]
        }
        
        # Padrões para limpeza de dados
        self.cleanup_patterns = [
            (r'\\n+', ' '),  # Quebras de linha
            (r'\\s+', ' '),  # Espaços múltiplos
            (r'^\\s+|\\s+$', ''),  # Espaços no início/fim
            (r'[^\\w\\s.,()/-]', ''),  # Caracteres especiais
        ]
    
    def clean_text(self, text: str) -> str:
        """Limpa texto de forma mais agressiva"""
        if pd.isna(text) or text is None:
            return ""
        
        text = str(text)
        
        # Aplica padrões de limpeza
        for pattern, replacement in self.cleanup_patterns:
            text = re.sub(pattern, replacement, text)
        
        return text.strip()
    
    def extract_number(self, text: str) -> Optional[float]:
        """Extrai números considerando formatos brasileiros e problemas de parsing"""
        if pd.isna(text) or text is None:
            return None
        
        text = str(text).strip()
        
        # Remove símbolos comuns
        text = re.sub(r'[R$\\s]', '', text)
        
        # Padrões mais robustos
        patterns = [
            r'(\\d{1,3}(?:\\.\\d{3})*,\\d{2})',  # 1.234.567,89
            r'(\\d+,\\d{2})',                     # 1234,89
            r'(\\d+\\.\\d{2})',                   # 1234.89
            r'(\\d+)',                            # 1234
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                num_str = matches[0]  # Pega o primeiro match
                
                # Converte formato brasileiro
                if ',' in num_str and '.' in num_str:
                    num_str = num_str.replace('.', '').replace(',', '.')
                elif ',' in num_str:
                    num_str = num_str.replace(',', '.')
                
                try:
                    return float(num_str)
                except ValueError:
                    continue
        
        return None
    
    def detect_header_row(self, df: pd.DataFrame) -> Optional[Tuple[int, Dict[str, int]]]:
        """Detecta linha de cabeçalho de forma mais robusta"""
        
        for idx in range(min(20, len(df))):  # Procura nas primeiras 20 linhas
            row = df.iloc[idx]
            
            # Converte linha para texto único para análise
            row_text = ' '.join([str(cell).lower() for cell in row if pd.notna(cell)])
            
            # Conta quantas palavras-chave de diferentes categorias encontrou
            categories_found = 0
            column_mapping = {}
            
            # Analisa cada célula da linha
            for col_idx, cell in enumerate(row):
                if pd.isna(cell):
                    continue
                
                cell_text = str(cell).lower().strip()
                
                # Verifica se é coluna de item
                if any(keyword in cell_text for keyword in ['item', 'nº', 'n°', 'numero', 'número', 'seq']):
                    if 'item' not in column_mapping:
                        column_mapping['item'] = col_idx
                        categories_found += 1
                
                # Verifica se é coluna de descrição
                elif any(keyword in cell_text for keyword in self.column_patterns['descricao_keywords']):
                    if 'descricao' not in column_mapping:
                        column_mapping['descricao'] = col_idx
                        categories_found += 1
                
                # Verifica se é coluna de unidade
                elif any(keyword in cell_text for keyword in self.column_patterns['unidade_keywords']):
                    if 'unidade' not in column_mapping:
                        column_mapping['unidade'] = col_idx
                        categories_found += 1
                
                # Verifica se é coluna de quantidade
                elif any(keyword in cell_text for keyword in self.column_patterns['quantidade_keywords']):
                    if 'quantidade' not in column_mapping:
                        column_mapping['quantidade'] = col_idx
                        categories_found += 1
                
                # Verifica se é coluna de valor
                elif any(keyword in cell_text for keyword in self.column_patterns['valor_keywords']):
                    if 'valor_unitario' not in column_mapping and 'unitário' in cell_text:
                        column_mapping['valor_unitario'] = col_idx
                        categories_found += 1
                    elif 'valor_total' not in column_mapping and 'total' in cell_text:
                        column_mapping['valor_total'] = col_idx
                        categories_found += 1
            
            # Se encontrou pelo menos 3 categorias, considera como cabeçalho
            if categories_found >= 3:
                logger.info(f"Cabeçalho detectado na linha {idx} com {categories_found} categorias")
                return idx, column_mapping
        
        # Se não encontrou cabeçalho explícito, tenta inferir pela estrutura
        return self.infer_header_from_structure(df)
    
    def infer_header_from_structure(self, df: pd.DataFrame) -> Optional[Tuple[int, Dict[str, int]]]:
        """Infere cabeçalho baseado na estrutura dos dados quando headers estão ausentes"""
        
        if len(df.columns) < 3:
            return None
        
        # Mapeia colunas baseado em padrões típicos
        column_mapping = {}
        
        # Primeira coluna geralmente é item (números)
        first_col = df.iloc[:, 0]
        numeric_count = sum(1 for val in first_col if pd.notna(val) and str(val).strip().isdigit())
        
        if numeric_count > len(first_col) * 0.5:  # Mais de 50% são números
            column_mapping['item'] = 0
            logger.info("Coluna 0 inferida como ITEM (muitos números)")
        
        # Segunda coluna geralmente é descrição (textos longos)
        if len(df.columns) > 1:
            second_col = df.iloc[:, 1]
            long_text_count = sum(1 for val in second_col if pd.notna(val) and len(str(val).strip()) > 20)
            
            if long_text_count > len(second_col) * 0.3:  # Mais de 30% são textos longos
                column_mapping['descricao'] = 1
                logger.info("Coluna 1 inferida como DESCRIÇÃO (textos longos)")
        
        # Últimas colunas geralmente são valores (números com vírgulas/pontos)
        for col_idx in range(len(df.columns) - 1, max(1, len(df.columns) - 4), -1):
            col_data = df.iloc[:, col_idx]
            value_count = sum(1 for val in col_data if pd.notna(val) and self.extract_number(str(val)) is not None)
            
            if value_count > len(col_data) * 0.3:  # Mais de 30% são valores
                if 'valor_total' not in column_mapping:
                    column_mapping['valor_total'] = col_idx
                    logger.info(f"Coluna {col_idx} inferida como VALOR TOTAL")
                elif 'valor_unitario' not in column_mapping:
                    column_mapping['valor_unitario'] = col_idx
                    logger.info(f"Coluna {col_idx} inferida como VALOR UNITÁRIO")
        
        # Coluna do meio pode ser quantidade ou unidade
        if len(df.columns) > 3:
            middle_cols = range(2, len(df.columns) - 2)
            for col_idx in middle_cols:
                if col_idx in [column_mapping.get('valor_unitario'), column_mapping.get('valor_total')]:
                    continue
                
                col_data = df.iloc[:, col_idx]
                
                # Verifica se parece quantidade (números pequenos)
                small_numbers = sum(1 for val in col_data if pd.notna(val) and 
                                  self.extract_number(str(val)) is not None and 
                                  self.extract_number(str(val)) < 1000)
                
                if small_numbers > len(col_data) * 0.3 and 'quantidade' not in column_mapping:
                    column_mapping['quantidade'] = col_idx
                    logger.info(f"Coluna {col_idx} inferida como QUANTIDADE")
                elif 'unidade' not in column_mapping:
                    column_mapping['unidade'] = col_idx
                    logger.info(f"Coluna {col_idx} inferida como UNIDADE")
        
        if len(column_mapping) >= 2:  # Pelo menos item e descrição
            return 0, column_mapping  # Assume que dados começam na linha 0
        
        return None
    
    def fix_aglutinated_data(self, df: pd.DataFrame, column_mapping: Dict[str, int]) -> pd.DataFrame:
        """Corrige dados aglutinados entre colunas"""
        
        df_fixed = df.copy()
        
        # Corrige CATMAT misturado na descrição
        if 'descricao' in column_mapping:
            desc_col = column_mapping['descricao']
            
            for idx, row in df_fixed.iterrows():
                desc_text = str(row.iloc[desc_col])
                
                # Procura por padrão de CATMAT no início da descrição
                catmat_match = re.search(r'^(\\d{6,})\\s+(.+)', desc_text)
                if catmat_match:
                    catmat = catmat_match.group(1)
                    desc_clean = catmat_match.group(2)
                    
                    # Atualiza descrição
                    df_fixed.iloc[idx, desc_col] = desc_clean
                    
                    # Se não tem coluna CATMAT, cria uma
                    if 'catmat' not in column_mapping and len(df_fixed.columns) > desc_col + 1:
                        df_fixed.iloc[idx, desc_col + 1] = catmat
                        logger.debug(f"CATMAT {catmat} separado da descrição na linha {idx}")
        
        # Corrige valores aglutinados (valor unitário + total na mesma célula)
        if 'valor_unitario' in column_mapping:
            val_col = column_mapping['valor_unitario']
            
            for idx, row in df_fixed.iterrows():
                val_text = str(row.iloc[val_col])
                
                # Procura por dois valores na mesma célula
                valores = re.findall(r'\\d+[.,]\\d+', val_text)
                if len(valores) >= 2:
                    valor_unitario = self.extract_number(valores[0])
                    valor_total = self.extract_number(valores[1])
                    
                    if valor_unitario and valor_total:
                        df_fixed.iloc[idx, val_col] = valor_unitario
                        
                        # Se tem coluna de valor total, atualiza
                        if 'valor_total' in column_mapping:
                            total_col = column_mapping['valor_total']
                            df_fixed.iloc[idx, total_col] = valor_total
                        
                        logger.debug(f"Valores separados na linha {idx}: {valor_unitario} | {valor_total}")
        
        return df_fixed
    
    def extract_items_from_dataframe(self, df: pd.DataFrame) -> List[Dict]:
        """Extrai itens de um DataFrame de forma robusta"""
        
        if df.empty:
            return []
        
        # Detecta cabeçalho
        header_info = self.detect_header_row(df)
        if not header_info:
            logger.warning("Não foi possível detectar cabeçalho")
            return []
        
        header_row, column_mapping = header_info
        logger.info(f"Mapeamento de colunas: {column_mapping}")
        
        # Corrige dados aglutinados
        df_fixed = self.fix_aglutinated_data(df, column_mapping)
        
        items = []
        
        # Processa linhas de dados (após o cabeçalho)
        for idx in range(header_row + 1, len(df_fixed)):
            row = df_fixed.iloc[idx]
            
            # Extrai número do item
            item_num = None
            if 'item' in column_mapping:
                item_text = str(row.iloc[column_mapping['item']])
                
                # Tenta extrair número
                for pattern in self.column_patterns['item']:
                    match = re.search(pattern, item_text)
                    if match:
                        try:
                            item_num = int(match.group(1) if match.groups() else match.group(0))
                            break
                        except (ValueError, IndexError):
                            continue
                
                # Se não encontrou padrão, tenta converter direto
                if not item_num:
                    try:
                        item_num = int(float(item_text))
                    except (ValueError, TypeError):
                        continue
            
            if not item_num:
                continue
            
            # Extrai descrição
            descricao = ""
            if 'descricao' in column_mapping:
                descricao = self.clean_text(str(row.iloc[column_mapping['descricao']]))
            
            if not descricao or len(descricao) < 5:
                continue
            
            # Extrai outros campos
            unidade = "unidade"
            if 'unidade' in column_mapping:
                unidade_text = self.clean_text(str(row.iloc[column_mapping['unidade']]))
                if unidade_text and unidade_text.lower() not in ['nan', 'none', '']:
                    unidade = unidade_text
            
            quantidade = 1
            if 'quantidade' in column_mapping:
                qtd_num = self.extract_number(str(row.iloc[column_mapping['quantidade']]))
                if qtd_num and qtd_num > 0:
                    quantidade = int(qtd_num)
            
            valor_unitario = None
            if 'valor_unitario' in column_mapping:
                valor_unitario = self.extract_number(str(row.iloc[column_mapping['valor_unitario']]))
            
            valor_total = None
            if 'valor_total' in column_mapping:
                valor_total = self.extract_number(str(row.iloc[column_mapping['valor_total']]))
            
            # Calcula valores faltantes
            if not valor_unitario and valor_total and quantidade > 0:
                valor_unitario = valor_total / quantidade
            elif not valor_total and valor_unitario:
                valor_total = valor_unitario * quantidade
            
            # Define valores finais
            if not valor_unitario or valor_unitario <= 0:
                valor_unitario = "etapa"
                valor_total = "etapa"
            
            items.append({
                'Nº': item_num,
                'Descrição do Produto': descricao,
                'Unidade': unidade,
                'Quantidade': quantidade,
                'Valor Unitario': valor_unitario,
                'Valor Total': valor_total
            })
        
        return items
    
    def extract_with_camelot(self, pdf_path: str) -> List[Dict]:
        """Extrai usando Camelot (melhor para tabelas com bordas)"""
        if not CAMELOT_AVAILABLE:
            return []
        
        try:
            logger.info("Tentando extração com Camelot...")
            
            # Tenta diferentes configurações
            configs = [
                {'flavor': 'lattice', 'pages': 'all'},
                {'flavor': 'stream', 'pages': 'all'},
                {'flavor': 'lattice', 'pages': 'all', 'line_scale': 40},
            ]
            
            for config in configs:
                try:
                    tables = camelot.read_pdf(pdf_path, **config)
                    
                    if not tables:
                        continue
                    
                    logger.info(f"Camelot encontrou {len(tables)} tabelas")
                    
                    all_items = []
                    for i, table in enumerate(tables):
                        df = table.df
                        
                        if df.empty or len(df.columns) < 3:
                            continue
                        
                        items = self.extract_items_from_dataframe(df)
                        all_items.extend(items)
                        
                        if items:
                            logger.info(f"Tabela {i+1}: {len(items)} itens extraídos")
                    
                    if all_items:
                        return all_items
                        
                except Exception as e:
                    logger.warning(f"Erro na configuração Camelot: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Erro no Camelot: {e}")
        
        return []
    
    def extract_with_tabula(self, pdf_path: str) -> List[Dict]:
        """Extrai usando Tabula (fallback)"""
        if not TABULA_AVAILABLE:
            return []
        
        try:
            logger.info("Tentando extração com Tabula...")
            
            tables = read_pdf(pdf_path, pages='all', multiple_tables=True, 
                            pandas_options={'header': None}, silent=True)
            
            all_items = []
            for table in tables:
                if not isinstance(table, pd.DataFrame) or table.empty:
                    continue
                
                items = self.extract_items_from_dataframe(table)
                all_items.extend(items)
            
            return all_items
            
        except Exception as e:
            logger.error(f"Erro no Tabula: {e}")
            return []
    
    def extract_with_pdfplumber(self, pdf_path: str) -> List[Dict]:
        """Extrai usando PDFPlumber (fallback)"""
        if not PDFPLUMBER_AVAILABLE:
            return []
        
        try:
            logger.info("Tentando extração com PDFPlumber...")
            
            all_items = []
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    
                    for table in tables:
                        if not table or len(table) < 2:
                            continue
                        
                        df = pd.DataFrame(table)
                        items = self.extract_items_from_dataframe(df)
                        all_items.extend(items)
            
            return all_items
            
        except Exception as e:
            logger.error(f"Erro no PDFPlumber: {e}")
            return []
    
    def extract_from_pdf(self, pdf_path: str) -> List[Dict]:
        """Método principal que tenta diferentes engines"""
        logger.info(f"Processando: {os.path.basename(pdf_path)}")
        
        # Ordem de preferência baseada nos testes
        engines = []
        
        if CAMELOT_AVAILABLE:
            engines.append(("Camelot", self.extract_with_camelot))
        if TABULA_AVAILABLE:
            engines.append(("Tabula", self.extract_with_tabula))
        if PDFPLUMBER_AVAILABLE:
            engines.append(("PDFPlumber", self.extract_with_pdfplumber))
        
        if not engines:
            logger.error("Nenhum engine de extração disponível!")
            return []
        
        best_result = []
        best_count = 0
        
        for engine_name, engine_func in engines:
            try:
                items = engine_func(pdf_path)
                
                if len(items) > best_count:
                    best_result = items
                    best_count = len(items)
                    logger.info(f"{engine_name} extraiu {len(items)} itens (melhor até agora)")
                else:
                    logger.info(f"{engine_name} extraiu {len(items)} itens")
                
                # Se encontrou muitos itens, para de tentar
                if len(items) > 50:
                    break
                    
            except Exception as e:
                logger.error(f"Erro no {engine_name}: {e}")
                continue
        
        # Remove duplicatas
        if best_result:
            df = pd.DataFrame(best_result)
            df = df.drop_duplicates(subset=['Nº'], keep='first')
            df = df.sort_values('Nº').reset_index(drop=True)
            best_result = df.to_dict('records')
        
        logger.info(f"Total final: {len(best_result)} itens extraídos")
        return best_result
    
    def save_to_excel(self, items: List[Dict], output_path: str):
        """Salva itens em Excel com formatação"""
        if not items:
            logger.warning("Nenhum item para salvar")
            return
        
        try:
            df = pd.DataFrame(items)
            
            # Garante ordem das colunas
            column_order = ['Nº', 'Descrição do Produto', 'Unidade', 'Quantidade', 'Valor Unitario', 'Valor Total']
            df = df[column_order]
            
            # Salva em Excel
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Itens')
                
                # Ajusta largura das colunas
                worksheet = writer.sheets['Itens']
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
            
            logger.info(f"Arquivo salvo: {output_path}")
            
        except Exception as e:
            logger.error(f"Erro ao salvar Excel: {e}")

def process_pdf_folder(input_folder: str, output_folder: str):
    """Processa todos os PDFs de uma pasta"""
    
    extractor = PDFExtractorRobusto()
    
    # Cria pasta de saída
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    # Estatísticas
    processed_files = 0
    total_items = 0
    error_files = []
    
    logger.info("Iniciando processamento de PDFs")
    logger.info(f"Pasta de entrada: {input_folder}")
    logger.info(f"Pasta de saída: {output_folder}")
    
    # Lista PDFs
    pdf_files = [f for f in os.listdir(input_folder) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        logger.warning("Nenhum arquivo PDF encontrado")
        return
    
    logger.info(f"Encontrados {len(pdf_files)} arquivos PDF")
    
    # Processa cada PDF
    for i, filename in enumerate(pdf_files, 1):
        pdf_path = os.path.join(input_folder, filename)
        
        logger.info(f"\\n{'='*60}")
        logger.info(f"Processando {i}/{len(pdf_files)}: {filename}")
        logger.info(f"{'='*60}")
        
        try:
            items = extractor.extract_from_pdf(pdf_path)
            
            if items:
                processed_files += 1
                total_items += len(items)
                
                # Salva em Excel
                excel_filename = f"{os.path.splitext(filename)[0]}_v3_robusto.xlsx"
                excel_path = os.path.join(output_folder, excel_filename)
                extractor.save_to_excel(items, excel_path)
                
                logger.info(f"SUCESSO: {filename} - {len(items)} itens extraídos")
            else:
                logger.warning(f"FALHA: {filename} - Nenhum item encontrado")
                error_files.append(filename)
                
        except Exception as e:
            logger.error(f"ERRO: {filename} - {e}")
            error_files.append(filename)
    
    # Resumo final
    logger.info(f"\\n{'='*60}")
    logger.info("RESUMO DO PROCESSAMENTO")
    logger.info(f"{'='*60}")
    logger.info(f"Arquivos processados com sucesso: {processed_files}")
    logger.info(f"Total de itens extraídos: {total_items}")
    logger.info(f"Arquivos com problemas: {len(error_files)}")
    
    if error_files:
        logger.info("\\nArquivos que apresentaram problemas:")
        for file in error_files:
            logger.info(f"  - {file}")
    
    logger.info("\\nProcessamento concluído!")

if __name__ == "__main__":
    # Configuração para produção
    input_folder = "C:/Users/pietr/OneDrive/Área de Trabalho/ARTE/01_EDITAIS/DOWNLOADS"
    output_folder = os.path.join(input_folder, "tabelas_extraidas_v3")
    
    # Para teste local (descomente)
    # input_folder = "/home/ubuntu/upload"
    # output_folder = "/home/ubuntu/output_robusto"
    
    process_pdf_folder(input_folder, output_folder)

