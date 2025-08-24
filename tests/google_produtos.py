# pesquisa_produtos_revisado.py

import google.generativeai as genai
import os
from dotenv import load_dotenv
import pandas as pd
import json
import time

# --- CONFIGURAÇÃO INICIAL ---
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)

# Modelo de IA
model = genai.GenerativeModel(model_name='gemini-2.5-flash-lite')

# Caminhos dos arquivos
BASE_PRODUTOS = r'sheets/PRODUTOS/produtos_teste.xlsx'
OUTPUT_FILE = r'C:\Users\pietr\OneDrive\.vscode\arte_\sheets\RESULTADO_metadados\produtos_master_pesquisa_tecnico_v3.xlsx'


# Função para gerar conteúdo técnico
def gerar_conteudo(marca, modelo, descricao):
    """
    Gera uma descrição técnica concisa para um produto, focando em especificações confirmadas.
    """
    print(f"🔎 Pesquisando: {marca} {modelo}...")

    prompt = f"""
Você é um especialista em catalogação de produtos musicais e de áudio.
Sua tarefa é criar uma descrição técnica para o produto abaixo, listando APENAS as especificações mais relevantes e confirmadas.
Dê um google no produto usando as informações do produto para analise, priorize o site do fabricante ou de algum revendedor confiavel, para captar as informações reais do produto.
Seu trabalho é fazer uma curadoria digital sobre os produtos, e buscar extidão nas informações.

**Produto para Análise:**
- **Marca:** {marca}
- **Modelo:** {modelo}
- **Descrição Conhecida:** "{descricao}"

**Regras Essenciais:**
1.  **Foco Total em Dados:** Liste apenas especificações técnicas concretas e verificáveis (ex: material, dimensões, tipo de conexão, resposta de frequência, etc.).
2.  **Sem "Encheção":** NÃO inclua opiniões, marketing, frases vagas ou comentários.
3.  **Omissão é Chave:** Se você não encontrar uma informação com alta certeza, **simplesmente não a mencione**. Não escreva "não encontrado", "desconhecido" ou "N/A". A ausência da informação é preferível.
4.  **Formato Limpo:** Apresente as especificações como uma lista de características separadas por vírgulas.
5.  **Relevância:** Forneça apenas especificações que fazem sentido para o tipo de produto. 

**Exemplo (Violão):**
Tampo em Spruce, laterais e fundo em Mogno, escala em Rosewood, 20 trastes, tarraxas cromadas.

**Exemplo (Microfone):**
Tipo Condensador, Padrão Polar Cardioide, Resposta de Frequência 20Hz-20kHz, Conexão XLR.

**Descrição Técnica Concisa:**
"""

    try:
        response = model.generate_content(prompt)
        # Limpa a resposta, removendo markdown e espaços extras.
        cleaned_response = response.text.strip()
        if not cleaned_response or len(cleaned_response) < 10: # Heurística para resposta vazia/inútil
             return "Nenhuma especificação técnica relevante encontrada."
        return cleaned_response
    
    except Exception as e:
        print(f"❌ Erro na chamada da IA: {e}")
        return "Erro ao pesquisar especificações."


# --- EXECUÇÃO ---
if __name__ == "__main__":
    try:
        df = pd.read_excel(BASE_PRODUTOS, engine='openpyxl')
        df['PESQUISA'] = ''

        for index, row in df.iterrows():
            marca = str(row.get('Marca', ''))
            modelo = str(row.get('Modelo', ''))
            descricao = str(row.get('DESCRICAO', ''))

            resultado = gerar_conteudo(marca, modelo, descricao)
            df.at[index, 'PESQUISA'] = resultado

            print(f"✅ Concluído: {marca} {modelo}")
            time.sleep(5)
            print("-" * 50)
        


        df.to_excel(OUTPUT_FILE, index=False, engine='openpyxl')
        print(f"\n🎉 Processo concluído! Arquivo salvo em: {OUTPUT_FILE}")


    except FileNotFoundError:
        print(f"❌ Erro: Arquivo não encontrado → {BASE_PRODUTOS}")
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
