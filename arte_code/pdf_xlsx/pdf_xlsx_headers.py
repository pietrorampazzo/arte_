import camelot
import os
import pandas as pd
import re
from typing import List, Optional, Union

# Configurações de caminhos
PASTA_PDFS = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\DOWNLOADS"
PASTA_SAIDA = os.path.join(PASTA_PDFS, "tabelas_extraidas")
os.makedirs(PASTA_SAIDA, exist_ok=True)

# Colunas desejadas
COLUNAS_DESEJADAS = ['Nº', 'Descrição', 'Unidade', 'Quantidade Total', 'Valor Unitario', 'Valor Total']

# Palavras-chave para mapear colunas
MAPEAMENTO_COLUNAS = {
    'Nº': ['item', 'número do item', 'grupo', ' N°'] ,             
    'Descrição': ['descrição', 'especificação', 'item'],
    'Unidade': ['unidade', 'unid', 'medida'],
    'Quantidade Total': ['qtd', 'quantidade', 'quantidade total'],
    'Valor Unitario': ['valor unitário','Preço Médio Untiário', 'valor unitario'],
    'Valor Total': ['total', 'valor total']
}

# Padrões regex para cabeçalhos (expandidos)
PADROES_CABECALHO = [
    re.compile(r'^\s*(grupo|item)\s*$', re.IGNORECASE),
    re.compile(r'^.*(especifica[cç][aã]o|descrição).*$', re.IGNORECASE),
    re.compile(r'^.*(unid|medida).*$', re.IGNORECASE),
    re.compile(r'^.*(qtd|quantidade).*$', re.IGNORECASE),
    re.compile(r'^.*(valor unitário|valor unitario).*$', re.IGNORECASE),
    re.compile(r'^.*(total|valor total).*$', re.IGNORECASE)
]

def detectar_cabecalho(df: pd.DataFrame) -> Optional[int]:
    for idx in range(min(5, len(df))):  # Verifica até 5 primeiras linhas
        linha = df.iloc[idx].str.strip().str.lower()
        matches = sum(1 for col in linha if any(p.search(str(col)) for p in PADROES_CABECALHO))
        if matches >= 4:  # Pelo menos 4 colunas correspondem
            return idx
    return None

def renomear_colunas(df: pd.DataFrame) -> pd.DataFrame:
    col_map = {}
    for col in df.columns:
        col_lower = str(col).strip().lower()
        for desired, keywords in MAPEAMENTO_COLUNAS.items():
            if any(kw in col_lower for kw in keywords):
                col_map[col] = desired
                break
    df = df.rename(columns=col_map)
    # Adiciona colunas ausentes com NaN
    for col in COLUNAS_DESEJADAS:
        if col not in df.columns:
            df[col] = pd.NA
    return df[COLUNAS_DESEJADAS]  # Reordena para o modelo desejado

def limpar_valores(valor: Union[str, float]) -> Union[str, float]:
    if isinstance(valor, str):
        valor = valor.strip()
        valor = re.sub(r'[^\d,.-]', '', valor)  # Remove símbolos não numéricos
        if re.match(r'^-?\d{1,3}(?:\.\d{3})*(?:,\d+)$', valor):
            valor = valor.replace('.', '').replace(',', '.')
        elif re.match(r'^-?\d{1,3}(?:,\d{3})*(?:\.\d+)$', valor):
            valor = valor.replace(',', '')
    try:
        return float(valor) if valor else valor
    except ValueError:
        return valor

def processar_tabela(df: pd.DataFrame) -> pd.DataFrame:
    """
    Processa uma tabela extraída: detecta cabeçalho, remove duplicados e limpa dados.
    """
    # Detecta e define o cabeçalho
    idx_cabecalho = detectar_cabecalho(df)
    if idx_cabecalho is not None:
        df.columns = df.iloc[idx_cabecalho]
        df = df.iloc[idx_cabecalho+1:].reset_index(drop=True)
    
    # Remove linhas vazias ou quase vazias
    df = df.dropna(how='all')
    df = df[df.iloc[:, 0].str.strip().astype(bool)].reset_index(drop=True)
    
    # Remove cabeçalhos duplicados no meio da tabela
    df = df[~df.iloc[:, 0].str.strip().str.lower().isin(['item', 'grupo'])]
    
    # Limpa valores numéricos
    for col in df.columns:
        if 'valor' in str(col).lower() or 'qtd' in str(col).lower():
            df[col] = df[col].apply(limpar_valores)
    
    df = renomear_colunas(df)  # Aplica mapeamento final
    return df

def extrair_tabelas_pdf(caminho_pdf: str) -> pd.DataFrame:
    """
    Extrai tabelas de um PDF usando Camelot com estratégias alternadas.
    """
    print(f"\n🔍 Processando: {os.path.basename(caminho_pdf)}")
    
    # Tenta primeiro com lattice (para tabelas com bordas)
    try:
        tabelas = camelot.read_pdf(
            caminho_pdf, 
            pages="all", 
            flavor="lattice", 
            strip_text="\n",
            suppress_stdout=True,
            line_scale=40  # Ajuste fino para detectar linhas
        )
    except Exception as e:
        print(f"⚠️ Erro com lattice: {e}")
        tabelas = []
    
    # Se não encontrou com lattice, tenta com stream
    if not tabelas:
        try:
            tabelas = camelot.read_pdf(
                caminho_pdf,
                pages="all",
                flavor="stream",
                strip_text="\n",
                suppress_stdout=True,
                row_tol=10  # Tolerância para junção de linhas
            )
        except Exception as e:
            print(f"⚠️ Erro com stream: {e}")
            return pd.DataFrame()
    
    print(f"📊 {len(tabelas)} tabelas encontradas")
    
    if not tabelas:
        return pd.DataFrame()
    
    # Processa cada tabela individualmente
    dfs_processados = []
    for i, tabela in enumerate(tabelas, 1):
        try:
            df = processar_tabela(tabela.df)
            if not df.empty:
                dfs_processados.append(df)
                print(f"   Tabela {i}: {len(df)} linhas válidas")
        except Exception as e:
            print(f"   ⚠️ Erro ao processar tabela {i}: {e}")
    
    # Combina todas as tabelas processadas
    if dfs_processados:
        return pd.concat(dfs_processados, ignore_index=True)
    return pd.DataFrame()

def processar_todos_pdfs(pasta: str):
    """
    Processa todos os PDFs na pasta especificada.
    """
    for nome_arquivo in os.listdir(pasta):
        if nome_arquivo.lower().endswith(".pdf"):
            caminho_pdf = os.path.join(pasta, nome_arquivo)
            df = extrair_tabelas_pdf(caminho_pdf)
            
            if not df.empty:
                nome_saida = os.path.splitext(nome_arquivo)[0] + "_tabelas.xlsx"
                caminho_saida = os.path.join(PASTA_SAIDA, nome_saida)
                df.to_excel(caminho_saida, index=False)
                print(f"✅ Salvo em: {caminho_saida}")
            else:
                print(f"⚠️ Nenhuma tabela válida em {nome_arquivo}")

if __name__ == "__main__":
    print("Iniciando extração de tabelas de PDFs...")
    processar_todos_pdfs(PASTA_PDFS)
    print("\nProcessamento concluído!")