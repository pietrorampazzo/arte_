# 1. Importar a biblioteca necessária
import google.generativeai as genai
import os # Usado para pegar a chave da API do ambiente
from dotenv import load_dotenv

# --- CONFIGURAÇÃO INICIAL ---
# Chama a função para carregar as variáveis do arquivo .env
load_dotenv() 

# É fundamental configurar sua chave de API. 
# É uma boa prática guardá-la como uma variável de ambiente.
# Substitua "SUA_API_KEY" pela sua chave real se não for usar variáveis de ambiente.
api_key = os.getenv("GOOGLE_API_KEY") 
genai.configure(api_key=api_key)

# 2. Inicializar o Modelo
# Escolha o modelo que deseja usar. 'gemini-1.5-flash' é uma ótima opção, rápida e poderosa.
model = genai.GenerativeModel(model_name='gemini-2.5-flash')

BASE_PRODUTOS = r'C:\Users\pietr\OneDrive\.vscode\arte_\sheets\PRODUTOS\base_consolidada.xlsx'

# 3. A Função para "Promptar"
def gerar_conteudo():
    """
    Esta função cria um prompt dinâmico e pede ao modelo para gerar conteúdo.
    """

    prompt = f"""

    Faça uma pesquisa no Google ...

    """

    # 5. Enviando o Prompt e Recebendo a Resposta
    try:
        # A chamada principal que envia seu prompt para a API do Gemini
        response = model.generate_content(prompt)
        
        # A resposta da IA está no atributo .text
        return response.text
        
    except Exception as e:
        # É importante tratar possíveis erros (ex: problema de conexão, API key inválida)
        print(f"❌ Ocorreu um erro durante a chamada para a IA: {e}")
        return None

# --- EXECUÇÃO DO CÓDIGO ---
# Exemplo de como usar a função
if __name__ == "__main__":
    # Definimos as variáveis que queremos inserir no prompt

    
    # Chamamos nossa função com essas variáveis
    resultado_da_ia = gerar_conteudo()
    
    # Verificamos se obtivemos um resultado e o imprimimos
    if resultado_da_ia:
        print("\n--- RESPOSTA DA IA ---")
        print(resultado_da_ia)
        print("--------------------")