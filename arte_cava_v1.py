import os
import json
from pdf2image import convert_from_path
import pytesseract
import os
import re
from pdf2image import convert_from_path
import pytesseract
import pandas as pd

# Caminho do Poppler (ajustado para sua pasta)
POPLER_PATH = r"C:\Users\pietr\OneDrive\.vscode\arte_\scripts\Release-25.07.0-0\poppler-25.07.0\Library\bin"
PASTA_EDITAIS = r"C:\Users\pietr\OneDrive\.vscode\arte_\EDITAIS"
TESSERACT_CMD = r"caminho/para/tesseract.exe" # caminho para tesseract executável (Windows)
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
pytesseract.pytesseract.tesseract_cmd = r"C:\Users\pietr\OneDrive\.vscode\arte_\scripts\Tesseract-OCR\tesseract.exe"


def extrair_texto_pdf(pdf_path):
    paginas = convert_from_path(pdf_path, dpi=300, poppler_path=POPLER_PATH)
    texto_completo = ""
    for pagina in paginas:
        texto = pytesseract.image_to_string(pagina, lang="por")
        texto_completo += texto + "\n"
    return texto_completo

def extrair_numero_descricao(texto):
    linhas = [l.strip() for l in texto.splitlines() if l.strip()]
    itens = []
    numero_atual = None
    descricao_atual = []

    # Regex para linha que começa com número (Nº do item)
    regex_numero = re.compile(r"^(\d+)\s*[-\.\)]?\s*(.*)")

    for linha in linhas:
        m = regex_numero.match(linha)
        if m:
            # Se já temos um item em construção, salva antes de iniciar novo
            if numero_atual is not None:
                descricao = " ".join(descricao_atual).strip()
                itens.append({"Nº": numero_atual, "DESCRICAO": descricao})
            numero_atual = m.group(1)
            descricao_inicial = m.group(2).strip()
            descricao_atual = [descricao_inicial] if descricao_inicial else []
        else:
            # Linha que provavelmente faz parte da descrição do item atual
            if numero_atual is not None:
                descricao_atual.append(linha)

    # Salva o último item
    if numero_atual is not None:
        descricao = " ".join(descricao_atual).strip()
        itens.append({"Nº": numero_atual, "DESCRICAO": descricao})

    return itens

def processar_pasta(pasta):
    todos_itens = []
    arquivos = [f for f in os.listdir(pasta) if f.lower().endswith(".pdf")]
    for arquivo in arquivos:
        caminho_pdf = os.path.join(pasta, arquivo)
        print(f"Processando arquivo: {arquivo}")
        texto = extrair_texto_pdf(caminho_pdf)
        itens = extrair_numero_descricao(texto)
        for item in itens:
            item["ARQUIVO_ORIGEM"] = arquivo
        todos_itens.extend(itens)
    return todos_itens

def salvar_excel(itens, arquivo_saida):
    df = pd.DataFrame(itens)
    df.to_excel(arquivo_saida, index=False)
    print(f"Arquivo Excel salvo em: {arquivo_saida}")

if __name__ == "__main__":
    itens_extraidos = processar_pasta(PASTA_EDITAIS)
    salvar_excel(itens_extraidos, "resultado_simples.xlsx")
