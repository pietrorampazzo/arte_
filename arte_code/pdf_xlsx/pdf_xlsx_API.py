import camelot
import pandas as pd
import os

def extract_tables_from_pdfs_to_excel(pdf_folder, output_folder):
    """
    Extrai tabelas de todos os arquivos PDF em uma pasta e as salva em um único
    arquivo Excel (.xlsx), com cada tabela em uma única planilha.

    Args:
        pdf_folder (str): O caminho para a pasta contendo os arquivos PDF.
        output_folder (str): O caminho para a pasta onde o arquivo Excel será salvo.
    """

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    all_dataframes = []
    
    # Itera sobre todos os arquivos na pasta de PDFs
    for filename in os.listdir(pdf_folder):
        if filename.endswith(".pdf"):
            pdf_path = os.path.join(pdf_folder, filename)
            print(f"Processando o arquivo: {filename}")

            try:
                # Extrai tabelas do PDF usando Camelot
                # 'pages': 'all' tenta extrair tabelas de todas as páginas
                # 'flavor': 'lattice' é bom para tabelas com linhas e colunas bem definidas
                # 'line_scale': 40 ajusta a detecção de linhas, pode precisar de ajuste
                tables = camelot.read_pdf(pdf_path, pages='all', flavor='lattice', line_scale=40)
                
                if tables:
                    print(f"  {len(tables)} tabela(s) encontrada(s) em {filename}.")
                    for i, table in enumerate(tables):
                        df = table.df
                        # Adiciona colunas para identificar a origem dos dados
                        df['Source_File'] = filename
                        df['Table_Index_in_File'] = i + 1
                        all_dataframes.append(df)
                else:
                    print(f"  Nenhuma tabela encontrada em {filename}.")

            except Exception as e:
                print(f"  Erro ao processar {filename}: {e}")

    if all_dataframes:
        # Concatena todos os dataframes em um único dataframe
        final_dataframe = pd.concat(all_dataframes, ignore_index=True)
        
        # Define o caminho de saída para o arquivo Excel
        output_excel_path = os.path.join(output_folder, "tabelas_extraidas.xlsx")
        
        # Salva o dataframe final em uma única planilha Excel
        try:
            final_dataframe.to_excel(output_excel_path, index=False, sheet_name="Todas as Tabelas")
            print(f"\nTodas as tabelas foram extraídas e salvas em: {output_excel_path}")
        except Exception as e:
            print(f"\nErro ao salvar o arquivo Excel: {e}")
    else:
        print("\nNenhuma tabela foi extraída de nenhum PDF. Nenhum arquivo Excel foi criado.")

# --- Configurações ---
pdf_input_folder = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\DOWNLOADS"
excel_output_folder = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\DOWNLOADS\tabelas_extraidas"

# --- Executa o algoritmo ---
if __name__ == "__main__":
    extract_tables_from_pdfs_to_excel(pdf_input_folder, excel_output_folder)

