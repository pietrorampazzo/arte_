import os
import pandas as pd

def somar_planilhas(diretorio, arquivo_saida):
    # Lista todos os arquivos Excel no diretório
    arquivos_excel = [f for f in os.listdir(diretorio) if f.endswith('.xlsx')]
    if not arquivos_excel:
        print(f"Nenhum arquivo Excel encontrado no diretório: {diretorio}")
        return

    print(f"📂 Encontrados {len(arquivos_excel)} arquivos Excel para processar.")
    dados_combinados = []

    for arquivo in arquivos_excel:
        caminho_arquivo = os.path.join(diretorio, arquivo)
        try:
            # Lê todas as planilhas do arquivo Excel
            xls = pd.ExcelFile(caminho_arquivo)
            for nome_planilha in xls.sheet_names:
                print(f"🔄 Processando planilha '{nome_planilha}' do arquivo '{arquivo}'...")
                df = pd.read_excel(xls, sheet_name=nome_planilha)
                df['Arquivo'] = arquivo  # Adiciona uma coluna com o nome do arquivo
                df['Planilha'] = nome_planilha  # Adiciona uma coluna com o nome da planilha
                dados_combinados.append(df)
        except Exception as e:
            print(f"❌ Erro ao processar o arquivo '{arquivo}': {e}")

    if not dados_combinados:
        print("Nenhum dado foi combinado.")
        return

    # Combina todos os DataFrames em um único
    df_combinado = pd.concat(dados_combinados, ignore_index=True)

    # Salva o DataFrame combinado em um novo arquivo Excel
    caminho_saida = os.path.join(diretorio, arquivo_saida)
    try:
        df_combinado.to_excel(caminho_saida, index=False, sheet_name='Resumo')
        print(f"✅ Dados combinados salvos em: {caminho_saida}")
    except Exception as e:
        print(f"❌ Erro ao salvar o arquivo de saída: {e}")

if __name__ == "__main__":
    PASTA_ORCAMENTOS = r"C:\Users\pietr\Meu Drive\arte_drive\ORÇARMENTO\ORÇANDO"
    ARQUIVO_SUMARIO = "summary.xlsx"
    somar_planilhas(PASTA_ORCAMENTOS, ARQUIVO_SUMARIO)