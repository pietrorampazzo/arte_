# Estratégia: Realiza web scraping e OCR para dados adicionais.
# Funcionamento: Extrai dados de sites de fornecedores e PDFs.
# Integração: Fornece dados para validação de prompts.

import requests
from pdf2image import convert_from_path
import pytesseract

def scrape_supplier_data(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.text
    return None

def ocr_pdf(pdf_path):
    images = convert_from_path(pdf_path)
    return ''.join(pytesseract.image_to_string(image) for image in images)