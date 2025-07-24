import requests
from datetime import datetime
import time
import json
import re

def formatar_data(data_iso):
    try:
        dt_obj = datetime.fromisoformat(data_iso.replace('Z', '+00:00'))
        return dt_obj.strftime("%d/%m/%Y às %H:%M Hs")
    except:
        return "Data não disponível"

def formatar_resposta(dados):
    """Formata os dados da resposta para exibição organizada"""
    if not dados:
        return "Nenhum dado recebido"
    
    resultado = ""
    for chave, valor in dados.items():
        if chave == '_links':
            resultado += "\n🔗 Links:\n"
            for link_nome, link_info in valor.items():
                resultado += f"  • {link_nome}: {link_info.get('href', '')} - {link_info.get('title', '')}\n"
        else:
            # Trata campos de data especificamente
            if 'data' in chave.lower() or 'dt' in chave.lower():
                valor_formatado = formatar_data(valor) if valor else "Não disponível"
                resultado += f"📅 {chave}: {valor_formatado}\n"
            elif 'valor' in chave.lower():
                try:
                    valor_float = float(valor) if valor else 0
                    valor_formatado = f"R$ {valor_float:,.2f}"
                    resultado += f"💰 {chave}: {valor_formatado}\n"
                except:
                    resultado += f"💰 {chave}: {valor}\n"
            else:
                valor_formatado = valor if valor not in [None, ''] else "Não disponível"
                # Limita descrições muito longas
                if isinstance(valor_formatado, str) and len(valor_formatado) > 150:
                    valor_formatado = valor_formatado[:150] + "..."
                resultado += f"• {chave}: {valor_formatado}\n"
    
    return resultado

def obter_dados_api(url, params=None):
    try:
        headers = {"Accept": "application/json"}
        resposta = requests.get(url, headers=headers, params=params, timeout=45)
        resposta.raise_for_status()
        
        if "X-RateLimit-Remaining" in resposta.headers and int(resposta.headers["X-RateLimit-Remaining"]) < 5:
            time.sleep(1)
            
        return resposta.json()
    except requests.exceptions.HTTPError as e:
        print(f"\n⚠️ Erro na requisição ({url}): {e.response.status_code}")
        if e.response.text:
            print(f"Detalhes: {e.response.text[:200]}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"\n⚠️ Falha de conexão: {str(e)}")
        return None

def buscar_licitacao_por_uasg_numero(uasg, numero_pregao, ano):
    url = "https://compras.dados.gov.br/pregoes/v1/pregoes.json"
    params = {
        "uasg": uasg,
        "numero": numero_pregao,
        "ano": ano
    }
    return obter_dados_api(url, params)

def extrair_id_do_link(link):
    """Extrai o ID completo do link da licitação"""
    if not link:
        return None
    
    # Tenta extrair do formato comum
    padrao1 = r"pregoes/id/pregao/(\d+)"
    correspondencia1 = re.search(padrao1, link)
    if correspondencia1:
        return correspondencia1.group(1)
    
    # Tenta outro formato alternativo
    padrao2 = r"pregoes/v1/pregoes/(\d+)\.json"
    correspondencia2 = re.search(padrao2, link)
    if correspondencia2:
        return correspondencia2.group(1)
    
    return None

def obter_itens_licitacao(licitacao):
    """Obtém itens usando a melhor estratégia disponível"""
    itens = []
    
    # Estratégia 1: Usar o link de itens direto da resposta
    if '_links' in licitacao and 'itens' in licitacao['_links']:
        url_itens = licitacao['_links']['itens']['href']
        if not url_itens.startswith('http'):
            url_itens = f"https://compras.dados.gov.br{url_itens}"
        
        resposta = obter_dados_api(url_itens)
        if resposta:
            itens = resposta.get("_embedded", {}).get("item", [])
    
    # Estratégia 2: Usar endpoint padrão se ID disponível
    if not itens and 'id' in licitacao:
        url = f"https://compras.dados.gov.br/pregoes/v1/itens_pregao/{licitacao['id']}.json"
        resposta = obter_dados_api(url)
        if resposta:
            itens = resposta.get("_embedded", {}).get("item", [])
    
    # Estratégia 3: Tentar extrair ID do link
    if not itens and '_links' in licitacao and 'self' in licitacao['_links']:
        link_self = licitacao['_links']['self']['href']
        id_licitacao = extrair_id_do_link(link_self)
        if id_licitacao:
            url = f"https://compras.dados.gov.br/pregoes/v1/itens_pregao/{id_licitacao}.json"
            resposta = obter_dados_api(url)
            if resposta:
                itens = resposta.get("_embedded", {}).get("item", [])
    
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
    
    # Exibir informações básicas da licitação
    print("\nℹ️ DADOS DA LICITAÇÃO ENCONTRADA:")
    print("="*60)
    print(formatar_resposta(licitacao))
    print("="*60)
    
    # Etapa 2: Obter itens usando múltiplas estratégias
    itens = obter_itens_licitacao(licitacao)
    
    if not itens:
        print("\n⚠️ Não foram encontrados itens para esta licitação")
        print("Possíveis causas:")
        print("- Licitação muito antiga (dados não disponíveis na API)")
        print("- Erro temporário no servidor de itens")
        print("- Formato incompatível com endpoints atuais")
        
        # Tentar obter dados alternativos
        print("\n💡 Alternativas disponíveis:")
        if '_links' in licitacao and 'self' in licitacao['_links']:
            link_self = licitacao['_links']['self']['href']
            if not link_self.startswith('http'):
                link_self = f"https://compras.dados.gov.br{link_self}"
            print(f"- Acesse detalhes completos: {link_self}")
        
        if 'co_processo' in licitacao:
            print(f"- Número do processo: {licitacao['co_processo']}")
        
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
    for campo in ["data_abertura", "data_abertura_proposta", "data_entrega_proposta", "dtFimProposta"]:
        if campo in licitacao:
            data_entrega = formatar_data(licitacao[campo])
            break
    
    print(f"Entrega até: {data_entrega}")
    
    print("\n" + "-"*80)
    print(f"📋 ITENS DA LICITAÇÃO ({len(itens)} encontrados):")
    print("-"*80)
    
    # Exibir itens simplificados
    for item in itens:
        print(f"\n▶ Item {item.get('numero')}: {item.get('descricao')}")
        print(f"  Quantidade: {item.get('quantidade')} {item.get('unidade', 'UN')}")
        
        # Formatar valor estimado
        valor_estimado = item.get('valor_estimado', 0)
        if isinstance(valor_estimado, str):
            try:
                valor_estimado = float(valor_estimado)
            except:
                valor_estimado = 0
        print(f"  Valor estimado: R$ {valor_estimado:,.2f}")
        
        print(f"  Benefícios: {item.get('tipo_beneficio', 'Nenhum')}")
    
    print("\n" + "="*80)
    print(f"🔗 Link oficial: https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/public/compras/acompanhamento-compra?compra={licitacao.get('id', '')}")
    print("="*80)