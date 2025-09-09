import pandas as pd
from datetime import date, timedelta
from ESTALEIRO.comprasgov_api_2 import get_resultados_contratacoes_pncp
import os
import re

# CNPJ da empresa a ser monitorada
CNPJ_NOSSA_EMPRESA = "05.019.519/0001-35"

# Diretório de saída para o arquivo master_heavy_arte.xlsx
OUTPUT_DIR = "/home/ubuntu/RESULTADO" # Caminho temporário no sandbox

def monitorar_licitacoes(caminho_planilha_entrada):
    try:
        df = pd.read_excel(caminho_planilha_entrada)
    except FileNotFoundError:
        print(f"Erro: O arquivo {caminho_planilha_entrada} não foi encontrado.")
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
            
            # Extrair numero_compra e ano, removendo caracteres não numéricos
            numero_compra_str = re.sub(r'\D', '', partes[3]) # Remove tudo que não for dígito
            ano_str = re.sub(r'\D', '', partes[4].split(".")[0]) # Remove tudo que não for dígito
            numero_compra = int(numero_compra_str + ano_str)
            
            numero_item_compra = int(row["Nº"])

            print(f"Consultando licitação: UASG={codigo_uasg}, Compra={numero_compra}, Item={numero_item_compra}")

            resultados = get_resultados_contratacoes_pncp(
                trinta_dias_atras.strftime("%Y-%m-%d"),
                hoje.strftime("%Y-%m-%d"),
                ni_fornecedor=CNPJ_NOSSA_EMPRESA.replace(".", "").replace("/", "").replace("-", "")
            )

            # Filtrar resultados para a UASG e número da compra específicos
            resultados_filtrados = []
            if resultados:
                for res in resultados:
                    # Ajuste para comparar numeroCompra com o formato da API (pode ser string ou int)
                    # E para comparar unidadeOrgaoCodigoUnidade
                    if str(res.get("numeroCompra")) == str(numero_compra) and \
                       str(res.get("unidadeOrgaoCodigoUnidade")) == str(codigo_uasg) and \
                       str(res.get("numeroItemCompra")) == str(numero_item_compra):
                        resultados_filtrados.append(res)

            if resultados_filtrados:
                print(f"Resultados encontrados para UASG={codigo_uasg}, Compra={numero_compra}, Item={numero_item_compra}")
                df.at[index, "Aguardando Disputa (Status)"] = "Não"

                nossa_empresa_encontrada = False
                fornecedor_vencedor = None
                menor_ordem_classificacao = float("inf")

                # Encontrar o vencedor e verificar nossa empresa
                for fornecedor in resultados_filtrados:
                    # A API retorna o CNPJ sem formatação, então removemos a formatação do nosso CNPJ para comparação
                    cnpj_fornecedor_sem_formatacao = fornecedor["niFornecedor"].replace(".", "").replace("/", "").replace("-", "")
                    cnpj_nossa_empresa_sem_formatacao = CNPJ_NOSSA_EMPRESA.replace(".", "").replace("/", "").replace("-", "")

                    # O campo ordemClassificacaoSrp pode não existir ou ser None para todos os resultados
                    # Se não existir, assumimos que o primeiro resultado é o vencedor ou que não há ranking claro
                    ordem_classificacao = fornecedor.get("ordemClassificacaoSrp", 1) # Assume 1 se não houver

                    if ordem_classificacao < menor_ordem_classificacao:
                        menor_ordem_classificacao = ordem_classificacao
                        fornecedor_vencedor = fornecedor

                    if cnpj_fornecedor_sem_formatacao == cnpj_nossa_empresa_sem_formatacao:
                        nossa_empresa_encontrada = True
                        df.at[index, "Rank Nº"] = ordem_classificacao
                        if ordem_classificacao == 1:
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

    # Salvar a planilha atualizada (master_heavy.xlsx de entrada)
    df.to_excel(caminho_planilha_entrada, index=False)
    print(f"Planilha {caminho_planilha_entrada} atualizada com sucesso.")

    # Criar master_heavy_arte.xlsx se houver alguma adjudicação que não seja nossa empresa
    df_heavy_arte = df[(df["Adjudicada (Status)"] == "Sim") & (df["CNPJ Vencedor (Texto)"].astype(str).str.replace(".", "").replace("/", "").replace("-", "") != CNPJ_NOSSA_EMPRESA.replace(".", "").replace("/", "").replace("-", ""))]
    
    if not df_heavy_arte.empty:
        # Cria o diretório de saída se não existir
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        caminho_saida = os.path.join(OUTPUT_DIR, "master_heavy_arte.xlsx")
        df_heavy_arte.to_excel(caminho_saida, index=False)
        print(f"Arquivo {caminho_saida} criado/atualizado.")
    else:
        print("Nenhuma adjudicação para outra empresa encontrada. master_heavy_arte.xlsx não foi criado.")


# Exemplo de uso
if __name__ == "__main__":
    # O arquivo master_heavy.xlsx será o input
    monitorar_licitacoes("master_heavy.xlsx")


