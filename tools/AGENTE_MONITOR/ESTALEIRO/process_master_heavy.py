"""
Script para integrar a planilha ``master_heavy.xlsx`` com a API de dados
abertos do Compras.gov.br. O objetivo deste script é iterar sobre cada
linha da planilha de entrada, extrair informações de licitações (como o
UASG, o número do aviso e a data) do campo ``ARQUIVO`` e, quando
possível, realizar consultas pontuais à API utilizando o CNPJ fornecido
pelo usuário. As consultas são utilizadas para determinar se a A.R.T.E.
participou ou venceu a licitação e para identificar o CNPJ do
fornecedor vencedor.

Nos casos em que a consulta à API não retorna dados (por exemplo,
restrições de rede ou ausência de informações para o UASG/aviso
solicitado), os campos derivados permanecem em branco. O script
sempre define se a licitação está ``Aguardando Disputa`` com base na
data extraída do campo ``ARQUIVO`` e adiciona a data da última
consulta.

O resultado é escrito em um novo arquivo Excel chamado
``master_heavy_arte.xlsx`` no mesmo diretório do script. A nova
planilha contém todas as colunas originais acrescidas das colunas:

- ``Aguardando Disputa (Status)`` – indica se a licitação ainda não
  aconteceu;
- ``Rank Nº`` – posição da A.R.T.E. na licitação (deixa em branco
  quando não é possível calcular);
- ``Adjudicada (Status)`` – ``Sim`` se a A.R.T.E. venceu algum item;
- ``Perdida (Status)`` – ``Sim`` se a A.R.T.E. não foi vencedora;
- ``CNPJ Vencedor (Texto)`` – CNPJ do fornecedor vencedor, quando
  disponível;
- ``Data Última Consulta (Data)`` – data em que o script foi executado.

Requisitos:
    - pandas
    - requests

Uso:
    python process_master_heavy.py --input master_heavy.xlsx --output master_heavy_arte.xlsx --cnpj 05019519000135

Autor: ChatGPT via OpenAI
"""

import argparse
import json
import re
from datetime import datetime
from typing import Optional, Tuple

import pandas as pd
import requests


# Base URL da API de dados abertos do Compras.gov.br. O manual oficial
# (versão de março/2025) indica que os endpoints estão sob o domínio
# ``https://dadosabertos.compras.gov.br``. Alguns módulos (como
# ``modulo-material``) respondem rapidamente, enquanto outros (por
# exemplo ``modulo-legado`` e ``modulo-contratacoes``) podem estar
# indisponíveis em ambientes de teste ou sujeitos a restrições de rede.
BASE_URL = "https://dadosabertos.compras.gov.br"


def parse_arquivo_field(arquivo: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Extrai UASG, número do aviso e data de abertura a partir do campo ``ARQUIVO``.

    O formato esperado do campo ``ARQUIVO`` é algo semelhante a:
        ``U_985693_E_900482025_C_PREFEITURA_MUNICIPAL_DE_SÃO_GABRIEL_DA_PALHA_10-09-2025_13h00m.xlsx``

    A função procura pelas sequências ``U_`` e ``E_`` para identificar o
    código da UASG e o número da licitação. Se as informações não
    estiverem presentes, retorna ``None`` para os respectivos campos.
    Também extrai a data da licitação (no formato DD-MM-YYYY) que
    aparece antes do horário e converte-a para ``YYYY-MM-DD``.

    Args:
        arquivo (str): O texto do campo ``ARQUIVO``.

    Returns:
        Tuple[str|None, str|None, str|None]: (uasg, numero_aviso, data)
    """
    uasg = None
    numero_aviso = None
    data_evento = None
    # Regex para capturar UASG e número do aviso
    match = re.search(r"U_(\d+)_E_(\d+)", arquivo)
    if match:
        uasg = match.group(1)
        numero_aviso = match.group(2)
    # Procurar a data no formato DD-MM-YYYY (antes do horário)
    # Dividimos o nome em partes e verificamos cada token
    tokens = arquivo.split('_')
    for token in tokens:
        if re.match(r"\d{2}-\d{2}-\d{4}", token):
            try:
                # Converter de DD-MM-YYYY para YYYY-MM-DD
                date_obj = datetime.strptime(token, "%d-%m-%Y")
                data_evento = date_obj.strftime("%Y-%m-%d")
            except ValueError:
                pass
            break
    return uasg, numero_aviso, data_evento


def consultar_modalidade(uasg: str, numero_aviso: str, data: str) -> Optional[int]:
    """Consulta o código de modalidade da licitação via endpoint ``1_consultarLicitacao``.

    A API de licitações do módulo legado exige, para a busca, que se
    informe um intervalo de datas de publicação limitado a 365 dias.
    Utilizamos a própria data do evento como início e fim do intervalo
    para restringir o resultado a um único dia. Caso a consulta
    retorne resultados, devolvemos o valor do campo ``modalidade`` do
    primeiro item. Caso contrário, retornamos ``None``.

    Args:
        uasg (str): Código da UASG extraído do campo ``ARQUIVO``.
        numero_aviso (str): Número da licitação extraído do campo ``ARQUIVO``.
        data (str): Data no formato ``YYYY-MM-DD``.

    Returns:
        Optional[int]: Código da modalidade, se encontrado.
    """
    params = {
        "pagina": 1,
        "tamanhoPagina": 1,
        "uasg": uasg,
        "numero_aviso": numero_aviso,
        "data_publicacao_inicial": data,
        "data_publicacao_final": data,
    }
    url = f"{BASE_URL}/modulo-legado/1_consultarLicitacao"
    try:
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code == 200:
            data_json = resp.json()
            resultados = data_json.get("resultado", [])
            if resultados:
                # Pega a modalidade do primeiro resultado
                modalidade = resultados[0].get("modalidade")
                return int(modalidade) if modalidade is not None else None
        else:
            # Erros 404 ou outros são tratados retornando None
            return None
    except Exception:
        return None


def consultar_itens_licitacao(uasg: str, numero_aviso: str, modalidade: int, cnpj: str) -> list:
    """Consulta itens de licitação vencedores para um determinado CNPJ.

    Utiliza o endpoint ``2_consultarItemLicitacao`` do módulo legado.
    Define ``tamanhoPagina`` como 500 para tentar retornar o maior
    número possível de registros por página. Em caso de falha na
    requisição, retorna uma lista vazia.

    Args:
        uasg (str): Código da UASG.
        numero_aviso (str): Número da licitação.
        modalidade (int): Código da modalidade retornado por
            ``consultar_modalidade``.
        cnpj (str): CNPJ do fornecedor.

    Returns:
        list: Lista de dicionários representando os itens da licitação
        encontrados.
    """
    params = {
        "pagina": 1,
        "tamanhoPagina": 500,
        "uasg": uasg,
        "numero_aviso": numero_aviso,
        "modalidade": modalidade,
        "cnpj_fornecedor": cnpj,
    }
    url = f"{BASE_URL}/modulo-legado/2_consultarItemLicitacao"
    resultados: list = []
    try:
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code == 200:
            data_json = resp.json()
            resultados = data_json.get("resultado", [])
    except Exception:
        # Em caso de exceção, retorna lista vazia
        pass
    return resultados


def process_planilha(
    df: pd.DataFrame,
    cnpj: str,
    current_date: Optional[datetime] = None,
) -> pd.DataFrame:
    """Processa a planilha adicionando campos de status e ranking.

    A tabela resultante inclui as colunas solicitadas pelo usuário:

    - ``Aguardando Disputa (Status)``: indica se a licitação ainda não
      aconteceu. É marcada como ``Sim`` quando a data extraída do
      campo ``ARQUIVO`` é posterior à data fornecida em ``current_date``.
    - ``Rank Nº``: posição da empresa A.R.T.E. na licitação. Como o
      ranking depende de dados externos disponíveis via API, caso não
      haja informações, permanece vazio.
    - ``Adjudicada (Status)``: ``Sim`` se a A.R.T.E. venceu a licitação.
    - ``Perdida (Status)``: ``Sim`` se outro fornecedor venceu ou a
      empresa foi desclassificada.
    - ``CNPJ Vencedor (Texto)``: CNPJ do fornecedor vencedor, quando
      disponível.
    - ``Data Última Consulta (Data)``: data em que a consulta foi
      executada (normalmente a data atual).

    O cálculo de ranking e a identificação do vencedor ainda exigem
    chamadas à API de Compras. Estas chamadas são realizadas quando
    possível, mas em ambientes com restrição de rede podem não
    retornar resultados. Nesses casos, os campos permanecem em branco.

    Args:
        df (pd.DataFrame): DataFrame da planilha original.
        cnpj (str): CNPJ da A.R.T.E.
        current_date (datetime, opcional): data de referência para
            definir o status "Aguardando Disputa". Se não for
            fornecida, usa ``datetime.now()``.

    Returns:
        pd.DataFrame: DataFrame original acrescido das colunas de status.
    """
    df_output = df.copy()
    if current_date is None:
        current_date = datetime.now()

    # Definição das novas colunas
    df_output["Aguardando Disputa (Status)"] = ""
    df_output["Rank Nº"] = ""
    df_output["Adjudicada (Status)"] = ""
    df_output["Perdida (Status)"] = ""
    df_output["CNPJ Vencedor (Texto)"] = ""
    df_output["Data Última Consulta (Data)"] = current_date.strftime("%Y-%m-%d")

    for idx, row in df_output.iterrows():
        arquivo = str(row.get("ARQUIVO", ""))
        uasg, numero_aviso, data_evento = parse_arquivo_field(arquivo)
        # Determinar se a licitação ainda não ocorreu
        aguardando = False
        try:
            if data_evento:
                data_evento_dt = datetime.strptime(data_evento, "%Y-%m-%d")
                aguardando = data_evento_dt.date() > current_date.date()
        except Exception:
            aguardando = False
        df_output.at[idx, "Aguardando Disputa (Status)"] = "Sim" if aguardando else "Não"

        # Caso a licitação ainda não ocorreu, não há mais informações
        if aguardando:
            continue
        # Para licitações passadas, tentamos determinar vencedor e ranking
        # Primeiro, consultar a modalidade da licitação (se possível)
        modalidade = None
        if uasg and numero_aviso and data_evento:
            modalidade = consultar_modalidade(uasg, numero_aviso, data_evento)

        if modalidade is not None:
            # Consultar itens da licitação para o CNPJ da A.R.T.E.
            itens_arte = consultar_itens_licitacao(uasg, numero_aviso, modalidade, cnpj)
            # Consultar todos os itens (sem filtrar CNPJ) para conhecer o vencedor
            # Observação: O campo "cnpj_fornecedor" filtra o CNPJ do vencedor da licitação
            # segundo o manual【908491075657389†L4412-L4515】. Se omitido, a API retorna
            # os dados de todos os fornecedores vencedores dos itens.
            itens_todos = consultar_itens_licitacao(uasg, numero_aviso, modalidade, "")

            # Determinar se a A.R.T.E. venceu algum item
            venceu_algum = bool(itens_arte)
            # Determinar vencedor principal (primeiro item da lista geral)
            cnpj_vencedor = ""
            if itens_todos:
                # Tenta pegar o campo 'cnpj_fornecedor' ou 'cnpjFornecedore' (casos distintos)
                for item in itens_todos:
                    cnpj_item = item.get("cnpj_fornecedor") or item.get("cpfVencedor") or ""
                    if cnpj_item:
                        cnpj_vencedor = cnpj_item
                        break
            df_output.at[idx, "CNPJ Vencedor (Texto)"] = cnpj_vencedor

            # Adjudicada / Perdida
            if venceu_algum:
                df_output.at[idx, "Adjudicada (Status)"] = "Sim"
                df_output.at[idx, "Perdida (Status)"] = ""
            else:
                df_output.at[idx, "Adjudicada (Status)"] = ""
                df_output.at[idx, "Perdida (Status)"] = "Sim"

            # Rank Nº: não é possível calcular sem comparar com outros
            # fornecedores. Se existirem itens, podemos marcar 1 quando
            # vencemos algum item, caso contrário, deixamos em branco.
            if venceu_algum:
                df_output.at[idx, "Rank Nº"] = "1"
            else:
                df_output.at[idx, "Rank Nº"] = ""
        else:
            # Não foi possível consultar a modalidade; campos permanecem vazios
            pass

    return df_output


def main():
    parser = argparse.ArgumentParser(
        description="Integra a planilha master_heavy.xlsx com a API de Compras.gov.br"
    )
    parser.add_argument(
        "--input", required=True, help="Caminho do arquivo Excel de entrada"
    )
    parser.add_argument(
        "--output", required=True, help="Caminho do arquivo Excel de saída"
    )
    parser.add_argument(
        "--cnpj", required=True, help="CNPJ do fornecedor para filtrar nas consultas"
    )
    parser.add_argument(
        "--current-date",
        dest="current_date",
        default=None,
        help=(
            "Data de referência no formato AAAA-MM-DD para calcular o "
            "status 'Aguardando Disputa'. Se omitido, utiliza a data atual."
        ),
    )
    args = parser.parse_args()

    # Carregar planilha
    df = pd.read_excel(args.input)
    # Converter current_date se fornecido
    current_date_obj = None
    if args.current_date:
        try:
            current_date_obj = datetime.strptime(args.current_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError(
                "--current-date deve estar no formato AAAA-MM-DD, por exemplo, 2025-09-09"
            )
    # Processar dados
    result_df = process_planilha(df, args.cnpj, current_date=current_date_obj)
    # Exportar para Excel
    result_df.to_excel(args.output, index=False)


if __name__ == "__main__":
    main()