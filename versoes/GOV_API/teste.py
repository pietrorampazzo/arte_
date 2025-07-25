import requests
from datetime import datetime
import time

def formatar_data(data_iso):
    try:
        dt_obj = datetime.fromisoformat(data_iso.replace('Z', '+00:00'))
        return dt_obj.strftime("%d/%m/%Y às %H:%M Hs")
    except:
        return "Data não disponível"

def obter_dados_api(url, params=None):
    try:
        headers = {"Accept": "application/json"}
        resposta = requests.get(url, headers=headers, params=params, timeout=15)
        resposta.raise_for_status()
        
        if "X-RateLimit-Remaining" in resposta.headers and int(resposta.headers["X-RateLimit-Remaining"]) < 5:
            time.sleep(1)
            
        return resposta.json()
    except requests.exceptions.HTTPError as e:
        print(f"Erro na requisição: {e.response.status_code}")
        if e.response.text:
            print(f"Detalhes: {e.response.text[:200]}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Falha de conexão: {str(e)}")
        return None

def buscar_licitacao_por_uasg_numero(uasg, numero_pregao, ano):
    url = "https://compras.dados.gov.br/pregoes/v1/pregoes.json"
    params = {
        "uasg": uasg,
        "numero": numero_pregao,
        "ano": ano
    }
    return obter_dados_api(url, params)

def obter_itens_licitacao(id_licitacao):
    url = f"https://compras.dados.gov.br/pregoes/v1/itens_pregao/{id_licitacao}.json"
    resposta = obter_dados_api(url)
    
    if not resposta:
        return None
    
    itens = resposta.get("_embedded", {}).get("item", [])
    
    # Tratar paginação
    while "_links" in resposta and "next" in resposta["_links"]:
        proxima_url = resposta["_links"]["next"]["href"]
        resposta = obter_dados_api(proxima_url)
        if resposta and "_embedded" in resposta:
            itens.extend(resposta["_embedded"].get("item", []))
    
    return itens

# Parâmetros da licitação
uasg = 153177
numero_pregao = "90012"
ano = 2025

# Execução principal
if __name__ == "__main__":
    print("\n" + "="*80)
    print("UNIVERSIDADE TECNOLOGICA FEDERAL DO PARANA")
    print("UTFPR - CAMPUS SUDOESTE PATO BRANCO")
    print("="*80)
    
    # Etapa 1: Buscar licitação
    resultado_busca = buscar_licitacao_por_uasg_numero(uasg, numero_pregao, ano)
    
    if not resultado_busca:
        print("\n⚠️ Erro ao acessar a API do Compras.gov.br")
        exit()
    
    if "_embedded" not in resultado_busca or "pregoes" not in resultado_busca["_embedded"]:
        print("\n⚠️ Licitação não encontrada na base de dados")
        print("Motivos possíveis:")
        print(f"- Licitação {numero_pregao}/{ano} do UASG {uasg} ainda não foi publicada")
        print("- A API pode estar temporariamente indisponível")
        print("- Formato diferente de numeração (verificar se é SRP)")
        exit()
    
    licitacoes = resultado_busca["_embedded"]["pregoes"]
    
    if not licitacoes:
        print("\n🚨 Nenhum pregão encontrado com os parâmetros fornecidos")
        exit()
    
    # Selecionar primeira licitação encontrada
    licitacao = licitacoes[0]
    
    # Extrair ID diretamente do objeto
    if "id" in licitacao:
        id_licitacao = licitacao["id"]
        print(f"\n✅ Licitação encontrada | ID: {id_licitacao}")
    else:
        print("\n⚠️ Estrutura de resposta inesperada: campo 'id' não encontrado")
        print("Dados recebidos:")
        print(licitacao)
        exit()
    
    # Etapa 2: Obter itens
    itens = obter_itens_licitacao(id_licitacao)
    
    if not itens:
        print("\n⚠️ Não foram encontrados itens para esta licitação")
        exit()
    
    # Processar informações básicas
    tem_beneficio_me = any(
        item.get("tipo_beneficio") in ["MICROEMPRESA", "EMPRESA_DE_PEQUENO_PORTE"] 
        for item in itens
    )
    
    # Exibir informações principais
    print(f"\nUASG: {uasg}")
    print(f"Pregão Eletrônico SRP {numero_pregao}/{ano}")
    print(f"Possui benefícios ME/EPP: {'Sim' if tem_beneficio_me else 'Não'}")
    
    # Obter data de entrega
    data_entrega = "Data não disponível"
    for campo in ["data_abertura", "data_abertura_proposta", "data_entrega_proposta"]:
        if campo in licitacao:
            data_entrega = formatar_data(licitacao[campo])
            break
    
    print(f"Entrega até: {data_entrega}")
    
    print("\n" + "-"*80)
    print(f"ITENS DA LICITAÇÃO ({len(itens)} encontrados):")
    print("-"*80)
    
    # Exibir itens simplificados
    for item in itens:
        print(f"\n▶ Item {item.get('numero')}: {item.get('descricao')}")
        print(f"  Quantidade: {item.get('quantidade')} {item.get('unidade', 'UN')}")
        print(f"  Valor estimado: R$ {item.get('valor_estimado', 0):.2f}")
        print(f"  Benefícios: {item.get('tipo_beneficio', 'Nenhum')}")
    
    print("\n" + "="*80)
    print(f"📋 Resumo: {len(itens)} itens listados")
    print(f"🔗 Link oficial: https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/public/compras/acompanhamento-compra?compra={id_licitacao}")
    print("="*80)