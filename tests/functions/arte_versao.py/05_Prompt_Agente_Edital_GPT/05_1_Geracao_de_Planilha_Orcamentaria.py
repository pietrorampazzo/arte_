# Estratégia: Extrai dados de editais com GPT.
# Funcionamento: Usa OpenAI para estruturar dados em planilhas.
# Integração: Fornece dados para matching e orçamentos.

import openai
from utils.config import load_config

def generate_budget_spreadsheet(edital_text):
    config = load_config()
    openai.api_key = config['OPENAI_API_KEY']
    prompt = f"Extract items, quantities, and values from: {edital_text}"
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=1024
    )
    return response.choices[0].text.strip()