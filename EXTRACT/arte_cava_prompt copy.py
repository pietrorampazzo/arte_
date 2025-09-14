import os
import pandas as pd
import google.generativeai as genai
from dotenv import load_dotenv
from io import StringIO

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)
model = genai.GenerativeModel(model_name='gemini-2.5-flash')

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
        elif arquivo.endswith('.txt'):
            txt_path = os.path.join(pasta_path, arquivo)

    # Verifica se ambos os arquivos foram encontrados
    if not xlsx_path:
        print(f"AVISO: Arquivo .xlsx não encontrado em {pasta_path}. Pulando pasta.")
        return
    if not txt_path:
        print(f"AVISO: Arquivo .txt não encontrado em {pasta_path}. Pulando pasta.")
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
    prompt = f"""
    Sua tarefa é extrair a descrição de referência para cada item de uma tabela, usando um texto de PDF como fonte.

    A tabela de itens original é:
    {df.to_csv(index=False)}

    O texto de referência do PDF é:
    {texto_pdf}

    Para cada item, encontre sua descrição detalhada no PDF.
    
    Retorne o resultado usando o caractere PIPE '|' como separador. NÃO use aspas.
    A saída deve ter apenas 2 colunas: 'Nº' e 'REFERENCIA'.

    O formato de saída DEVE ser:
    Nº|REFERENCIA
    1|Descrição detalhada do item 1.
    2|Descrição detalhada do item 2, que pode ter vírgulas, e não causa problema.
    3|Outra descrição.

    IMPORTANTE: Use '|' como separador. Não inclua nenhuma explicação ou formatação extra.
    """

    resposta = chamar_llm(prompt)
    if resposta:
        try:
            # Limpa a resposta para garantir que seja um formato puro
            clean_response = resposta.strip().replace('`', '').replace('csv', '')
            
            # Lê o resultado da LLM usando o separador pipe '|'
            df_referencia = pd.read_csv(StringIO(clean_response), sep='|')

            # Garante que a coluna de junção não tenha tipos mistos e seja a mesma (Nº)
            key_col = df.columns[0]
            df[key_col] = df[key_col].astype(str)
            df_referencia[key_col] = df_referencia[key_col].astype(str)
            
            # Junta o DataFrame original com as referências encontradas
            df_merged = pd.merge(df, df_referencia, on=key_col, how='left')

            # Organiza as colunas na ordem desejada
            desired_order = ['Nº', 'DESCRICAO', 'REFERENCIA', 'QTDE', 'VALOR_UNIT', 'VALOR_TOTAL', 'UNID_FORN', 'LOCAL_ENTREGA', 'ARQUIVO']
            existing_cols_in_order = [col for col in desired_order if col in df_merged.columns]
            df_result = df_merged[existing_cols_in_order]
            
            # Salvar novo arquivo com nome baseado na pasta
            nome_da_pasta = os.path.basename(pasta_path)
            novo_nome_arquivo = f"{nome_da_pasta}_master.xlsx"
            output_filename = os.path.join(pasta_path, novo_nome_arquivo)
            df_result.to_excel(output_filename, index=False)
            print(f"SUCESSO: Arquivo salvo em {output_filename}")
        except Exception as e:
            print(f"FALHA ao processar a resposta da LLM para {pasta_path}: {e}")
            # Opcional: salvar a resposta bruta para depuração
            with open(os.path.join(pasta_path, 'resposta_bruta.txt'), 'w', encoding='utf-8') as f:
                f.write(resposta)
    else:
        print(f"FALHA: Não foi possível obter resposta da LLM para {pasta_path}")

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
