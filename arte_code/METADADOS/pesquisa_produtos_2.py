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
BASE_PRODUTOS = r'sheets/PRODUTOS/base_produtos_master_500.xlsx'
OUTPUT_FILE = r'C:\Users\pietr\OneDrive\.vscode\arte_\sheets\RESULTADO_metadados\produtos_master_pesquisa_tecnico.xlsx'


# Função para gerar conteúdo técnico
def gerar_conteudo(marca, modelo, descricao):
    """
    Cria um prompt técnico e solicita ao modelo apenas especificações objetivas.
    """
    print(f"🔎 Pesquisando: {marca} {modelo}...")

    prompt = f"""
Você é um especialista em catalogação técnica de produtos musicais e eletrônicos.

Sua tarefa é retornar EXCLUSIVAMENTE as especificações técnicas confirmadas do produto abaixo:

Marca: {marca}
Modelo: {modelo}
Descrição conhecida: "{descricao}"

Regras:
1. Liste apenas especificações técnicas objetivas (ex: potência RMS, impedância, conexões, dimensões, materiais, número de canais, etc).
2. Não inclua texto narrativo, opinião, marketing ou comentários adicionais.
3. Não invente dados. Se não houver informação confirmada para um campo, responda "NÃO ENCONTRADO".
4. O resultado deve ser entregue em formato JSON, estruturado como:

{{
  "Marca": "{marca}",
  "Modelo": "{modelo}",
  "Especificacoes": {{
    "Categoria": "...",
    "Potencia": "...",
    "Impedancia": "...",
    "Conectores": "...",
    "Dimensoes": "...",
    "Material": "...",
    "Outros": "..."
  }}
}}

Se nenhuma informação técnica confirmada existir, retorne:
{{ "Marca": "{marca}", "Modelo": "{modelo}", "Especificacoes": "NÃO ENCONTRADO" }}
"""

    try:
        response = model.generate_content(prompt)
        cleaned = response.text.strip().replace("```json", "").replace("```", "")
        # Validar JSON
        data = json.loads(cleaned)
        return json.dumps(data, ensure_ascii=False)
    
    except Exception as e:
        print(f"❌ Erro IA: {e}")
        return json.dumps({
            "Marca": marca,
            "Modelo": modelo,
            "Especificacoes": "NÃO ENCONTRADO"
        }, ensure_ascii=False)


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
