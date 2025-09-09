import pandas as pd
from datetime import datetime, timedelta
from comprasgov_api_1 import get_resultados_contratacoes_pncp, get_itens_pregoes_legado
import os
import re

BASE_URL = "https://dadosabertos.compras.gov.br"

CNPJ_NOSSA_EMPRESA = "05019519000135"
OUTPUT_DIR = r"C:\Users\pietr\OneDrive\.vscode\arte_\DOWNLOADS\RESULTADO"

def monitorar_licitacoes(caminho_planilha_entrada):
    try:
        df = pd.read_excel(caminho_planilha_entrada)
    except FileNotFoundError:
        print(f"Erro: O arquivo {caminho_planilha_entrada} não foi encontrado.")
        return

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

    hoje = datetime.now()
    trinta_dias_atras = hoje - timedelta(days=30)

    for index, row in df.iterrows():
        try:
            nome_arquivo = row["ARQUIVO"]
            partes = nome_arquivo.split("_")
            codigo_uasg = int(partes[1])
            numero_compra = int(partes[3] + partes[4].split(".")[0])  # Ex: 900202025
            numero_item_compra = int(row["Nº"])

            print(f"Consultando licitação: UASG={codigo_uasg}, Compra={numero_compra}, Item={numero_item_compra}")

            resultados = get_resultados_contratacoes_pncp(
                trinta_dias_atras.strftime("%Y-%m-%d"),
                hoje.strftime("%Y-%m-%d"),
                CNPJ_NOSSA_EMPRESA.replace(".", "").replace("/", "").replace("-", "")
            )

            if resultados:
                for fornecedor in resultados:
                    if fornecedor["niFornecedor"] == CNPJ_NOSSA_EMPRESA:
                        df.at[index, "Aguardando Disputa (Status)"] = "Não"
                        df.at[index, "Rank Nº"] = fornecedor["ordemClassificacaoSrp"]
                        df.at[index, "Adjudicada (Status)"] = "Sim" if fornecedor["ordemClassificacaoSrp"] == 1 else "Não"
                        df.at[index, "Perdida (Status)"] = "Sim" if fornecedor["ordemClassificacaoSrp"] != 1 else "Não"
                        df.at[index, "CNPJ Vencedor (Texto)"] = fornecedor["niFornecedor"]
            else:
                df.at[index, "Aguardando Disputa (Status)"] = "Sim"
                df.at[index, "Adjudicada (Status)"] = ""
                df.at[index, "Perdida (Status)"] = ""
                df.at[index, "Rank Nº"] = ""
                df.at[index, "CNPJ Vencedor (Texto)"] = ""

            df.at[index, "Data Última Consulta (Data)"] = hoje.strftime("%Y-%m-%d")

        except Exception as e:
            print(f"Erro ao processar a linha {index}: {e}")
            df.at[index, "Data Última Consulta (Data)"] = hoje.strftime("%Y-%m-%d")

    df.to_excel(caminho_planilha_entrada, index=False)
    print(f"Planilha {caminho_planilha_entrada} atualizada com sucesso.")

    df_heavy_arte = df[(df["Adjudicada (Status)"] == "Sim") & (df["CNPJ Vencedor (Texto)"] != CNPJ_NOSSA_EMPRESA)]
    if not df_heavy_arte.empty:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        caminho_saida = os.path.join(OUTPUT_DIR, "master_heavy_arte.xlsx")
        df_heavy_arte.to_excel(caminho_saida, index=False)
        print(f"Arquivo {caminho_saida} criado/atualizado.")
    else:
        print("Nenhuma adjudicação para outra empresa encontrada. master_heavy_arte.xlsx não foi criado.")

if __name__ == "__main__":
    monitorar_licitacoes("master_heavy.xlsx")
