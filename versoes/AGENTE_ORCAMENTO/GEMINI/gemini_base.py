import pandas as pd
import google.generativeai as genai

GOOGLE_API_KEY = 'AIzaSyBdrzcton2jUCv5PSaXE38UCp-l8O42Fvc'
genai.configure(api_key=GOOGLE_API_KEY)

# Carrega a base de produtos
CAMINHO_PRODUTOS = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\data_base.xlsx"
df = pd.read_excel(CAMINHO_PRODUTOS)

# Selecione só as colunas úteis para o prompt
colunas_interesse = ["DESCRICAO", "Marca", "Modelo", "Valor"]  # ajuste conforme sua planilha
df_prompt = df[colunas_interesse].head(10)  # limite para não estourar o token limit

# Converta para JSON string (mais fácil do que CSV para LLMs entenderem)
produtos_json = df_prompt.to_json(orient="records", force_ascii=False, indent=2)

# Monte o prompt
prompt = f"""
Você é um especialista em categorização de produtos para licitações.

Abaixo estão os dados de alguns produtos:

{produtos_json}

Para cada item, me retorne um JSON contendo:
- categoria_principal
- subcategoria
- marca
- modelo
- especificacoes_tecnicas (inferidas da descrição)
- palavras_chave

Responda apenas com o JSON.
"""

# Chama o modelo Gemini
model = genai.GenerativeModel("gemini-1.5-flash")
response = model.generate_content(prompt)

print(response.text)
