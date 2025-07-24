import requests
import csv
from datetime import datetime

def formatar_numprp(modalidade, numero, ano):
    """Garante 6 dígitos no número da licitação"""
    numero_formatado = str(numero).zfill(6)  # Preenche com zeros à esquerda
    return f"{modalidade}{numero_formatado}{ano}"

def verificar_metadados_licitacao(uasg, numero, ano):
    """Busca metadados para validar a existência da licitação"""
    url_metadados = f"https://dadosabertos.compras.gov.br/licitacoes/v1/licitacoes.json?uasg={uasg}&numero={numero}&ano={ano}"
    
    try:
        response = requests.get(url_metadados, headers={'Accept': 'application/json'})
        if response.status_code == 200:
            dados = response.json()
            if dados.get("_embedded", {}).get("licitacoes"):
                # Verifica se encontrou alguma licitação
                licitacao = dados["_embedded"]["licitacoes"][0]
                print(f"Licitação encontrada nos metadados: {licitacao['objeto']}")
                print(f"Data abertura: {licitacao['data_abertura_proposta']}")
                return licitacao['numero_processo']  # Retorna numprp real
        return None
    except Exception as e:
        print(f"Erro ao buscar metadados: {str(e)}")
        return None

def extrair_dados_licitacao(uasg, modalidade, numero, ano):
    """Extrai dados de itens de licitação com tratamento robusto"""
    # 1. Formatar numprp corretamente
    numprp = formatar_numprp(modalidade, numero, ano)
    print(f"Parâmetro numprp gerado: {numprp}")
    
    # 2. Verificar se a licitação já está disponível
    data_hoje = datetime.now().strftime("%Y-%m-%d")
    data_licitacao = f"{ano}-07-28"  # Data conhecida da licitação
    
    if data_hoje < data_licitacao:
        print(f"Aviso: Licitação programada para {data_licitacao} (hoje é {data_hoje})")
        print("Os dados podem não estar disponíveis até a data de abertura")
    
    # 3. Tentar endpoint principal
    url_principal = f"https://dadosabertos.compras.gov.br/item_licitacao/v1/itens_licitacao.json?uasg={uasg}&numprp={numprp}"
    print(f"URL principal: {url_principal}")
    
    try:
        # Adicionar headers para garantir resposta JSON
        headers = {'Accept': 'application/json'}
        response = requests.get(url_principal, headers=headers, timeout=30)
        
        # 4. Se 404, buscar metadados alternativos
        if response.status_code == 404:
            print("Erro 404 no endpoint principal. Buscando metadados alternativos...")
            numprp_alternativo = verificar_metadados_licitacao(uasg, numero, ano)
            
            if numprp_alternativo:
                print(f"Tentando numprp alternativo: {numprp_alternativo}")
                url_alternativa = f"https://dadosabertos.compras.gov.br/item_licitacao/v1/itens_licitacao.json?uasg={uasg}&numprp={numprp_alternativo}"
                response = requests.get(url_alternativa, headers=headers, timeout=30)
        
        # 5. Tratar resposta
        response.raise_for_status()
        dados = response.json()
        
        # Verificar estrutura da resposta
        if '_embedded' in dados and 'item_licitacao' in dados['_embedded']:
            return dados['_embedded']['item_licitacao']
        else:
            print("Resposta da API não contém itens de licitação")
            print(f"Estrutura da resposta: {list(dados.keys())}")
            return []
    
    except requests.exceptions.HTTPError as e:
        print(f"Erro HTTP {e.response.status_code}: {e.response.text}")
        
        # Tentar extrair detalhes do erro
        try:
            error_details = e.response.json()
            if 'title' in error_details:
                print(f"Detalhes do erro: {error_details['title']}")
                if 'detail' in error_details:
                    print(f"Mais informações: {error_details['detail']}")
        except:
            pass
        
        return None
    
    except requests.exceptions.RequestException as e:
        print(f"Falha na conexão: {str(e)}")
        return None

def main():
    # Dados da licitação da UTFPR
    UASG = "153177"
    MODALIDADE = "05"
    NUMERO_LICITACAO = "90012"
    ANO = "2025"
    
    print("\n" + "="*70)
    print("SISTEMA DE EXTRAÇÃO DE DADOS DE LICITAÇÕES - COMPRAS.GOV.BR")
    print("="*70)
    print(f"UASG: {UASG}")
    print(f"Modalidade: {MODALIDADE} (Pregão Eletrônico)")
    print(f"Licitação: {NUMERO_LICITACAO}/{ANO}")
    print(f"Data atual: {datetime.now().strftime('%d/%m/%Y')}")
    print("-"*70)
    
    # Extrair dados
    itens = extrair_dados_licitacao(UASG, MODALIDADE, NUMERO_LICITACAO, ANO)
    
    if itens is None:
        print("\nFalha na obtenção dos dados.")
    elif len(itens) == 0:
        print("\nNenhum item encontrado para esta licitação.")
    else:
        print(f"\nTotal de itens extraídos: {len(itens)}")
        
        # Gerar nome do arquivo CSV
        nome_csv = f"licitacao_{UASG}_{NUMERO_LICITACAO}_{ANO}.csv"
        
        # Salvar em CSV
        try:
            with open(nome_csv, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'descricao_item',
                    'modalidade',
                    'numero_item_licitacao',
                    'numero_licitacao',
                    'quantidade',
                    'valor_estimado'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';')
                writer.writeheader()
                
                for item in itens:
                    writer.writerow(item)
            
            print(f"Arquivo CSV salvo: {nome_csv}")
            print("Primeiros itens:")
            for i, item in enumerate(itens[:3], 1):
                print(f"{i}. {item['descricao_item'][:50]}... (Qtd: {item['quantidade']}, Valor: {item.get('valor_estimado', 'N/A')})")
        
        except Exception as e:
            print(f"Erro ao salvar CSV: {str(e)}")
    
    print("\n" + "="*70)
    print("Recomendações finais:")
    print("- Verifique a data de publicação da licitação")
    print("- Consulte a API diretamente: https://dadosabertos.compras.gov.br/swagger-ui/index.html")
    print("- Entre em contato com suporte: dadosabertos@compras.gov.br")

if __name__ == "__main__":
    main()