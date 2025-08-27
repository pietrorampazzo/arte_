from groq import Groq
from dotenv import load_dotenv
import os

# Carregue as variáveis de ambiente
load_dotenv()

# Obtenha a chave da API
api_key = os.getenv("QROQ_API_KEY")

if not api_key:
    raise ValueError("Por favor, forneça uma chave API válida nas variáveis de ambiente.")

try:
    # Inicialize o cliente Groq
    client = Groq(api_key=api_key)

    # Defina as mensagens para o chat
    messages = [
        {
            "role": "user",
            "content": "Qual é o raio da Terra?"
        }
    ]

    # Crie a requisição de complemento
    completion = client.chat.completions.create(
        model="mixtral-8x7b-32768",
        messages=messages,
        stream=True
    )

    # Processo cada pedaço da resposta
    for chunk in completion:
        content = chunk.choices[0].delta.content
        if content:
            print(content, end="")
    print()  # Nova linha no final

except Exception as e:
    print(f"Ocorreu um erro: {e}")