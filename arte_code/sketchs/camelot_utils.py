import camelot
import os
import pandas as pd

# Caminho para a pasta onde estão os PDFs
PASTA_PDFS = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\DOWNLOADS"  # <- Substitua

# Pasta onde salvar os resultados
PASTA_SAIDA = os.path.join(PASTA_PDFS, "tabelas_extraidas")
os.makedirs(PASTA_SAIDA, exist_ok=True)

def extrair_tabelas_pdf(caminho_pdf):
    print(f"🔍 Extraindo tabelas de: {os.path.basename(caminho_pdf)}")
    try:
        tabelas = camelot.read_pdf(caminho_pdf, pages="all", flavor="lattice", strip_text="\n")
        print(f"📄 {len(tabelas)} tabelas encontradas")
        if tabelas:
            df_final = pd.concat([t.df for t in tabelas], ignore_index=True)
            return df_final
        else:
            return pd.DataFrame()
    except Exception as e:
        print(f"⚠️ Erro ao processar {caminho_pdf}: {e}")
        return pd.DataFrame()

def processar_todos_pdfs(pasta):
    for nome_arquivo in os.listdir(pasta):
        if nome_arquivo.lower().endswith(".pdf"):
            caminho_pdf = os.path.join(pasta, nome_arquivo)
            df = extrair_tabelas_pdf(caminho_pdf)
            if not df.empty:
                nome_saida = os.path.splitext(nome_arquivo)[0] + "_tabelas.xlsx"
                caminho_saida = os.path.join(PASTA_SAIDA, nome_saida)
                df.to_excel(caminho_saida, index=False)
                print(f"✅ Tabela consolidada salva em: {caminho_saida}")
            else:
                print(f"⚠️ Nenhuma tabela extraída de {nome_arquivo}")

if __name__ == "__main__":
    processar_todos_pdfs(PASTA_PDFS)
