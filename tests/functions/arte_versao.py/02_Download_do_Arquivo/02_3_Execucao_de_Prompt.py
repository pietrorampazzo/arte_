# Estratégia: Executa prompts genéricos para análise inicial.
# Funcionamento: Usa OpenAI para processar dados estruturados.
# Integração: Prepara dados para prompts específicos (GPT, Manus, etc.).

import openai
from utils.config import load_config

def execute_prompt(data):
    config = load_config()
    openai.api_key = config['OPENAI_API_KEY']
    prompt = f"Analyze the following bid data: {data.to_json()}"
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=1024
    )
    return response.choices[0].text.strip()