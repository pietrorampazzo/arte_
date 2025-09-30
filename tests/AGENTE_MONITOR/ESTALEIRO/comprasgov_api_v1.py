import requests
import pandas as pd
from datetime import datetime, timedelta

# --- Configurações da API ---
# A URL base para a API de Compras Governamentais
# Conforme os exemplos de cURL e o manual, usa-se https
BASE_URL = "https://dadosabertos.compras.gov.br" 

# --- Funções Auxiliares ---

def fetch_data_with_pagination(endpoint: str, params: dict = None, max_pages: int = None) -> list:
    """
    Função para buscar dados da API de Compras Governamentais com paginação.
    Retorna uma lista de dicionários com os resultados.

    Args:
        endpoint (str): O caminho do módulo e método da API (ex: "modulo-legado/1_consultarLicitacao").
        params (dict, optional): Dicionário de parâmetros de consulta. Defaults to None.
        max_pages (int, optional): Limite de páginas a serem buscadas. Útil para testes. Defaults to None.

    Returns:
        list: Uma lista contendo todos os registros coletados.
    """
    all_results = []
    page = 1
    has_more_pages = True

    while has_more_pages:
        current_params = params.copy() if params else {}
        current_params['pagina'] = page
        # A API permite ajustar o 'tamanhoPagina' (máximo de 500 registros)
        current_params['tamanhoPagina'] = 500 

        full_url = f"{BASE_URL}/{endpoint}"
        print(f"Buscando dados em: {full_url}?{('&'.join(f'{k}={v}' for k, v in current_params.items()))}")

        try:
            response = requests.get(full_url, params=current_params)
            response.raise_for_status() # Levanta um HTTPError para respostas de erro (4xx ou 5xx)
            data = response.json() # Os dados são disponibilizados em JSON

            if "resultado" in data and data["resultado"]:
                all_results.extend(data["resultado"])
                # Continua a buscar se houver 'paginasRestantes' e não tiver atingido o 'max_pages'
                if data.get("paginasRestantes", 0) > 0 and (max_pages is None or page < max_pages):
                    page += 1
                else:
                    has_more_pages = False
            else:
                has_more_pages = False # Não há mais resultados ou a resposta não contém 'resultado'
            
            # Limite opcional para evitar buscas muito longas em desenvolvimento
            if max_pages is not None and page >= max_pages:
                has_more_pages = False

        except requests.exceptions.RequestException as e:
            print(f"Erro de requisição ao acessar a API: {e}")
            break
        except ValueError:
            print(f"Erro ao decodificar JSON. Resposta da API inválida: {response.text}")
            break
        except Exception as e:
            print(f"Ocorreu um erro inesperado: {e}")
            break
    
    print(f"Total de registros obtidos para o endpoint {endpoint}: {len(all_results)}")
    return all_results

# --- Funções para Coleta de Dados de Módulos Específicos ---

def get_licitacoes_legado(data_inicial: str, data_final: str, uasg: int = None, modalidade: int = None) -> list:
    """
    Consulta licitações do Módulo Legado (Lei 8.666/93).
    Os parâmetros 'data_publicacao_inicial' e 'data_publicacao_final' são obrigatórios
    e a consulta é limitada a um período de 365 dias.
    """
    endpoint = "modulo-legado/1_consultarLicitacao"
    params = {
        "data_publicacao_inicial": data_inicial,
        "data_publicacao_final": data_final,
    }
    if uasg:
        params["uasg"] = uasg
    if modalidade:
        params["modalidade"] = modalidade # Ex: 5 para Pregão, conforme indicadores de modalidade
    
    print(f"\n--- Buscando Licitações (Legado) de {data_inicial} a {data_final} ---")
    return fetch_data_with_pagination(endpoint, params)

def get_itens_pregoes_legado(data_homologacao_inicial: str, data_homologacao_final: str, fornecedor_cnpj_cpf: str = None) -> list:
    """
    Consulta itens de pregões do Módulo Legado. Crucial para o ranking.
    Os parâmetros 'dt_hom_inicial' e 'dt_hom_final' (data de homologação) são obrigatórios.
    """
    endpoint = "modulo-legado/4_consultarItensPregoes"
    params = {
        "dt_hom_inicial": data_homologacao_inicial,
        "dt_hom_final": data_homologacao_final,
    }
    # A documentação indica o parâmetro 'fornecedor_vencedor' como Inteiro mas o campo de retorno como Texto.
    # Para o filtro, geralmente se espera o NI (CPF/CNPJ). Se não funcionar, seria necessário filtrar localmente.
    if fornecedor_cnpj_cpf:
        params["fornecedor_vencedor"] = fornecedor_cnpj_cpf # Testar se a API aceita CNPJ/CPF aqui.
    
    print(f"\n--- Buscando Itens de Pregões (Legado) homologados de {data_homologacao_inicial} a {data_homologacao_final} ---")
    return fetch_data_with_pagination(endpoint, params)

def get_resultados_contratacoes_pncp(data_resultado_inicial: str, data_resultado_final: str, ni_fornecedor: str = None) -> list:
    """
    Consulta resultados de itens de contratações PNCP (Lei 14.133/2021).
    Os parâmetros 'dataResultadoPncpInicial' e 'dataResultadoPncpFinal' são obrigatórios.
    Este endpoint é excelente para ranking, pois já possui campos como 'niFornecedor', 'nomeRazaoSocialFornecedor',
    'valorTotalHomologado' e 'quantidadeHomologada'.
    """
    endpoint = "modulo-contratacoes/3_consultarResultadoItensContratacoes_PNCP_14133"
    params = {
        "dataResultadoPncpInicial": data_resultado_inicial,
        "dataResultadoPncpFinal": data_resultado_final,
    }
    if ni_fornecedor:
        params["niFornecedor"] = ni_fornecedor
    
    print(f"\n--- Buscando Resultados de Itens de Contratações PNCP de {data_resultado_inicial} a {data_resultado_final} ---")
    return fetch_data_with_pagination(endpoint, params)


# --- Lógica de Cálculo de Ranking ---

def calculate_ranking(df_results: pd.DataFrame, company_cnpj: str) -> pd.DataFrame:
    """
    Calcula um ranking básico dos fornecedores com base nos resultados de licitações.

    Args:
        df_results (pd.DataFrame): DataFrame contendo os resultados das licitações.
        company_cnpj (str): CNPJ da sua empresa para destacar no ranking.

    Returns:
        pd.DataFrame: DataFrame com o ranking dos fornecedores.
    """
    if df_results.empty:
        print("Nenhum resultado para calcular o ranking.")
        return pd.DataFrame()

    # Assegura que as colunas essenciais para ranking existem e são do tipo correto.
    # 'niFornecedor' identifica o fornecedor
    df_results['niFornecedor'] = df_results.get('niFornecedor', pd.Series(dtype='str')).astype(str)
    # 'nomeRazaoSocialFornecedor' para o nome
    df_results['nomeFornecedor'] = df_results.get('nomeRazaoSocialFornecedor', df_results.get('nomeFornecedor', pd.Series(dtype='str'))).astype(str)
    # 'valorTotalHomologado' para o valor total vencido
    df_results['valor_total_homologado'] = pd.to_numeric(df_results.get('valorTotalHomologado', 0), errors='coerce').fillna(0)
    # 'quantidadeHomologada' para a quantidade
    df_results['quantidade_homologada'] = pd.to_numeric(df_results.get('quantidadeHomologada', 0), errors='coerce').fillna(0)

    # Agrupar por fornecedor para calcular métricas
    ranking_data = df_results.groupby('niFornecedor').agg(
        total_vitorias=('idCompraItem', 'count'), # Cada 'idCompraItem' pode ser contado como uma vitória de item
        valor_total_homologado=('valor_total_homologado', 'sum'),
        quantidade_total_homologada=('quantidade_homologada', 'sum'),
        nome_fornecedor=('nomeFornecedor', 'first') # Pega o primeiro nome encontrado para o CNPJ
    ).reset_index()

    # Limpeza de dados: remover entradas com CNPJ 'string' genérico ou vazio, se houver
    ranking_data = ranking_data[ranking_data['niFornecedor'].str.isnumeric() & (ranking_data['niFornecedor'].str.len() >= 11)]

    # Ordenar o ranking pelo valor total homologado
    ranking_data = ranking_data.sort_values(by='valor_total_homologado', ascending=False)
    # Atribui a posição no ranking (method='dense' atribui o mesmo rank para valores iguais)
    ranking_data['rank'] = ranking_data['valor_total_homologado'].rank(method='dense', ascending=False).astype(int)

    # Adicionar a posição da sua empresa
    your_company_rank_info = ranking_data[ranking_data['niFornecedor'] == company_cnpj]

    print("\n--- Ranking de Fornecedores ---")
    # Exibe o top 10 do ranking
    print(ranking_data[['rank', 'nome_fornecedor', 'total_vitorias', 'valor_total_homologado']].head(10).to_string(index=False))

    if not your_company_rank_info.empty:
        # Formatação para valores monetários
        valor_sua_empresa = your_company_rank_info['valor_total_homologado'].iloc
        vitorias_sua_empresa = your_company_rank_info['total_vitorias'].iloc
        nome_sua_empresa = your_company_rank_info['nome_fornecedor'].iloc
        posicao_sua_empresa = your_company_rank_info['rank'].iloc

        print(f"\nSua empresa (**{nome_sua_empresa}**) está na **posição: {posicao_sua_empresa}** "
              f"com **{vitorias_sua_empresa} vitórias** e **R$ {valor_sua_empresa:,.2f}** homologados.")
    else:
        print(f"\nSua empresa (CNPJ: **{company_cnpj}**) não foi encontrada nos resultados para este período.")
    
    return ranking_data

# --- Exemplo de Uso ---
if __name__ == "__main__":
    # >>> Substitua pelo CNPJ real da sua empresa (sem pontos, barras ou hífens) <<<
    # Exemplo: YOUR_COMPANY_CNPJ = "00000000000100" 
    YOUR_COMPANY_CNPJ = "05019519000135"

    # Define o período de consulta (limitado a 365 dias para algumas APIs, como o Módulo Legado)
    # Para o exemplo, vamos buscar dados dos últimos 60 dias.
    end_date = datetime.now()
    start_date = end_date - timedelta(days=60) 

    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")
    
    # Lista para armazenar DataFrames de diferentes fontes de dados
    all_tender_items_dfs = []
    
    # 1. Coleta resultados de Itens de Contratações PNCP (Lei 14.133/2021)
    # Este módulo é mais recente e tem campos já formatados para resultados de fornecedores.
    pncp_results_raw = get_resultados_contratacoes_pncp(start_date_str, end_date_str)
    if pncp_results_raw:
        df_pncp_results = pd.DataFrame(pncp_results_raw)
        all_tender_items_dfs.append(df_pncp_results)
    else:
        print("Nenhum resultado PNCP encontrado para o período especificado.")
    
    # 2. Coleta Itens de Pregões do Módulo Legado (Lei 8.666/93)
    # Este módulo também tem informações do fornecedor vencedor e valores homologados.
    # ATENÇÃO: Os nomes das colunas e os tipos de dados podem ser diferentes e precisarão de padronização
    # para serem combinados com os dados do PNCP para um ranking unificado.
    pregoes_items_legado_raw = get_itens_pregoes_legado(start_date_str, end_date_str)
    if pregoes_items_legado_raw:
        df_pregoes_items_legado = pd.DataFrame(pregoes_items_legado_raw)
        
        # Exemplo de Mapeamento/Padronização de Colunas para integrar ao ranking
        # Note que 'quantidade_item' e 'valorHomologadoItem' são strings nos exemplos,
        # então exigem conversão para numérico. O 'fornecedor_vencedor' é o nome, não o NI.
        # Para um ranking unificado, você precisaria de um mapeamento de nomes para CNPJs
        # ou buscar o NI do fornecedor separadamente.
        df_pregoes_items_legado_mapped = df_pregoes_items_legado.rename(columns={
            'fornecedor_vencedor': 'nomeFornecedorLegado', # Nome do fornecedor (não o NI)
            'valorHomologadoItem': 'valor_homologado_item_legado',
            'quantidade_item': 'quantidade_item_legado',
            'id_compra_item': 'idCompraItemLegado'
        })
        #all_tender_items_dfs.append(df_pregoes_items_legado_mapped) # Descomente para incluir após padronização
        print("\nPara integrar dados do Módulo Legado para o ranking, é crucial padronizar os nomes e tipos de colunas, "
              "além de resolver a identificação do fornecedor (CNPJ/CPF) se o campo 'fornecedor_vencedor' retornar apenas o nome.")
    else:
        print("Nenhum item de Pregão (Legado) encontrado para o período especificado.")


    # --- Combinação e Cálculo do Ranking ---
    if all_tender_items_dfs:
        # Combina todos os DataFrames de itens de licitação coletados
        combined_df = pd.concat(all_tender_items_dfs, ignore_index=True, sort=False)
        print(f"\nDataFrame combinado de resultados possui **{len(combined_df)}** registros.")
        
        # Realiza o cálculo do ranking
        ranking_final = calculate_ranking(combined_df, YOUR_COMPANY_CNPJ)
    else:
        print("\nNenhum dado de licitação foi coletado para gerar o ranking.")

    # --- Observações Importantes ---
    print("\n--- Observações Importantes para o Desenvolvimento ---")
    print("1. **Autenticação**: A API de Compras Governamentais (dadosabertos.compras.gov.br) geralmente não exige autenticação por token para acesso a dados públicos.")
    print("   No entanto, a **API do Portal da Transparência** (mencionada nos fontes como /api-de-dados/*) **requer autenticação** via Gov.br (conta Prata/Ouro ou 2FA) para obter uma chave de acesso (token). Esta aplicação foca nos endpoints de Compras, que não explicitamente requerem este token nos exemplos dados [37, 40, etc.].")
    print("2. **Limites de Requisição**: Para a API do Portal da Transparência, há limites de 400 a 700 requisições por minuto (180 para APIs restritas). Ultrapassar esses limites pode suspender o token. Para a API de Compras, embora não explicitamente detalhado, boas práticas sugerem um intervalo entre as requisições para evitar bloqueios temporários.")
    print("3. **Monitoramento em 'Tempo Real'**: O 'tempo real' será alcançado através de **polling frequente**. Implemente um agendador de tarefas (ex: `APScheduler`, `Celery`) para executar o script em intervalos regulares (e.g., a cada 5-15 minutos). Monitore campos como `dataHoraAtualizacao` para buscar apenas dados novos ou modificados.")
    print("4. **Armazenamento de Dados**: Para análise histórica e evitar reprocessamento, é **essencial persistir os dados** coletados em um banco de dados (SQL como PostgreSQL, ou NoSQL como MongoDB).")
    print("5. **Padronização de Dados**: Observe que diferentes módulos da API podem usar nomes de campos ou tipos de dados ligeiramente diferentes para informações similares (ex: `cnpj_fornecedor` vs `niFornecedor`, `valor_estimado` vs `valorTotalHomologado`). Para um ranking consolidado, será necessária uma lógica robusta de padronização.")
    print("6. **Tratamento de Erros e Logging**: Implemente um tratamento de erros mais robusto e logging para monitorar a execução e depurar problemas.")
