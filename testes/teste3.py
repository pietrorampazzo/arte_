import requests
import csv
import os

def formatar_numprp(modalidade, numero, ano):
    """Formata o número do processo conforme padrão da API"""
    return f"{modalidade}{numero.zfill(6)}{ano}"

def extrair_dados_licitacao(uasg, numprp):
    """Extrai dados de itens de licitação da API do governo"""
    url = f"https://dadosabertos.compras.gov.br/item_licitacao/v1/itens_licitacao.json?uasg={uasg}&numprp={numprp}"
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        dados = response.json()
        return dados.get('_embedded', {}).get('item_licitacao', [])
    
    except requests.exceptions.RequestException as e:
        print(f"Erro na requisição: {e}")
        return None

def salvar_csv(dados, nome_arquivo):
    """Salva os dados em arquivo CSV formatado"""
    if not dados:
        print("Nenhum dado para salvar.")
        return False

    campos = [
        'descricao_item',
        'modalidade',
        'numero_item_licitacao',
        'numero_licitacao',
        'quantidade',
        'valor_estimado'
    ]

    try:
        with open(nome_arquivo, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=campos, delimiter=';')
            writer.writeheader()
            
            for item in dados:
                # Garantir que todos os campos existam
                linha = {campo: item.get(campo, '') for campo in campos}
                writer.writerow(linha)
        
        return True
    
    except IOError as e:
        print(f"Erro ao salvar arquivo: {e}")
        return False

def main():
    # Parâmetros da licitação da UTFPR (exemplo fornecido)
    UASG = "153177"
    MODALIDADE = "05"  # Código para Pregão Eletrônico
    NUMERO_LICITACAO = "90012"
    ANO = "2025"
    
    # Formatar numprp conforme exigido pela API
    numprp = formatar_numprp(MODALIDADE, NUMERO_LICITACAO, ANO)
    
    print("=" * 70)
    print(f"EXTRAÇÃO DE DADOS DE LICITAÇÃO - UTFPR CAMPUS PATO BRANCO")
    print("=" * 70)
    print(f"UASG: {UASG}")
    print(f"Modalidade: {MODALIDADE} (Pregão Eletrônico)")
    print(f"Licitação: {NUMERO_LICITACAO}/{ANO}")
    print(f"Parâmetro numprp formatado: {numprp}")
    print("-" * 70)
    
    # Extrair dados da API
    print("Conectando à API de dados abertos...")
    itens_licitacao = extrair_dados_licitacao(UASG, numprp)
    
    if not itens_licitacao:
        print("Nenhum item encontrado ou erro na conexão.")
        return
    
    print(f"Encontrados {len(itens_licitacao)} itens na licitação.")
    
    # Nome do arquivo de saída
    nome_csv = f"licitacao_{UASG}_{numprp}.csv"
    
    # Salvar resultados
    if salvar_csv(itens_licitacao, nome_csv):
        print("-" * 70)
        print(f"Arquivo CSV gerado com sucesso: {os.path.abspath(nome_csv)}")
        print("=" * 70)
        
        # Mostrar resumo dos dados
        print("\nRESUMO DOS DADOS EXTRAÍDOS:")
        print(f"{'Item':<5} | {'Descrição':<40} | {'Quantidade':>10} | {'Valor Estimado':>14}")
        print("-" * 80)
        
        for item in itens_licitacao[:5]:  # Mostrar até 5 itens como amostra
            valor = f"R$ {float(item.get('valor_estimado', 0)):,.2f}" if item.get('valor_estimado') else "Não informado"
            print(f"{item['numero_item_licitacao']:<5} | {item['descricao_item'][:40]:<40} | {item['quantidade']:>10} | {valor:>14}")

if __name__ == "__main__":
    main()