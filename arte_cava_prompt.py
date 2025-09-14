import os
import pandas as pd
import google.generativeai as genai
from dotenv import load_dotenv
from io import StringIO
import json

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)
model = genai.GenerativeModel(model_name='gemini-2.5-flash-lite')

def chamar_llm(prompt):
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Erro na chamada da LLM: {e}")
        return None

def processar_pasta(pasta_path):
    xlsx_path = None
    txt_path = None

    # Encontra dinamicamente os arquivos .xlsx e .txt na pasta
    for arquivo in os.listdir(pasta_path):
        if arquivo.endswith('.xlsx') and not arquivo.startswith('~'):
            xlsx_path = os.path.join(pasta_path, arquivo)
        elif arquivo.endswith('.txt') and arquivo != 'resposta_bruta.txt': # Ignora o arquivo de resposta bruta
            txt_path = os.path.join(pasta_path, arquivo)

    # Verifica se ambos os arquivos foram encontrados
    if not xlsx_path:
        print(f"AVISO: Arquivo .xlsx não encontrado em {pasta_path}. Pulando pasta.")
        return
    if not txt_path:
        print(f"AVISO: Arquivo .txt de referência não encontrado em {pasta_path}. Pulando pasta.")
        return

    print(f"Processando: {pasta_path}")
    try:
        # Ler xlsx
        df = pd.read_excel(xlsx_path)

        # Ler txt
        with open(txt_path, 'r', encoding='utf-8') as f:
            texto_pdf = f.read()
    except Exception as e:
        print(f"ERRO ao ler arquivos em {pasta_path}: {e}")
        return

    # Construir prompt
    prompt = f'''
    Sua tarefa é extrair a descrição de referência para cada item de uma tabela, usando um texto de PDF como fonte.

    A tabela de itens original é:
    {df[['Nº', 'DESCRICAO']].to_csv(index=False)}

    O texto de referência do PDF é:
    {texto_pdf}

    Para cada item, encontre sua descrição detalhada no PDF.
    
    Retorne o resultado como um objeto JSON contendo uma única chave "itens". 
    O valor de "itens" deve ser um array de objetos, onde cada objeto representa um item e possui duas chaves: "Nº" (string) e "REFERENCIA" (string).

    O formato de saída DEVE ser um JSON válido, como no exemplo abaixo:
    {{
      "itens": [
        {{
          "Nº": "1",
          "REFERENCIA": "Descrição detalhada do item 1."
        }},
        {{
          "Nº": "2",
          "REFERENCIA": "Descrição do item 2, que pode ter vírgulas e outros caracteres."
        }}
      ]
    }}

    IMPORTANTE: Retorne APENAS o objeto JSON, sem nenhuma explicação, acentos graves de markdown, ou qualquer outro texto antes ou depois.
    '''

    resposta = chamar_llm(prompt)
    if resposta:
        df_referencia = None
        try:
            # Limpa a resposta para remover ```json ... ```
            clean_response = resposta.strip()
            if clean_response.startswith('```json'):
                clean_response = clean_response[7:].strip()
            if clean_response.endswith('```'):
                clean_response = clean_response[:-3].strip()
            
            data = json.loads(clean_response)
            df_referencia = pd.DataFrame(data['itens'])
            print(f"SUCESSO: Resposta da LLM processada como JSON para {pasta_path}.")

        except (json.JSONDecodeError, KeyError) as e:
            print(f"FALHA no parsing de JSON para {pasta_path}: {e}. Tentando fallback com separador.")
            try:
                # Fallback: Tentar ler como CSV com separador |
                df_referencia = pd.read_csv(StringIO(resposta), sep='|', engine='python')
                if 'Nº' not in df_referencia.columns or 'REFERENCIA' not in df_referencia.columns:
                     raise ValueError("Colunas esperadas não encontradas no fallback de CSV.")
                print(f"SUCESSO (Fallback): Resposta da LLM processada como CSV para {pasta_path}.")
            except Exception as fallback_e:
                print(f"FALHA (Fallback): Não foi possível processar a resposta da LLM para {pasta_path}: {fallback_e}")
                with open(os.path.join(pasta_path, 'resposta_bruta.txt'), 'w', encoding='utf-8') as f:
                    f.write(resposta)
                df_referencia = None # Garante que não prossiga com dados ruins

        if df_referencia is not None and not df_referencia.empty:
            try:
                # Garante que a coluna de junção não tenha tipos mistos e seja a mesma (Nº)
                key_col = df.columns[0] # Assume que a primeira coluna é a chave
                df[key_col] = df[key_col].astype(str)
                df_referencia['Nº'] = df_referencia['Nº'].astype(str)
                
                # Junta o DataFrame original com as referências encontradas
                df_merged = pd.merge(df, df_referencia, on='Nº', how='left')

                # Organiza as colunas na ordem desejada
                desired_order = ['Nº', 'DESCRICAO', 'REFERENCIA', 'QTDE', 'VALOR_UNIT', 'VALOR_TOTAL', 'UNID_FORN', 'LOCAL_ENTREGA', 'ARQUIVO']
                
                # Aplica regras para dados ausentes
                if 'ARQUIVO' not in df_merged.columns:
                    df_merged['ARQUIVO'] = os.path.basename(pasta_path)
                else:
                    df_merged['ARQUIVO'].fillna(os.path.basename(pasta_path), inplace=True)

                if 'REFERENCIA' in df_merged.columns:
                    df_merged['REFERENCIA'].fillna('-', inplace=True)
                else:
                    df_merged['REFERENCIA'] = '-'

                existing_cols_in_order = [col for col in desired_order if col in df_merged.columns]
                df_result = df_merged[existing_cols_in_order]
                
                # Salvar novo arquivo com nome baseado na pasta
                nome_da_pasta = os.path.basename(pasta_path)
                novo_nome_arquivo = f"{nome_da_pasta}_master.xlsx"
                output_filename = os.path.join(pasta_path, novo_nome_arquivo)
                df_result.to_excel(output_filename, index=False)
                print(f"SUCESSO: Arquivo final salvo em {output_filename}")
                return # Finaliza o processamento bem sucedido

            except Exception as merge_e:
                print(f"FALHA ao mesclar dados e salvar para {pasta_path}: {merge_e}")
                # Salva a resposta bruta se a mesclagem falhar
                with open(os.path.join(pasta_path, 'resposta_bruta.txt'), 'w', encoding='utf-8') as f:
                    f.write(resposta)

    # Se a resposta da LLM for nula ou o processamento falhar antes de salvar
    # salvamos o arquivo original com defaults.
    print(f"AVISO: Não foi possível obter ou processar a referência da LLM para {pasta_path}. Salvando com dados existentes e defaults.")
    df_merged = df.copy() # Usa o dataframe original
    
    # Aplica regras para dados ausentes
    if 'ARQUIVO' not in df_merged.columns:
        df_merged['ARQUIVO'] = os.path.basename(pasta_path)
    else:
        df_merged['ARQUIVO'].fillna(os.path.basename(pasta_path), inplace=True)

    if 'REFERENCIA' not in df_merged.columns:
        df_merged['REFERENCIA'] = '-'
    else:
        df_merged['REFERENCIA'].fillna('-', inplace=True)

    desired_order = ['Nº', 'DESCRICAO', 'REFERENCIA', 'QTDE', 'VALOR_UNIT', 'VALOR_TOTAL', 'UNID_FORN', 'LOCAL_ENTREGA', 'ARQUIVO']
    existing_cols_in_order = [col for col in desired_order if col in df_merged.columns]
    df_result = df_merged[existing_cols_in_order]
    
    nome_da_pasta = os.path.basename(pasta_path)
    novo_nome_arquivo = f"{nome_da_pasta}_master.xlsx"
    output_filename = os.path.join(pasta_path, novo_nome_arquivo)
    df_result.to_excel(output_filename, index=False)
    print(f"SUCESSO (com dados de fallback): Arquivo salvo em {output_filename}")


def main():
    # O diretório principal agora aponta para a pasta 'EDITAIS'
    diretorio_principal = './EDITAIS'
    if not os.path.isdir(diretorio_principal):
        print(f"ERRO: O diretório '{diretorio_principal}' não foi encontrado.")
        return

    for pasta_edital in os.listdir(diretorio_principal):
        pasta_path = os.path.join(diretorio_principal, pasta_edital)
        if os.path.isdir(pasta_path):
            processar_pasta(pasta_path)

if __name__ == "__main__":
    main()
