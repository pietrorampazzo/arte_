"""
Pipeline sequencial:
1. Download dos editais (Wavecode)
2. Descompactação dos arquivos ZIP baixados
3. Extração e renomeação dos arquivos RelacaoItens*.pdf
4. Conversão dos PDFs para Excel (com lógica COT)
"""
import os
from A_download_edital import main as download_editais
import B_depx

PASTA_DOWNLOAD = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\DOWNLOADS"
PASTA_ORCAMENTOS = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\ORCAMENTOS"

def pipeline():
    print("="*60)
    print("INICIANDO PIPELINE ARTE COMERCIAL")
    print("="*60)

    # 1. Download dos editais
    print("\n[1/4] Baixando editais do portal Wavecode...")
    download_editais()

    # 2. Descompactar arquivos ZIP
    print("\n[2/4] Descompactando arquivos ZIP baixados...")
    B_depx.descompactar_arquivos(PASTA_DOWNLOAD)

    # 3. Extrair e renomear RelacaoItens*.pdf
    print("\n[3/4] Extraindo e renomeando arquivos RelacaoItens*.pdf...")
    B_depx.extrair_e_copiar_pdfs(PASTA_DOWNLOAD, PASTA_DOWNLOAD)

    # 4. Converter PDFs para Excel (com lógica COT)
    print("\n[4/4] Convertendo PDFs para Excel (com lógica COT)...")
    B_depx.pdfs_para_xlsx(PASTA_DOWNLOAD, PASTA_ORCAMENTOS)

    print("\nPIPELINE FINALIZADO!")
    print(f"Arquivos Excel gerados em: {PASTA_ORCAMENTOS}")

if __name__ == "__main__":
    pipeline()


