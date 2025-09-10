"Script 1: Monitoramento de Licitações"

import pandas as pd
import requests
import time
from datetime import datetime, timedelta

# Configurações
CNPJ_ARTE = "05019519000135"
BASE_URL = "https://pncp.gov.br/api/consulta/v1"

MODALIDADES = {
    "Pregão Eletrônico": 6,
    "Dispensa Eletrônica": 8,
    "Concorrência Eletrônica": 4,
    "Concorrência Presencial": 5,
    "Pregão Presencial": 7,
    "Dispensa de Licitação": 8,
    "Inexigibilidade": 9
}

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

def processar_licitacao(uasg, edital, modalidade, data_publicacao):
    codigo_modalidade = MODALIDADES.get(modalidade)
    if not codigo_modalidade:
        return {"Status": "Modalidade não mapeada", "Rank": None}

    data_inicial = (data_publicacao - timedelta(days=30)).strftime("%Y%m%d")
    data_final = (data_publicacao + timedelta(days=30)).strftime("%Y%m%d")

    params = {
        "dataInicial": data_inicial,
        "dataFinal": data_final,
        "codigoModalidadeContratacao": codigo_modalidade,
        "pagina": 1
    }

    dados = consultar_api("contratacoes/publicacao", params)
    if not dados or not dados.get('data'):
        return {"Status": "Não encontrada", "Rank": None}

    for licitacao in dados['data']:
        if (str(licitacao.get('unidadeOrgao', {}).get('codigoUnidade', '')) == str(uasg) and
            (str(licitacao.get('numeroCompra', '')).endswith(edital) or
             str(licitacao.get('processo', '')).endswith(edital))):
            numero_controle = licitacao.get('numeroControlePNCP')
            if not numero_controle:
                continue

            resultados = consultar_api(f"contratacoes/{numero_controle}/resultados", {})
            if not resultados or not resultados.get('data'):
                return {"Status": "Aguardando Disputa", "Rank": None}

            for resultado in resultados['data']:
                participante = resultado.get('participante', {})
                if participante.get('cnpj') == CNPJ_ARTE:
                    classificacao = resultado.get('classificacao')
                    situacao = resultado.get('situacao', '').lower()
                    if 'adjudicado' in situacao or 'homologado' in situacao:
                        return {"Status": "Adjudicada", "Rank": classificacao}
                    elif 'desclassificado' in situacao:
                        return {"Status": "Perdida", "Rank": classificacao}
                    else:
                        return {"Status": f"Rank {classificacao}", "Rank": classificacao}
            return {"Status": "Não participou", "Rank": None}

    return {"Status": "Não encontrada", "Rank": None}

if __name__ == "__main__":
    licitacoes = [
        {"UASG": "153028", "EDITAL": "90022/2025", "Modalidade": "Pregão Eletrônico", "Data Publicação": datetime(2025, 8, 1)},
        {"UASG": "987383", "EDITAL": "90031/2025", "Modalidade": "Pregão Eletrônico", "Data Publicação": datetime(2025, 7, 15)}
    ]

    resultados = []
    for lic in licitacoes:
        res = processar_licitacao(lic['UASG'], lic['EDITAL'], lic['Modalidade'], lic['Data Publicação'])
        resultados.append({
            "UASG": lic['UASG'],
            "EDITAL": lic['EDITAL'],
            "Status": res['Status'],
            "Rank": res['Rank']
        })
        time.sleep(1)

    df = pd.DataFrame(resultados)
    print(df)