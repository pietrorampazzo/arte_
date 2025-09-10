import pandas as pd
import requests
import time
from datetime import datetime, timedelta

# Configurações
CNPJ_ARTE = "05019519000135"  # Substituir pelo CNPJ real
BASE_URL = "https://pncp.gov.br/api/consulta/v1"

# Mapeamento de modalidades (conforme tabela 5.2 do manual)
MODALIDADES = {
    "Pregão Eletrônico": 6,
    "Dispensa Eletrônica": 8,
    "Concorrência Eletrônica": 4,
    "Concorrência Presencial": 5,
    "Pregão Presencial": 7,
    "Dispensa de Licitação": 8,
    "Inexigibilidade": 9
}

# Mapeamento de situações (conforme tabelas 5.5, 5.6, 5.8)
SITUACOES = {
    1: "Divulgada no PNCP",
    2: "Revogada",
    3: "Anulada",
    4: "Suspensa",
    5: "Em Andamento",
    6: "Homologado",
    7: "Anulado/Revogado/Cancelado",
    8: "Deserto",
    9: "Fracassado",
    10: "Informado",
    11: "Cancelado"
}

def consultar_api(endpoint, params, max_tentativas=3):
    """Função robusta para consultar a API PNCP com tratamento de erros"""
    for tentativa in range(max_tentativas):
        try:
            response = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 204:
                return {"data": [], "totalRegistros": 0}
            else:
                print(f"Erro HTTP {response.status_code} na tentativa {tentativa + 1}")
                time.sleep(2)  # Espera antes de tentar novamente
                
        except requests.exceptions.RequestException as e:
            print(f"Erro de conexão na tentativa {tentativa + 1}: {str(e)}")
            time.sleep(5)  # Espera mais tempo para erros de conexão
    
    return None

def encontrar_licitacao_por_edital(data_inicial, data_final, codigo_modalidade, numero_edital):
    """Encontra uma licitação específica pelo número do edital"""
    params = {
        "dataInicial": data_inicial,
        "dataFinal": data_final,
        "codigoModalidadeContratacao": codigo_modalidade,
        "pagina": 1,
        "tamanhoPagina": 50
    }
    
    pagina = 1
    while True:
        dados = consultar_api("contratacoes/publicacao", params)
        
        if not dados or not dados.get('data'):
            return None
            
        for licitacao in dados['data']:
            if (licitacao.get('numeroCompra') == numero_edital or 
                str(licitacao.get('processo', '')).endswith(numero_edital)):
                return licitacao
                
        # Verifica se há mais páginas
        if pagina >= dados.get('totalPaginas', 1):
            break
            
        pagina += 1
        params['pagina'] = pagina
        
    return None

def consultar_itens_licitacao(numero_controle_pncp):
    """Consulta os itens de uma licitação específica"""
    return consultar_api(f"contratacoes/{numero_controle_pncp}/itens", {})

def consultar_resultados_licitacao(numero_controle_pncp):
    """Consulta os resultados de uma licitação específica"""
    return consultar_api(f"contratacoes/{numero_controle_pncp}/resultados", {})

def processar_licitacao(uasg, edital, item, modalidade, data_publicacao):
    """Processa uma licitação específica e retorna o status"""
    # Converter modalidade para código
    codigo_modalidade = MODALIDADES.get(modalidade)
    if not codigo_modalidade:
        return {"Status": "Modalidade não mapeada", "Rank": None}
    
    # Calcular intervalo de datas (30 dias antes e depois)
    data_inicial = (data_publicacao - timedelta(days=30)).strftime("%Y%m%d")
    data_final = (data_publicacao + timedelta(days=30)).strftime("%Y%m%d")
    
    # Encontrar a licitação
    licitacao = encontrar_licitacao_por_edital(data_inicial, data_final, codigo_modalidade, edital)
    
    if not licitacao:
        return {"Status": "Não encontrada", "Rank": None}
    
    numero_controle_pncp = licitacao.get('numeroControlePNCP')
    if not numero_controle_pncp:
        return {"Status": "Sem numeroControlePNCP", "Rank": None}
    
    # Verificar situação da licitação
    situacao_id = licitacao.get('situacaoCompraId')
    if situacao_id in [2, 3, 4]:  # Revogada, Anulada, Suspensa
        return {"Status": "Licitação " + SITUACOES.get(situacao_id, "Cancelada"), "Rank": None}
    
    # Consultar resultados
    resultados = consultar_resultados_licitacao(numero_controle_pncp)
    
    if not resultados or not resultados.get('data'):
        # Verificar se o período de propostas está aberto
        data_encerramento = licitacao.get('dataEncerramentoProposta')
        if data_encerramento and datetime.now() < datetime.fromisoformat(data_encerramento.replace('Z', '+00:00')):
            return {"Status": "Aguardando Disputa", "Rank": None}
        else:
            return {"Status": "Em análise", "Rank": None}
    
    # Procurar pelo item específico
    for resultado in resultados.get('data', []):
        if str(resultado.get('numeroItem')) == str(item):
            # Verificar se a A.R.T.E. está neste item
            participante = resultado.get('participante', {})
            cnpj_part = participante.get('cnpj')
            
            if cnpj_part == CNPJ_ARTE:
                classificacao = resultado.get('classificacao')
                situacao = resultado.get('situacao', '').lower()
                
                if 'adjudicado' in situacao or 'homologado' in situacao:
                    return {"Status": "Adjudicada", "Rank": classificacao}
                elif 'desclassificado' in situacao:
                    return {"Status": "Perdida", "Rank": classificacao}
                else:
                    return {"Status": f"Rank {classificacao}", "Rank": classificacao}
            else:
                # Outro participante ganhou
                return {"Status": "Perdida", "Rank": None}
    
    return {"Status": "Item não encontrado nos resultados", "Rank": None}

# Exemplo de uso
if __name__ == "__main__":
    # Dados de exemplo (substituir pelos dados reais da planilha)
    licitacoes = [
        {"UASG": "153028", "EDITAL": "90022/2025", "Item": "1", "Modalidade": "Pregão Eletrônico", "Data Publicação": datetime(2025, 8, 1)},
        {"UASG": "987383", "EDITAL": "90031/2025", "Item": "1", "Modalidade": "Pregão Eletrônico", "Data Publicação": datetime(2025, 7, 15)}
    ]
    
    resultados = []
    
    for licitacao in licitacoes:
        print(f"Processando: {licitacao['EDITAL']}")
        resultado = processar_licitacao(
            licitacao['UASG'],
            licitacao['EDITAL'],
            licitacao['Item'],
            licitacao['Modalidade'],
            licitacao['Data Publicação']
        )
        
        resultados.append({
            "UASG": licitacao['UASG'],
            "EDITAL": licitacao['EDITAL'],
            "Item": licitacao['Item'],
            "Status": resultado['Status'],
            "Rank Nº": resultado['Rank']
        })
        
        time.sleep(1)  # Respeitar rate limiting da API
    
    # Criar DataFrame com resultados
    df = pd.DataFrame(resultados)
    print(df)