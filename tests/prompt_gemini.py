
import google.generativeai as genai
import os 
from dotenv import load_dotenv

load_dotenv() 

api_key = os.getenv("GOOGLE_API_KEY") 
genai.configure(api_key=api_key)

# Escolha o modelo que deseja usar. 'gemini-2.5-flash' é uma ótima opção, rápida e poderosa.
model = genai.GenerativeModel(model_name='gemini-2.5-flash')


# 3. A Função para "Promptar"
def gerar_conteudo():
    """
    Gemini esta comigo?
    """

    prompt = f"""
    
  HELLO WORLD gemini 

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