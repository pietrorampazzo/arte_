"""
Script busca todas as licitações recentes (últimos 30 dias) 
e verifica em quais a A.R.T.E. participou.
"""
import pandas as pd
import requests
import time
from datetime import datetime, timedelta

CNPJ_ARTE = "05019519000135"
BASE_URL = "https://pncp.gov.br/api/consulta/v1"

def consultar_api(endpoint, params, max_tentativas=3):
    for tentativa in range(max_tentativas):
        try:
            response = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=30)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 204:
                return {"data": [], "totalRegistros": 0}
            else:
                print(f"Erro HTTP {response.status_code} na tentativa {tentativa + 1}")
                time.sleep(2)
        except requests.exceptions.RequestException as e:
            print(f"Erro de conexão na tentativa {tentativa + 1}: {str(e)}")
            time.sleep(5)
    return None

def buscar_participacoes():
    data_inicio = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
    data_fim = datetime.now().strftime("%Y%m%d")

    params = {
        "dataInicial": data_inicio,
        "dataFinal": data_fim,
        "pagina": 1,
        "tamanhoPagina": 50
    }

    todas_licitacoes = []
    while True:
        dados = consultar_api("contratacoes/publicacao", params)
        if not dados or not dados.get('data'):
            break
        todas_licitacoes.extend(dados['data'])
        if params['pagina'] >= dados.get('totalPaginas', 1):
            break
        params['pagina'] += 1
        time.sleep(1)

    participacoes = []
    for licitacao in todas_licitacoes:
        numero_controle = licitacao.get('numeroControlePNCP')
        if not numero_controle:
            continue

        resultados = consultar_api(f"contratacoes/{numero_controle}/resultados", {})
        if not resultados or not resultados.get('data'):
            continue

        for resultado in resultados['data']:
            participante = resultado.get('participante', {})
            if participante.get('cnpj') == CNPJ_ARTE:
                participacoes.append({
                    "UASG": licitacao.get('unidadeOrgao', {}).get('codigoUnidade', ''),
                    "Edital": licitacao.get('numeroCompra', ''),
                    "Item": resultado.get('numeroItem', ''),
                    "Situação": resultado.get('situacao', ''),
                    "Classificação": resultado.get('classificacao', ''),
                    "Órgão": licitacao.get('orgaoEntidade', {}).get('razaoSocial', '')
                })

    return participacoes

if __name__ == "__main__":
    participacoes = buscar_participacoes()
    df = pd.DataFrame(participacoes)
    print(df)