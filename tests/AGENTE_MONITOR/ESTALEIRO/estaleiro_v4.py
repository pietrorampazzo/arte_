import pandas as pd
import requests
import os
from datetime import datetime
import time

# Configurações
CNPJ_ARTE = "05019519000135"  # Substitua pelo CNPJ da A.R.T.E
INPUT_PATH = r"C:\Users\pietr\OneDrive\.vscode\arte_\DOWNLOADS\ORCAMENTOS\master_heavy.xlsx"
OUTPUT_DIR = r"C:\Users\pietr\OneDrive\.vscode\arte_\DOWNLOADS\RESULTADO"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "arte_heavy_Arte.xlsx")

# Mapeamento de modalidades (códigos PNCP)
MODALIDADES = {
    "Pregão Eletrônico": 6,
    "Dispensa Eletrônica": 8,
    "Concorrência": 1,
    "Tomada de Preços": 3,
    "Convite": 5
}

def consultar_api_pncp(uasg, numero_edital, modalidade, data_publicacao):
    """
    Consulta a API do PNCP para obter informações sobre a licitação
    """
    try:
        # Converter data para o formato AAAAMMDD
        data_inicial = data_publicacao.strftime("%Y%m%d")
        data_final = (data_publicacao + pd.DateOffset(days=30)).strftime("%Y%m%d")
        
        # Construir URL da API
        url = f"https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
        params = {
            "dataInicial": data_inicial,
            "dataFinal": data_final,
            "codigoModalidadeContratacao": MODALIDADES.get(modalidade, 6),
            "pagina": 1
        }
        
        # Fazer requisição
        headers = {"accept": "application/json"}
        response = requests.get(url, params=params, headers=headers, timeout=30)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Erro na API: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"Erro ao consultar API: {e}")
        return None

def processar_resultados(dados_api, uasg, numero_edital, item):
    """
    Processa os resultados da API para determinar o status da A.R.T.E.
    """
    if not dados_api or "data" not in dados_api or not dados_api["data"]:
        return "Aguardando Disputa", None
    
    # Procurar pela licitação específica
    for licitacao in dados_api["data"]:
        if (str(licitacao.get("uasg", "")) == str(uasg) and 
            str(licitacao.get("numeroCompra", "")).endswith(str(numero_edital))):
            
            # Obter número de controle PNCP
            numero_controle = licitacao.get("numeroControlePNCP")
            if not numero_controle:
                continue
            
            # Consultar resultados específicos
            try:
                url_resultados = f"https://pncp.gov.br/api/consulta/v1/contratacoes/{numero_controle}/resultados"
                response = requests.get(url_resultados, timeout=30)
                
                if response.status_code == 200:
                    resultados = response.json()
                    return analisar_resultados(resultados, item)
                else:
                    return "Aguardando Disputa", None
                    
            except Exception as e:
                print(f"Erro ao consultar resultados: {e}")
                return "Erro na Consulta", None
    
    return "Aguardando Disputa", None

def analisar_resultados(resultados, item_numero):
    """
    Analisa os resultados para determinar a posição da A.R.T.E.
    """
    for resultado in resultados:
        # Verificar se é o item correto
        item_resultado = resultado.get("numeroItem", "")
        if str(item_resultado) != str(item_numero):
            continue
        
        # Verificar situação da A.R.T.E.
        participante = resultado.get("participante", {})
        cnpj = participante.get("cnpj", "")
        
        if cnpj == CNPJ_ARTE:
            situacao = resultado.get("situacao", "").lower()
            classificacao = resultado.get("classificacao")
            
            if "adjudicado" in situacao or "homologado" in situacao:
                return "Adjudicada", classificacao
            elif "desclassificado" in situacao:
                return "Perdida", classificacao
            else:
                return f"Rank {classificacao}", classificacao
    
    return "Perdida", None

def main():
    # Carregar dados da planilha
    try:
        df = pd.read_excel(INPUT_PATH)
        print(f"Carregadas {len(df)} licitações para monitoramento")
    except Exception as e:
        print(f"Erro ao carregar planilha: {e}")
        return
    
    resultados = []
    
    for index, row in df.iterrows():
        uasg = row.get("UASG", "")
        edital = row.get("EDITAL", "")
        item = row.get("Item", "")
        modalidade = row.get("Modalidade", "Pregão Eletrônico")
        data_publicacao = row.get("Data Publicação", datetime.now())
        
        print(f"Processando: UASG {uasg}, Edital {edital}, Item {item}")
        
        # Consultar API PNCP
        dados_api = consultar_api_pncp(uasg, edital, modalidade, data_publicacao)
        
        # Processar resultados
        status, rank = processar_resultados(dados_api, uasg, edital, item)
        
        # Adicionar aos resultados
        resultados.append({
            "UASG": uasg,
            "EDITAL": edital,
            "Item": item,
            "Status": status,
            "Rank Nº": rank
        })
        
        # Esperar para não sobrecarregar a API
        time.sleep(1)
    
    # Criar DataFrame com resultados
    df_resultados = pd.DataFrame(resultados)
    
    # Salvar resultados
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    df_resultados.to_excel(OUTPUT_FILE, index=False)
    print(f"Resultados salvos em: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()