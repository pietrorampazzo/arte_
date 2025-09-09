import pandas as pd
from datetime import date, timedelta
import requests
import json

BASE_URL = "https://dadosabertos.compras.gov.br"

def consultar_resultado_itens_contratacoes_pncp(unidade_orgao_codigo_unidade, numero_compra, numero_item_compra, data_resultado_pncp_inicial, data_resultado_pncp_final):
    url = f"{BASE_URL}/modulo-contratacoes/3_consultarResultadoItensContratacoes_PNCP_14133"
    params = {
        "unidadeOrgaoCodigoUnidade": unidade_orgao_codigo_unidade,
        "numeroCompra": numero_compra,
        "numeroItemCompra": numero_item_compra,
        "dataResultadoPncpInicial": data_resultado_pncp_inicial,
        "dataResultadoPncpFinal": data_resultado_pncp_final
    }
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao consultar resultado de itens de contratações PNCP: {e}")
        return None
    

# CNPJ da empresa a ser monitorada
CNPJ_NOSSA_EMPRESA = "05.019.519/0001-35"

def monitorar_licitacoes(caminho_planilha):
    try:
        df = pd.read_excel(caminho_planilha)
    except FileNotFoundError:
        print(f"Erro: O arquivo {caminho_planilha} não foi encontrado.")
        return

    # Adicionar colunas se não existirem
    colunas_novas = [
        "Aguardando Disputa (Status)",
        "Rank Nº",
        "Adjudicada (Status)",
        "Perdida (Status)",
        "CNPJ Vencedor (Texto)",
        "Data Última Consulta (Data)"
    ]
    for col in colunas_novas:
        if col not in df.columns:
            df[col] = ""

    hoje = date.today()
    trinta_dias_atras = hoje - timedelta(days=30)

    for index, row in df.iterrows():
        try:
            # Extrair parâmetros da coluna 'ARQUIVO' e 'Nº'
            # Ex: ARQUIVO = 'U_153128_E_90020_2025.xlsx'
            # Ex: Nº = 1
            nome_arquivo = row["ARQUIVO"]
            partes = nome_arquivo.split("_")
            codigo_uasg = int(partes[1])
            numero_compra = int(partes[3] + partes[4].split(".")[0]) # Concatena 90020 e 2025 para 900202025
            numero_item_compra = int(row["Nº"])

            print(f"Consultando licitação: UASG={codigo_uasg}, Compra={numero_compra}, Item={numero_item_compra}")

            resultados = consultar_resultado_itens_contratacoes_pncp(
                codigo_uasg,
                numero_compra,
                numero_item_compra,
                trinta_dias_atras.strftime("%Y-%m-%d"),
                hoje.strftime("%Y-%m-%d")
            )

            if resultados and resultados["resultado"]:
                print(f"Resultados encontrados para UASG={codigo_uasg}, Compra={numero_compra}, Item={numero_item_compra}")
                df.at[index, "Aguardando Disputa (Status)"] = "Não"

                nossa_empresa_encontrada = False
                fornecedor_vencedor = None
                menor_ordem_classificacao = float("inf")

                # Encontrar o vencedor e verificar nossa empresa
                for fornecedor in resultados["resultado"]:
                    if fornecedor["ordemClassificacaoSrp"] < menor_ordem_classificacao:
                        menor_ordem_classificacao = fornecedor["ordemClassificacaoSrp"]
                        fornecedor_vencedor = fornecedor

                    if fornecedor["niFornecedor"] == CNPJ_NOSSA_EMPRESA:
                        nossa_empresa_encontrada = True
                        df.at[index, "Rank Nº"] = fornecedor["ordemClassificacaoSrp"]
                        if fornecedor["ordemClassificacaoSrp"] == 1:
                            df.at[index, "Adjudicada (Status)"] = "Sim"
                            df.at[index, "Perdida (Status)"] = "Não"
                        else:
                            df.at[index, "Adjudicada (Status)"] = "Não"
                            df.at[index, "Perdida (Status)"] = "Sim"

                if not nossa_empresa_encontrada:
                    df.at[index, "Perdida (Status)"] = "Sim"
                    df.at[index, "Adjudicada (Status)"] = "Não"
                    df.at[index, "Rank Nº"] = "N/A"

                if fornecedor_vencedor:
                    df.at[index, "CNPJ Vencedor (Texto)"] = fornecedor_vencedor["niFornecedor"]

            else:
                print(f"Nenhum resultado encontrado para UASG={codigo_uasg}, Compra={numero_compra}, Item={numero_item_compra}. Aguardando disputa.")
                df.at[index, "Aguardando Disputa (Status)"] = "Sim"
                df.at[index, "Adjudicada (Status)"] = ""
                df.at[index, "Perdida (Status)"] = ""
                df.at[index, "Rank Nº"] = ""
                df.at[index, "CNPJ Vencedor (Texto)"] = ""

            df.at[index, "Data Última Consulta (Data)"] = hoje.strftime("%Y-%m-%d")

        except Exception as e:
            print(f"Erro ao processar a linha {index}: {e}")
            df.at[index, "Data Última Consulta (Data)"] = hoje.strftime("%Y-%m-%d") # Registrar a data mesmo com erro

    # Salvar a planilha atualizada
    df.to_excel(caminho_planilha, index=False)
    print(f"Planilha {caminho_planilha} atualizada com sucesso.")

    # Criar master_heavy.xlsx se houver alguma adjudicação que não seja nossa empresa
    df_heavy = df[(df["Adjudicada (Status)"] == "Sim") & (df["CNPJ Vencedor (Texto)"] != CNPJ_NOSSA_EMPRESA)]
    if not df_heavy.empty:
        df_heavy.to_excel("master_heavy.xlsx", index=False)
        print("Arquivo master_heavy.xlsx criado/atualizado.")


# Exemplo de uso (assumindo que master.xlsx existe no diretório de trabalho)
if __name__ == "__main__":
    monitorar_licitacoes("master.xlsx")


