import os
import json
from pdf2image import convert_from_path
import pytesseract
import re

# Caminho do Poppler (ajustado para sua pasta)
POPLER_PATH = r"C:\Users\pietr\OneDrive\.vscode\arte_\scripts\Release-25.07.0-0\poppler-25.07.0\Library\bin"
PASTA_EDITAIS = r"C:\Users\pietr\OneDrive\.vscode\arte_\EDITAIS"
TESSERACT_CMD = r"C:\Users\pietr\OneDrive\.vscode\arte_\scripts\Tesseract-OCR\tesseract.exe"
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

def extrair_texto_pdf(pdf_path):
    paginas = convert_from_path(pdf_path, dpi=300, poppler_path=POPLER_PATH)
    texto_completo = ""
    for pagina in paginas:
        texto = pytesseract.image_to_string(pagina, lang="por")
        texto_completo += texto + "\n\n"  # Adiciona separador de páginas para melhor legibilidade
    return texto_completo

def processar_pasta(pasta):
    arquivos = [f for f in os.listdir(pasta) if f.lower().endswith(".pdf")]
    for arquivo in arquivos:
        caminho_pdf = os.path.join(pasta, arquivo)
        print(f"Processando arquivo: {arquivo}")
        texto = extrair_texto_pdf(caminho_pdf)
        # Salva o texto completo em um arquivo .txt com o mesmo nome do PDF
        nome_txt = os.path.splitext(arquivo)[0] + ".txt"
        caminho_txt = os.path.join(pasta, nome_txt)
        with open(caminho_txt, "w", encoding="utf-8") as f:
            f.write(texto)
        print(f"Texto extraído salvo em: {caminho_txt}")

if __name__ == "__main__":
    processar_pasta(PASTA_EDITAIS)