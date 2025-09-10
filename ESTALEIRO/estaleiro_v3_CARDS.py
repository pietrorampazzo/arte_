import pandas as pd
import requests
import time
from datetime import datetime, timedelta
import re

# Configurações
CNPJ_ARTE = "05019519000135"  # Substituir pelo CNPJ real
BASE_URL = "https://pncp.gov.br/api/consulta/v1"

# Mapeamento de modalidades (conforme tabela 5.2 do manual)
MODALIDADES = {
    "Pregão Eletrônico": 6,
    "Dispensa Eletrônica": 8,
    "Concorrência Eletrônica": 4,
    "Dispensa de Licitação": 8,
    "Inexigibilidade": 9
}

def consultar_api(endpoint, params, max_tentativas=3):
    """Função robusta para consultar a API PNCP com tratamento de erros"""
    for tentativa in range(max_tentativas):
        try:
            print(f"Tentativa {tentativa+1}: {endpoint} com parâmetros {params}")
            response = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 204:
                return {"data": [], "totalRegistros": 0}
            elif response.status_code == 400:
                print(f"Erro 400 - Parâmetros inválidos: {params}")
                return None
            else:
                print(f"Erro HTTP {response.status_code} na tentativa {tentativa + 1}")
                time.sleep(2)
                
        except requests.exceptions.RequestException as e:
            print(f"Erro de conexão na tentativa {tentativa + 1}: {str(e)}")
            time.sleep(5)
    
    return None

def extrair_uasg_edital(arquivo_nome):
    """Extrai UASG e número do edital do formato U_XXXXX_E_YYYYY"""
    match = re.match(r"U_(\d+)_E_(\d+)", arquivo_nome)
    if match:
        return match.group(1), match.group(2)
    return None, None

def encontrar_licitacao(uasg, numero_edital):
    """Encontra uma licitação específica pelo UASG e número do edital"""
    # Tentar diferentes modalidades
    for modalidade_nome, codigo_modalidade in MODALIDADES.items():
        print(f"Tentando modalidade: {modalidade_nome} ({codigo_modalidade})")
        
        # Definir período de consulta (últimos 180 dias)
        data_inicial = (datetime.now() - timedelta(days=180)).strftime("%Y%m%d")
        data_final = datetime.now().strftime("%Y%m%d")
        
        params = {
            "dataInicial": data_inicial,
            "dataFinal": data_final,
            "codigoModalidadeContratacao": codigo_modalidade,
            "pagina": 1
        }
        
        dados = consultar_api("contratacoes/publicacao", params)
        
        if dados is None:
            continue
            
        if dados and 'data' in dados:
            for licitacao in dados['data']:
                # Verificar se é a licitação procurada
                codigo_unidade = licitacao.get('unidadeOrgao', {}).get('codigoUnidade', '')
                numero_compra = licitacao.get('numeroCompra', '')
                processo = licitacao.get('processo', '')
                
                # Verificar por UASG e número do edital
                if (str(codigo_unidade) == str(uasg) and 
                    (str(numero_compra).endswith(numero_edital) or 
                     str(processo).endswith(numero_edital))):
                    return licitacao
        
        time.sleep(1)  # Respeitar rate limiting
    
    return None

def consultar_resultados_licitacao(numero_controle_pncp):
    """Consulta os resultados de uma licitação específica"""
    return consultar_api(f"contratacoes/{numero_controle_pncp}/resultados", {})

def processar_licitacao(uasg, edital):
    """Processa uma licitação específica e retorna o status da A.R.T.E."""
    print(f"Processando: UASG {uasg}, Edital {edital}")
    
    # Encontrar a licitação
    licitacao = encontrar_licitacao(uasg, edital)
    
    if not licitacao:
        return {"UASG": uasg, "EDITAL": edital, "Status": "Não encontrada", "Rank": None, "Detalhes": "Licitação não encontrada no PNCP"}
    
    numero_controle_pncp = licitacao.get('numeroControlePNCP')
    if not numero_controle_pncp:
        return {"UASG": uasg, "EDITAL": edital, "Status": "Erro", "Rank": None, "Detalhes": "Licitação sem numeroControlePNCP"}
    
    # Consultar resultados
    resultados = consultar_resultados_licitacao(numero_controle_pncp)
    
    if not resultados or not resultados.get('data'):
        # Verificar se o período de propostas está aberto
        data_encerramento = licitacao.get('dataEncerramentoProposta')
        if data_encerramento:
            try:
                data_encerramento = datetime.fromisoformat(data_encerramento.replace('Z', '+00:00'))
                if datetime.now() < data_encerramento:
                    return {"UASG": uasg, "EDITAL": edital, "Status": "Aguardando Disputa", "Rank": None, "Detalhes": f"Período de propostas aberto até {data_encerramento.strftime('%d/%m/%Y')}"}
            except:
                pass
        
        return {"UASG": uasg, "EDITAL": edital, "Status": "Em análise", "Rank": None, "Detalhes": "Licitação finalizada, aguardando resultados"}
    
    # Verificar se a A.R.T.E. está nos resultados
    for resultado in resultados['data']:
        participante = resultado.get('participante', {})
        cnpj_part = participante.get('cnpj')
        
        if cnpj_part == CNPJ_ARTE:
            classificacao = resultado.get('classificacao')
            situacao = resultado.get('situacao', '').lower()
            numero_item = resultado.get('numeroItem')
            
            if 'adjudicado' in situacao or 'homologado' in situacao:
                status = "Adjudicada"
            elif 'desclassificado' in situacao:
                status = "Perdida"
            else:
                status = f"Rank {classificacao}"
            
            return {
                "UASG": uasg,
                "EDITAL": edital,
                "Item": numero_item,
                "Status": status,
                "Rank": classificacao,
                "Detalhes": f"Item {numero_item} - {situacao}",
                "Valor Unitário": resultado.get('valorUnitario'),
                "Valor Total": resultado.get('valorTotal'),
                "Órgão": licitacao.get('orgaoEntidade', {}).get('razaoSocial', '')
            }
    
    return {"UASG": uasg, "EDITAL": edital, "Status": "Não participou", "Rank": None, "Detalhes": "A.R.T.E. não encontrada nos resultados"}

def main():
    # Dados da planilha TRELLO
    dados_trello = [
        "U_153128_E_900202025", "U_102333_E_900252025", "U_786200_E_900262025",
        "U_987833_E_900312025", "U_158720_E_900892025", "U_160422_E_900052025",
        "U_153177_E_900142025", "U_925438_E_900892025", "U_158132_E_901072025",
        "U_987425_E_900402025", "U_925998_E_901752025", "U_158380_E_900012025",
        "U_153177_E_900122025", "U_153079_E_901642025", "U_929682_E_900032025",
        "U_80009_E_900232025", "U_153010_E_900312025", "U_984165_E_900402025",
        "U_160237_E_900082025", "U_153164_E_900952025", "U_153028_E_900222025",
        "U_980107_E_900262025", "U_927119_E_900042025", "U_153164_E_901082025",
        "U_783810_E_900052025", "U_982837_E_900282025", "U_984865_E_901002025",
        "U_160433_E_900062025", "U_985693_E_900482025"
    ]
    
    resultados = []
    
    # Processar cada item da planilha
    for arquivo in dados_trello:
        if arquivo == 'ARQUIVO':
            continue
            
        uasg, edital = extrair_uasg_edital(arquivo)
        
        if uasg and edital:
            resultado = processar_licitacao(uasg, edital)
            resultados.append(resultado)
            time.sleep(2)  # Respeitar rate limiting da API
        else:
            print(f"Formato inválido: {arquivo}")
    
    # Criar DataFrame com resultados
    if resultados:
        df_resultados = pd.DataFrame(resultados)
        
        # Salvar resultados
        data_hoje = datetime.now().strftime("%Y%m%d_%H%M%S")
        caminho_arquivo = f"C:/Users/pietr/OneDrive/.vscode/arte_/DOWNLOADS/RESULTADO/resultados_trello_{data_hoje}.xlsx"
        
        df_resultados.to_excel(caminho_arquivo, index=False)
        print(f"Resultados salvos em: {caminho_arquivo}")
        
        # Exibir resumo
        print("\n=== RESUMO DOS RESULTADOS ===")
        print(f"Total de licitações processadas: {len(resultados)}")
        
        # Estatísticas
        if 'Status' in df_resultados.columns:
            print("\nDistribuição por status:")
            print(df_resultados['Status'].value_counts())
    else:
        print("Nenhum resultado encontrado.")

if __name__ == "__main__":
    main()