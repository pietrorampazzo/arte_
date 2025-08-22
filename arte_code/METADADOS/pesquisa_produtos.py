# 1. Importar as bibliotecas necessárias
import google.generativeai as genai
import os
from dotenv import load_dotenv
import pandas as pd # Para trabalhar com a tabela de dados

# --- CONFIGURAÇÃO INICIAL ---
# Chama a função para carregar as variáveis do arquivo .env
load_dotenv() 

# Configura a chave da API
api_key = os.getenv("GOOGLE_API_KEY") 
genai.configure(api_key=api_key)

# 2. Inicializar o Modelo
# Importante: O Gemini 2.5 flash não existe, o modelo mais próximo é o 1.5. Vamos usar 'gemini-1.5-flash'.
# Para funções de pesquisa, o Gemini 1.5 Pro também é uma excelente escolha.
model = genai.GenerativeModel(model_name='gemini-2.5-flash-lite')

# 3. Caminhos dos arquivos
# Certifique-se de que o caminho está correto para o arquivo de entrada
BASE_PRODUTOS = r'sheets/PRODUTOS/base_produtos_master_500.xlsx'
# Define o caminho do arquivo de saída com a nova coluna
OUTPUT_FILE = r'C:\Users\pietr\OneDrive\.vscode\arte_\sheets\RESULTADO_metadados\prdodutos_master_pesquisa.xlsx'

# 4. A Função para "Promptar"
def gerar_conteudo(marca, modelo, descricao):
    """
    Esta função cria um prompt dinâmico e pede ao modelo para gerar conteúdo.
    """
    print(f"🤖 Pedindo à IA para pesquisar sobre: {modelo} da marca {marca}...")

    prompt = f"""
    Faça uma pesquisa na internet de forma ampla e categórica afim de extrair as principais CARACTERÍSTICAS TÉCNICAS DO PRODUTO: {modelo} da marca: {marca}. 
    Se serve de ajuda, o máximo que sabemos de descrições desse produto hoje é: "{descricao}" (utilize isso como um balizador do seu conhecimento apenas).
    Agora realize a pesquisa e me traga uma descrição completa e detalhada do produto, com suas principais especificações técnicas e funcionalidades.
    """

    # 5. Enviando o Prompt e Recebendo a Resposta
    try:
        # A chamada principal que envia seu prompt para a API do Gemini
        # Aqui, estamos usando o modo de geração de conteúdo para uma resposta mais concisa.
        response = model.generate_content(prompt)
        
        # A resposta da IA está no atributo .text
        return response.text
        
    except Exception as e:
        print(f"❌ Ocorreu um erro durante a chamada para a IA: {e}")
        return "Erro ao obter a descrição."

# --- EXECUÇÃO DO CÓDIGO PRINCIPAL ---
if __name__ == "__main__":
    try:
        # Ler o arquivo Excel usando pandas
        # O motor openpyxl é necessário para ler arquivos .xlsx
        df = pd.read_excel(BASE_PRODUTOS, engine='openpyxl')
        
        # Cria uma nova coluna para armazenar os resultados da pesquisa
        df['PESQUISA'] = ''

        # Percorre cada linha do DataFrame
        for index, row in df.iterrows():
            marca = row['Marca']
            modelo = row['Modelo']
            descricao = row['DESCRICAO']
            
            # Chama a função para gerar o conteúdo com os dados da linha
            resultado_da_ia = gerar_conteudo(marca, modelo, descricao)
            
            # Adiciona o resultado na nova coluna da linha correspondente
            df.loc[index, 'PESQUISA'] = resultado_da_ia
            
            print(f"✅ Pesquisa para '{modelo}' concluída com sucesso!")
            print("-" * 50)

        # Salva o DataFrame atualizado em um novo arquivo Excel
        df.to_excel(OUTPUT_FILE, index=False, engine='openpyxl')
        
        print("\n🎉 Processo concluído! O arquivo com as pesquisas foi salvo em:")
        print(OUTPUT_FILE)
        
    except FileNotFoundError:
        print(f"❌ Erro: O arquivo não foi encontrado no caminho especificado: {BASE_PRODUTOS}")
    except Exception as e:
        print(f"❌ Ocorreu um erro inesperado: {e}")