import os
from pdf2image import convert_from_path
import pytesseract

# Caminho do Poppler
POPLER_PATH = r"C:\Users\pietr\OneDrive\.vscode\arte_\scripts\Release-25.07.0-0\poppler-25.07.0\Library\bin"
# Caminho para a pasta de editais
PASTA_EDITAIS = r"C:\Users\pietr\OneDrive\.vscode\arte_\EDITAIS"
# Caminho para o executável do Tesseract
TESSERACT_CMD = r"C:\Users\pietr\OneDrive\.vscode\arte_\scripts\Tesseract-OCR\tesseract.exe"
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

def extrair_texto_pdf(pdf_path):
    """
    Extrai texto de um arquivo PDF usando OCR.
    """
    try:
        paginas = convert_from_path(pdf_path, dpi=300, poppler_path=POPLER_PATH)
        texto_completo = ""
        for i, pagina in enumerate(paginas):
            print(f"  Lendo página {i+1}/{len(paginas)}...")
            texto = pytesseract.image_to_string(pagina, lang="por")
            texto_completo += texto + "\n\n"
        return texto_completo
    except Exception as e:
        print(f"  Erro ao processar o PDF {pdf_path}: {e}")
        return ""

def processar_subpastas_editais(pasta_base):
    """
    Processa cada subpasta na pasta de editais para extrair texto do PDF correto.
    """
    for nome_item in os.listdir(pasta_base):
        caminho_item = os.path.join(pasta_base, nome_item)
        if os.path.isdir(caminho_item):
            print(f"Processando pasta: {nome_item}")
            pdf_encontrado = None
            for arquivo in os.listdir(caminho_item):
                if arquivo.lower().endswith(".pdf") and not arquivo.lower().startswith("relacaoitens"):
                    pdf_encontrado = arquivo
                    break
            
            if pdf_encontrado:
                caminho_pdf = os.path.join(caminho_item, pdf_encontrado)
                print(f"  Encontrado PDF para extração: {pdf_encontrado}")
                
                texto_extraido = extrair_texto_pdf(caminho_pdf)
                
                if texto_extraido:
                    caminho_txt = os.path.join(caminho_item, "PDF.txt")
                    with open(caminho_txt, "w", encoding="utf-8") as f:
                        f.write(texto_extraido)
                    print(f"  Texto extraído salvo em: {caminho_txt}")
            else:
                print(f"  Nenhum PDF alvo encontrado na pasta {nome_item}.")

if __name__ == "__main__":
    processar_subpastas_editais(PASTA_EDITAIS)
