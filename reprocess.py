
import glob
import openpyxl
import os
import sys
from pathlib import Path

# Adiciona a raiz do projeto ao path para permitir a importação de arte_ataque_zip
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from arte_ataque_zip import processar_pasta_edital, main as run_main_processing

def find_files_with_errors():
    """
    Encontra todos os arquivos *master*.xlsx com a string de erro específica.
    Retorna uma lista de caminhos para os arquivos com erros.
    """
    error_string = "IA FALHOU EM RETORNAR Nº"
    # Usar caminho relativo para ser mais portatil
    file_pattern = os.path.join(project_root, "**", "*master*.xlsx")
    excel_files = glob.glob(file_pattern, recursive=True)
    
    found_files = []
    for file in excel_files:
        try:
            wb = openpyxl.load_workbook(file, data_only=True)
            found_in_file = False
            for sheet in wb.worksheets:
                for row in sheet.iter_rows():
                    for cell in row:
                        if cell.value and error_string in str(cell.value):
                            found_files.append(file)
                            found_in_file = True
                            break
                    if found_in_file:
                        break
                if found_in_file:
                    break
        except Exception:
            # Ignora arquivos que não podem ser lidos
            pass
    return list(set(found_files)) # Usa set para obter arquivos unicos

def reprocess_edital(master_file_path_str):
    """
    Reprocessa um único edital, dado o caminho para seu arquivo _master.xlsx.
    """
    master_file_path = Path(master_file_path_str)
    edital_path = master_file_path.parent

    # Caso especial para master.xlsx e master_stanley.xlsx em DOWNLOADS
    if edital_path.name == 'DOWNLOADS':
        print(f"- Pulando reprocessamento do arquivo principal: {master_file_path.name}")
        return

    print(f"-- Reprocessando edital: {edital_path.name}")

    if master_file_path.exists():
        print(f"  - Removendo arquivo corrompido: {master_file_path.name}")
        os.remove(master_file_path)
    
    # Chama a função de processamento de arte_ataque_zip
    try:
        processar_pasta_edital(edital_path)
    except Exception as e:
        print(f"  - ERRO ao reprocessar {edital_path.name}: {e}")

def main_reprocess():
    print("--- Iniciando script de reprocessamento ---")
    
    print("\n[ETAPA 1/3] Procurando arquivos com erros...")
    files_to_fix = find_files_with_errors()
    
    if not files_to_fix:
        print("Nenhum arquivo com o erro 'IA FALHOU EM RETORNAR Nº' foi encontrado.")
    else:
        print(f"Encontrados {len(files_to_fix)} arquivos para reprocessar:")
        for f in sorted(files_to_fix):
            print(f"  - {os.path.relpath(f, project_root)}")
        
        print("\n[ETAPA 2/3] Reprocessando editais individuais...")
        for file_path in sorted(files_to_fix):
            reprocess_edital(file_path)
            
    print("\n[ETAPA 3/3] Executando o processo principal de consolidação...")
    # Isso irá regenerar os arquivos master.xlsx e summary.xlsx principais
    try:
        run_main_processing()
    except Exception as e:
        print(f"Ocorreu um erro durante a consolidação final: {e}")

    print("\n--- Script de reprocessamento concluído ---")

if __name__ == "__main__":
    main_reprocess()
