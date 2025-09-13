import pandas as pd
import fitz  # PyMuPDF
import re
import os
from pathlib import Path

# Configurações de diretórios
BASE_DIR = Path("C:\\Users\\pietr\\OneDrive\\.vscode\\arte_\\EDITAIS")
DOWNLOADS_DIR = Path("DOWNLOADS")
SUMMARY_EXCEL_PATH = DOWNLOADS_DIR / "summary.xlsx"
FINAL_MASTER_PATH = DOWNLOADS_DIR / "master.xlsx"

# Palavras-chave para filtro (mantendo as mesmas do script original)
PALAVRAS_CHAVE = [
    r'Instrumento Musical - Sopro', r'Instrumento Musical - Corda',r'Instrumento Musical - Percursão',
    r'Instrumento Musical', r'Peças e acessórios instrumento musical', r'Cabo Rede Computador'
    r'saxofone', r'trompete', r'tuba', r'clarinete', r'óleo lubrificante',r'trompa', r'sax', r'óleos para válvulas',
    r'violão', r'Guitarra', r'Baixo', r'Violino', r'Viola', r'Cavaquinho',r'Bandolim', r'Ukulele', 
    r'Microfone', r'Microfone direcional', r'Suporte microfone', r'Microfone Dinâmico', r'Microfone de Lapela',
    r'Base microfone', r'Pedestal microfone', r'Medusa para microfone', r'Pré-amplificador microfone',
    r'Caixa Acústica', r'Caixa de Som', r'Caixa som', r'Subwoofer', r'tarol', r'Estante - partitura',
    r'Amplificador de áudio', r'Amplificador som', r'Amplificador fone ouvido'
    r'Piano', r'Suporte para teclado', r'Mesa áudio', r'Interface de Áudio', r'Piano',
    r'Pedestal', r'Pedestal caixa acústica', r'Pedal Efeito', r'fone de ouvido', r'headset', 
    r'Bateria Eletrônica', r'Cabo extensor',r'Tela projeção', r'Projetor Multimídia',
]
REGEX_FILTRO = re.compile('|'.join(PALAVRAS_CHAVE), re.IGNORECASE)

def extract_items_from_text(text):
    """Extrai itens do texto do PDF usando regex."""
    items = []
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r'\s+', ' ', text)

    item_pattern = re.compile(r'(\d+)\s*-\s*([^0-9]+?)(?=Descrição Detalhada:)', re.DOTALL | re.IGNORECASE)
    item_matches = list(item_pattern.finditer(text))

    for i, match in enumerate(item_matches):
        item_num = match.group(1).strip()
        item_nome = match.group(2).strip()
        start_pos = match.start()
        end_pos = item_matches[i + 1].start() if i + 1 < len(item_matches) else len(text)
        item_text = text[start_pos:end_pos]

        # Extrai descrição detalhada
        descricao_match = re.search(r'Descrição Detalhada:\s*(.*?)(?=Tratamento Diferenciado:)|Aplicabilidade Decreto|$',
                                   item_text, re.DOTALL | re.IGNORECASE)
        descricao = ""
        if descricao_match:
            descricao = descricao_match.group(1).strip()
            descricao = re.sub(r'\s+', ' ', descricao)
            descricao = re.sub(r'[^\w\s:,.()/-]', '', descricao)

        item_completo = f"{item_nome}"
        if descricao:
            item_completo += f" {descricao}"

        # Extrai quantidade
        quantidade_match = re.search(r'Quantidade Total:\s*(\d+)', item_text, re.IGNORECASE)
        quantidade = quantidade_match.group(1) if quantidade_match else ""

        # Extrai valor unitário
        valor_unitario = ""
        valor_unitario_match = re.search(r'Valor Unitário[^:]*:\s*R?\$?\s*([\d.,]+)', item_text, re.IGNORECASE)
        if valor_unitario_match:
            valor_unitario = valor_unitario_match.group(1)

        # Extrai valor total
        valor_total = ""
        valor_total_match = re.search(r'Valor Total[^:]*:\s*R?\$?\s*([\d.,]+)', item_text, re.IGNORECASE)
        if valor_total_match:
            valor_total = valor_total_match.group(1)

        # Extrai unidade de fornecimento
        unidade_match = re.search(r'Unidade de Fornecimento:\s*([^0-9\n]+?)(?=\s|$|\n)', item_text, re.IGNORECASE)
        unidade = unidade_match.group(1).strip() if unidade_match else ""

        # Extrai local de entrega
        local = ""
        local_match = re.search(r'Local de Entrega[^:]*:\s*([^(\n]+?)(?:\s*\(|$|\n)', item_text, re.IGNORECASE)
        if local_match:
            local = local_match.group(1).strip()

        item_data = {
            "Nº": item_num,
            "DESCRICAO": item_completo,
            "QTDE": quantidade,
            "VALOR_UNIT": valor_unitario,
            "VALOR_TOTAL": valor_total,
            "UNID_FORN": unidade,
            "LOCAL_ENTREGA": local
        }
        items.append(item_data)

    return items

def process_pdf_file(pdf_path):
    """Processa um arquivo PDF e extrai seu conteúdo."""
    print(f"Processando: {pdf_path}")
    text = ""
    try:
        with fitz.open(pdf_path) as doc:
            for page in doc:
                text += page.get_text()
    except Exception as e:
        print(f"Erro ao processar PDF {pdf_path}: {e}")
        return []
    
    if not text.strip():
        print(f"  Aviso: Nenhum texto extraído de {pdf_path}")
        return []
    
    return extract_items_from_text(text)

def tratar_dataframe(df):
    """Trata e padroniza o DataFrame."""
    if df.empty:
        return df

    # Converte valores numéricos
    if 'QTDE' in df.columns:
        df['QTDE'] = pd.to_numeric(df['QTDE'], errors='coerce').fillna(0)

    for col in ['VALOR_UNIT', 'VALOR_TOTAL']:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace('.', '', regex=False)
                .str.replace(',', '.', regex=False)
            )
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Calcula valores ausentes
    mask = (df['VALOR_UNIT'] == 0) & (df['VALOR_TOTAL'] > 0) & (df['QTDE'] > 0)
    df.loc[mask, 'VALOR_UNIT'] = df.loc[mask, 'VALOR_TOTAL'] / df.loc[mask, 'QTDE']

    if 'QTDE' in df.columns and 'VALOR_UNIT' in df.columns:
        df['VALOR_TOTAL'] = df['QTDE'] * df['VALOR_UNIT']

    # Formata valores monetários
    for col in ['VALOR_UNIT', 'VALOR_TOTAL']:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: f"{x:.2f}".replace(".", ","))

    return df

def criar_planilhas():
    """Função principal que cria as planilhas summary.xlsx e master.xlsx"""
    # Cria diretório de downloads se não existir
    DOWNLOADS_DIR.mkdir(exist_ok=True)
    
    all_dfs = []
    for pasta in BASE_DIR.iterdir():
        if pasta.is_dir():
            folder_name = pasta.name
            for arquivo in pasta.glob("RelacaoItens*.pdf"):
                items = process_pdf_file(arquivo)
                if items:
                    df_pasta = pd.DataFrame(items)
                    df_pasta["ARQUIVO"] = folder_name
                    all_dfs.append(df_pasta)
    
    if not all_dfs:
        print("Nenhum item encontrado nos PDFs.")
        return
    
    # Cria o DataFrame com todos os itens
    df_all = pd.concat(all_dfs, ignore_index=True)
    df_all = tratar_dataframe(df_all)

    # Salva os arquivos individuais
    for folder_name, df_group in df_all.groupby('ARQUIVO'):
        output_path = BASE_DIR / folder_name / f"{folder_name}.xlsx"
        df_group.to_excel(output_path, index=False)
        print(f"✅ Arquivo {output_path.name} criado com {len(df_group)} itens")

    # Salva summary.xlsx
    df_all.to_excel(SUMMARY_EXCEL_PATH, index=False)
    print(f"✅ Arquivo summary.xlsx criado com {len(df_all)} itens")
    
    # Filtra itens relevantes para master.xlsx
    mask = df_all['DESCRICAO'].apply(lambda x: bool(REGEX_FILTRO.search(str(x))))
    df_filtered = df_all[mask].copy()
    
    # Salva master.xlsx
    df_filtered.to_excel(FINAL_MASTER_PATH, index=False)
    print(f"✅ Arquivo master.xlsx criado com {len(df_filtered)} itens relevantes")

if __name__ == "__main__":
    print("="*60)
    print("PROCESSADOR DE EDITAIS DE TESTE")
    print("="*60)
    criar_planilhas()
    print("\nProcessamento concluído!")