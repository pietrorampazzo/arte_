
import glob
import openpyxl
import os

def find_excel_errors():
    error_string = "IA FALHOU EM RETORNAR Nº"
    file_pattern = "c:/Users/pietr/OneDrive/.vscode/arte_/**/*master*.xlsx"
    excel_files = glob.glob(file_pattern, recursive=True)
    
    found_files = []

    for file in excel_files:
        try:
            wb = openpyxl.load_workbook(file, data_only=True)
            for sheet in wb.worksheets:
                for row in sheet.iter_rows():
                    for cell in row:
                        if cell.value and error_string in str(cell.value):
                            if file not in found_files:
                                print(file)
                                found_files.append(file)
                            break
                    if file in found_files:
                        break
                if file in found_files:
                    break
        except Exception as e:
            pass

find_excel_errors()
