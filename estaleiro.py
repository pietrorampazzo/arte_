import pandas as pd
import requests
import re
import time
from datetime import datetime

# --- Configurações da API ---
BASE_URL_LEGADO = "https://dadosabertos.compras.gov.br/modulo-legado"

# --- Funções de Consulta à API ---

def fetch_data_with_pagination(endpoint, params, max_pages=5):
    """
    Função auxiliar para buscar dados de APIs paginadas.
    Retorna uma lista de resultados.
    """
    all_results = []
    page = 1
    while page <= max_pages:
        current_params = params.copy()
        current_params['pagina'] = page
        try:
            response = requests.get(f"{BASE_URL_LEGADO}/{endpoint}", params=current_params)
            response.raise_for_status()  # Levanta um erro para status HTTP ruins (4xx ou 5xx)
            data = response.json()

            if not data.get('resultado'):
                break # Não há mais resultados

            all_results.extend(data['resultado'])

            if data.get('paginasRestantes', 0) == 0:
                break # Não há mais páginas

            page += 1
            time.sleep(0.5) # Pequeno delay para não sobrecarregar a API

        except requests.exceptions.RequestException as e:
            print(f"Erro ao consultar a API no endpoint {endpoint} (página {page}): {e}")
            break
        except ValueError:
            print(f"Erro ao decodificar JSON da API no endpoint {endpoint} (página {page}). Resposta: {response.text}")
            break
    return all_results

def get_pregao_status(uasg, numero_pregao):
    """
    Consulta o status geral de um pregão.
    """
    params = {
        'co_uasg': uasg,
        'numero': numero_pregao,
        'dt_data_edital_inicial': '2025-01-01', # Amplo range para encontrar o pregão
        'dt_data_edital_final': datetime.now().strftime('%Y-%m-%d')
    }
    
    pregoes = fetch_data_with_pagination('3_consultarPregoes', params)
    
    if pregoes:
        return pregoes[0]
    return None

def get_item_pregao_status(uasg, numero_pregao, numero_item):
    """
    Consulta o status de um item específico dentro de um pregão.
    """
    params = {
        'co_uasg': uasg,
        'numero': numero_pregao,
        'dt_hom_inicial': '2025-01-01', # Amplo range para encontrar o item
        'dt_hom_final': datetime.now().strftime('%Y-%m-%d')
    }
    
    itens = fetch_data_with_pagination('4_consultarItensPregoes', params)

    for item in itens:
        # A API retorna 'numero_licitacao' e 'numero_item_licitacao'
        # 'numero_licitacao' na API é o 'numero' do pregão que passamos.
        # 'numero_item_licitacao' na API é o número do item dentro daquele pregão.
        if str(item.get('numero_licitacao')) == str(numero_pregao) and \
           str(item.get('numero_item_licitacao')) == str(numero_item):
            return item
    return None

# --- Função Principal de Processamento ---

def process_licitacoes_excel(file_path="master.xlsx"):
    try:
        df = pd.read_excel(file_path)
    except FileNotFoundError:
        print(f"Erro: O arquivo '{file_path}' não foi encontrado.")
        return

    # Adicionar/garantir colunas para os novos status
    # Usamos .get() para evitar KeyError se a coluna já existir e não quisermos sobrescrever
    if 'Status do Item' not in df.columns:
        df['Status do Item'] = 'Não Processado'
    if 'Detalhes do Status' not in df.columns:
        df['Detalhes do Status'] = ''
    if 'CNPJ Vencedor' not in df.columns:
        df['CNPJ Vencedor'] = ''
    if 'Nome Vencedor' not in df.columns:
        df['Nome Vencedor'] = ''
    if 'Data Homologação Item' not in df.columns:
        df['Data Homologação Item'] = pd.NaT # Not a Time (para datas)
    if 'Data Encerramento Pregão' not in df.columns:
        df['Data Encerramento Pregão'] = pd.NaT
    if 'Data Resultado Pregão' not in df.columns:
        df['Data Resultado Pregão'] = pd.NaT
    if 'Data Última Consulta' not in df.columns:
        df['Data Última Consulta'] = pd.NaT

    # Expressão regular para extrair UASG e EDITAL do nome do arquivo
    # Ex: U_153409_E_900092025_C_DEPTO_DE_ADMINISTRACAO_DA_UFPE_29-08-2025_08h00m.xlsx
    # Captura o número após 'U_' e o número após 'E_'
    regex_arquivo = r"U_(\d+)_E_(\d+)_" 

    for index, row in df.iterrows():
        arquivo_col = str(row['ARQUIVO']) # Garantir que é string
        numero_item_col = str(row['Nº']) # Garantir que é string

        match_arquivo = re.search(regex_arquivo, arquivo_col)

        if match_arquivo:
            uasg = match_arquivo.group(1)
            numero_pregao = match_arquivo.group(2)
            numero_item = numero_item_col # Usar a coluna 'Nº' diretamente
            
            print(f"\nProcessando linha {index+2}: UASG={uasg}, Pregão={numero_pregao}, Item={numero_item}")

            df.at[index, 'Data Última Consulta'] = datetime.now()

            pregao_data = get_pregao_status(uasg, numero_pregao)
            item_data = get_item_pregao_status(uasg, numero_pregao, numero_item)

            status_item = "Desconhecido"
            detalhes = "Não foi possível determinar o status."
            cnpj_vencedor = ""
            nome_vencedor = ""
            data_homologacao_item = pd.NaT
            data_encerramento_pregao = pd.NaT
            data_resultado_pregao = pd.NaT

            # Processar dados do pregão
            ds_situacao_pregao = "N/A (Pregão não encontrado)"
            if pregao_data:
                ds_situacao_pregao = pregao_data.get('ds_situacao_pregao', 'N/A')
                dt_encerramento = pregao_data.get('dt_encerramento')
                dt_resultado = pregao_data.get('dt_resultado')

                if dt_encerramento:
                    try:
                        data_encerramento_pregao = pd.to_datetime(dt_encerramento)
                    except ValueError:
                        pass
                if dt_resultado:
                    try:
                        data_resultado_pregao = pd.to_datetime(dt_resultado)
                    except ValueError:
                        pass

                detalhes = f"Situação Pregão: {ds_situacao_pregao}. "
                if data_encerramento_pregao is not pd.NaT:
                    detalhes += f"Encerrado em: {data_encerramento_pregao.strftime('%Y-%m-%d')}. "
                if data_resultado_pregao is not pd.NaT:
                    detalhes += f"Resultado em: {data_resultado_pregao.strftime('%Y-%m-%d')}. "
            else:
                detalhes = "Pregão não encontrado na API ou erro na consulta. "

            # Processar dados do item
            if item_data:
                situacao_item_api = item_data.get('situacao_item', 'N/A')
                dt_hom = item_data.get('dt_hom')
                fornecedor_vencedor_api = item_data.get('fornecedor_vencedor', 'N/A')
                cnpj_vencedor_api = item_data.get('cnpj_fornecedor', '')
                cpf_vencedor_api = item_data.get('cpfVencedor', '')

                if dt_hom:
                    try:
                        data_homologacao_item = pd.to_datetime(dt_hom)
                    except ValueError:
                        pass

                detalhes += f"Situação Item: {situacao_item_api}. "
                if data_homologacao_item is not pd.NaT:
                    detalhes += f"Homologado em: {data_homologacao_item.strftime('%Y-%m-%d')}. "
                if fornecedor_vencedor_api != 'N/A':
                    detalhes += f"Vencedor: {fornecedor_vencedor_api}. "
                
                cnpj_vencedor = cnpj_vencedor_api if cnpj_vencedor_api else cpf_vencedor_api
                nome_vencedor = fornecedor_vencedor_api

                # Lógica para determinar o status final
                if "HOMOLOGADO" in situacao_item_api.upper() or (data_homologacao_item is not pd.NaT and data_homologacao_item <= datetime.now()):
                    status_item = "Adjudicada (Homologada)"
                elif "ADJUDICADO" in situacao_item_api.upper():
                    status_item = "Adjudicada"
                elif "FRACASSADO" in situacao_item_api.upper() or "CANCELADO" in situacao_item_api.upper():
                    status_item = "Perdida (Fracassado/Cancelado)"
                elif pregao_data and ("ENCERRADO" in ds_situacao_pregao.upper() or "CONCLUIDO" in ds_situacao_pregao.upper()):
                    # Se o pregão está encerrado mas o item não foi adjudicado/homologado
                    status_item = "Encerrada (Item sem resultado)"
                elif pregao_data and ("ABERTO" in ds_situacao_pregao.upper() or "EM ANDAMENTO" in ds_situacao_pregao.upper()):
                    status_item = "Aguardando Disputa"
                else:
                    status_item = "Status Indefinido (Item encontrado, mas status ambíguo)"
            else:
                detalhes += "Item não encontrado na API ou erro na consulta do item."
                if pregao_data and ("ENCERRADO" in ds_situacao_pregao.upper() or "CONCLUIDO" in ds_situacao_pregao.upper()):
                    status_item = "Encerrada (Item não detalhado na API)"
                elif pregao_data and ("ABERTO" in ds_situacao_pregao.upper() or "EM ANDAMENTO" in ds_situacao_pregao.upper()):
                    status_item = "Aguardando Disputa (Item não detalhado na API)"
                else:
                    status_item = "Erro na Consulta do Item"


            df.at[index, 'Status do Item'] = status_item
            df.at[index, 'Detalhes do Status'] = detalhes.strip()
            df.at[index, 'CNPJ Vencedor'] = cnpj_vencedor
            df.at[index, 'Nome Vencedor'] = nome_vencedor
            df.at[index, 'Data Homologação Item'] = data_homologacao_item
            df.at[index, 'Data Encerramento Pregão'] = data_encerramento_pregao
            df.at[index, 'Data Resultado Pregão'] = data_resultado_pregao

        else:
            df.at[index, 'Status do Item'] = 'Formato de ARQUIVO inválido'
            df.at[index, 'Detalhes do Status'] = 'Não foi possível extrair UASG e EDITAL do nome do arquivo.'
            print(f"\nErro de formato na linha {index+2}: '{arquivo_col}'")

        time.sleep(0.1) # Pequeno delay entre as linhas para não sobrecarregar a API

    # Salvar o DataFrame atualizado em um novo arquivo Excel
    output_file = "master_com_status.xlsx"
    df.to_excel(output_file, index=False)
    print(f"\nProcessamento concluído. Resultados salvos em '{output_file}'")

# --- Execução do Script ---
if __name__ == "__main__":
    process_licitacoes_excel()

