import pdfplumber

def extrair_headers_pdf(caminho_pdf):
    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            tabelas = pagina.extract_tables()
            if tabelas:
                primeira_tabela = tabelas[0]
                headers = primeira_tabela[0]  # primeira linha é o header
                return headers
    return None  # Caso nenhuma tabela seja encontrada

# Uso da função
caminho = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\DOWNLOADS\153177_900142025.pdf"
headers = extrair_headers_pdf(caminho)

if headers:
    print("🔍 Headers encontrados:")
    for i, header in enumerate(headers):
        print(f"{i+1}. {header}")
else:
    print("⚠️ Nenhuma tabela ou headers encontrados no PDF.")
