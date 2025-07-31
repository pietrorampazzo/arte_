import camelot
import os
import pandas as pd
import re

# Caminho para a pasta onde estão os PDFs
PASTA_PDFS = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\DOWNLOADS"
PASTA_SAIDA = os.path.join(PASTA_PDFS, "tabelas_extraidas")
os.makedirs(PASTA_SAIDA, exist_ok=True)

# Padrão para identificar cabeçalhos repetidos
PADROES_CABECALHO = [
    re.compile(r'^item$', re.IGNORECASE),
    re.compile(r'^material.*servic.*$', re.IGNORECASE),
    re.compile(r'^unid.*$', re.IGNORECASE),
    re.compile(r'^qtd.*$', re.IGNORECASE)
]

def remover_cabecalhos_duplicados(df):
    def eh_cabecalho(linha):
        return any(p.match(str(linha[0]).strip()) for p in PADROES_CABECALHO)
    return df[~df.apply(eh_cabecalho, axis=1)].reset_index(drop=True)

def unificar_linhas_quebradas(df):
    colunas = df.columns.tolist()
    nova_linha = []
    linhas_limpa = []
    
    for idx, row in df.iterrows():
        primeira_coluna = str(row[colunas[0]]).strip()
        if primeira_coluna and (not primeira_coluna.startswith("nan")):
            if nova_linha:
                linhas_limpa.append(nova_linha)
            nova_linha = row.tolist()
        else:
            for i in range(len(row)):
                texto_atual = str(nova_linha[i]) if i < len(nova_linha) else ''
                texto_adicional = str(row[colunas[i]])
                if pd.notna(texto_adicional) and not texto_adicional.lower().strip().startswith("nan"):
                    nova_linha[i] = f"{texto_atual} {texto_adicional}".strip()
    if nova_linha:
        linhas_limpa.append(nova_linha)
    return pd.DataFrame(linhas_limpa, columns=colunas)

def extrair_tabelas_pdf(caminho_pdf):
    print(f"🔍 Extraindo tabelas de: {os.path.basename(caminho_pdf)}")
    try:
        tabelas = camelot.read_pdf(caminho_pdf, pages="all", flavor="lattice", strip_text="\n")
        print(f"📄 {len(tabelas)} tabelas encontradas")
        if not tabelas:
            return pd.DataFrame()
        df = pd.concat([t.df for t in tabelas], ignore_index=True)
        df = remover_cabecalhos_duplicados(df)
        df = unificar_linhas_quebradas(df)
        return df
    except Exception as e:
        print(f"⚠️ Erro ao processar {caminho_pdf}: {e}")
        return pd.DataFrame()

def processar_todos_pdfs(pasta):
    for nome_arquivo in os.listdir(pasta):
        if nome_arquivo.lower().endswith(".pdf"):
            caminho_pdf = os.path.join(pasta, nome_arquivo)
            df = extrair_tabelas_pdf(caminho_pdf)
            if not df.empty:
                nome_saida = os.path.splitext(nome_arquivo)[0] + "_v2_tabelas.xlsx"
                caminho_saida = os.path.join(PASTA_SAIDA, nome_saida)
                df.to_excel(caminho_saida, index=False)
                print(f"✅ Tabela estruturada salva em: {caminho_saida}")
            else:
                print(f"⚠️ Nenhuma tabela extraída de {nome_arquivo}")

if __name__ == "__main__":
    processar_todos_pdfs(PASTA_PDFS)