import os
import pdfplumber
import pandas as pd
import google.generativeai as genai
from dotenv import load_dotenv
import re
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io

# --- CONFIGURAÇÃO INICIAL ---
# Chama a função para carregar as variáveis do arquivo .env
load_dotenv()

# 🔑 Configure sua chave de API Gemini
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Função para extrair texto bruto das páginas do PDF
def extrair_texto_pdf_com_ocr(pdf_path):
    """
    Extrai texto de um PDF, usando OCR se necessário.
    Primeiro tenta extrair texto nativo. Se falhar, converte a página para imagem e aplica OCR.
    """
    textos_por_pagina = []
    try:
        # Tenta com pdfplumber primeiro (para PDFs baseados em texto)
        print("Tentando extração de texto nativo com pdfplumber...")
        with pdfplumber.open(pdf_path) as pdf:
            for i, pagina in enumerate(pdf.pages):
                texto = pagina.extract_text()
                if texto and texto.strip():
                    textos_por_pagina.append(f"--- PÁGINA {i+1} (Texto Nativo) ---\n{texto}")
        
        if textos_por_pagina:
            print("Extração de texto nativo bem-sucedida.")
            return textos_por_pagina

        # Se pdfplumber não retornou nada, partimos para o OCR com PyMuPDF
        print("Nenhum texto nativo encontrado. Partindo para a extração com OCR...")
        textos_por_pagina = [] # Reseta a lista
        doc = fitz.open(pdf_path)
        for i, page in enumerate(doc):
            print(f"   -> Processando OCR da página {i+1}...")
            # Renderiza a página como uma imagem de alta resolução
            pix = page.get_pixmap(dpi=300)
            img_bytes = pix.tobytes("png")
            
            # Converte os bytes da imagem para um objeto de imagem PIL
            img = Image.open(io.BytesIO(img_bytes))
            
            # Extrai o texto usando Tesseract (especificando o português)
            try:
                texto_ocr = pytesseract.image_to_string(img, lang='por')
                if texto_ocr and texto_ocr.strip():
                    textos_por_pagina.append(f"--- PÁGINA {i+1} (OCR) ---\n{texto_ocr}")
            except pytesseract.TesseractNotFoundError:
                print("\nERRO: O executável do Tesseract OCR não foi encontrado.")
                print("Por favor, instale o Tesseract no seu sistema e adicione-o ao PATH do sistema.")
                print("Instruções: https://tesseract-ocr.github.io/tessdoc/Installation.html")
                return None # Retorna None para indicar uma falha crítica
            except Exception as e:
                print(f"   -> Erro no OCR da página {i+1}: {e}")

        doc.close()
        if textos_por_pagina:
            print("Extração com OCR concluída.")
        else:
            print("Nenhum texto pôde ser extraído com OCR.")
        return textos_por_pagina

    except Exception as e:
        print(f"Ocorreu um erro inesperado ao processar o PDF: {e}")
        return []

# Função para processar com Gemini AI e identificar tabelas
def processar_com_gemini(texto_pagina):
    """Envia o texto de uma página para o Gemini e pede para extrair la tabela."""
    model = genai.GenerativeModel("gemini-1.5-pro") # Usando um modelo mais robusto
    prompt = f'''
    Você receberá o texto extraído de uma página de um edital em PDF.
    Sua tarefa é extrair as linhas da tabela de itens que encontrar nesta página.
    Mantenha a estrutura da tabela e formate a saída como uma lista de listas Python,
    onde cada lista interna representa uma linha da tabela.
    O formato esperado é: [Item, Descrição, Quantidade, Unidade, Valor Unitário, Valor Total]

    Se não houver uma tabela ou linhas de tabela nesta página, retorne uma lista vazia [].

    Texto da Página:
    {texto_pagina}
    '''
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Erro ao chamar a API Gemini: {e}")
        return "[]" # Retorna lista vazia em caso de erro

def parse_resposta_gemini(resposta_bruta):
    """Analisa a resposta de texto do Gemini para extrair a lista de listas."""
    # Remove cercas de markdown e a palavra 'python'
    resposta_limpa = re.sub(r"```python\n|```", "", resposta_bruta.strip())

    # Tenta avaliar a string como um literal Python (cuidado: use com cautela)
    try:
        # A resposta pode ter lixo antes ou depois da lista. Vamos encontrar a lista.
        match = re.search(r'\[\s*\[.*\]\s*\]', resposta_limpa, re.DOTALL)
        if match:
            lista_extraida = eval(match.group(0))
            if isinstance(lista_extraida, list):
                return lista_extraida
    except (SyntaxError, ValueError, NameError) as e:
        print(f"Nao foi possivel parsear a resposta do Gemini como lista: {e}")
        print(f"Resposta recebida:\n{resposta_bruta}")

    return []


if __name__ == "__main__":
    pdf_path = r"C:\\Users\\pietr\\OneDrive\\.vscode\\arte_\\DOWNLOADS\\EDITAIS_TESTE\\teste.pdf"
    output_path = "tabelas_extraidas.xlsx"
    
    print(f"Lendo o arquivo PDF: {pdf_path}")
    textos_por_pagina = extrair_texto_pdf_com_ocr(pdf_path)
    
    if not textos_por_pagina:
        print("Nao foi possivel extrair texto do PDF.")
    else:
        print(f"Encontradas {len(textos_por_pagina)} paginas com texto.")
        
        todas_as_linhas_da_tabela = []
        for i, texto_pagina in enumerate(textos_por_pagina):
            print(f"Processando pagina {i+1}/{len(textos_por_pagina)} com a IA...")
            
            resposta_gemini = processar_com_gemini(texto_pagina)
            linhas_da_pagina = parse_resposta_gemini(resposta_gemini)
            
            if linhas_da_pagina:
                print(f"   -> Encontradas {len(linhas_da_pagina)} linhas de tabela na pagina {i+1}.")
                todas_as_linhas_da_tabela.extend(linhas_da_pagina)
            else:
                print(f"   -> Nenhuma linha de tabela encontrada na pagina {i+1}.")

        if todas_as_linhas_da_tabela:
            print(f"\nTotal de {len(todas_as_linhas_da_tabela)} linhas de tabela extraidas.")
            
            # Define as colunas esperadas
            colunas = ["Item", "Descrição", "Quantidade", "Unidade", "Valor Unitário", "Valor Total"]
            
            # Cria o DataFrame
            df = pd.DataFrame(todas_as_linhas_da_tabela)
            
            # Ajusta os nomes das colunas para o número de colunas que realmente temos
            num_colunas_reais = len(df.columns)
            df.columns = colunas[:num_colunas_reais]

            # Salva em Excel
            df.to_excel(output_path, index=False)
            print(f"Arquivo Excel gerado com sucesso: {output_path}")
        else:
            print("Nenhuma tabela foi encontrada em todo o documento.")