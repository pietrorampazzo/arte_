# Estratégia: Extrai texto de PDFs usando OCR.
# Funcionamento: Converte PDFs em imagens e usa Tesseract para extrair texto.
# Integração: Fornece texto para parsing e análise.

from pdf2image import convert_from_path
import pytesseract

def extract_text_from_pdf(pdf_path):
    images = convert_from_path(pdf_path)
    text = ''
    for image in images:
        text += pytesseract.image_to_string(image)
    return text