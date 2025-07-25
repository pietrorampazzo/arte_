import os
import zipfile
from pathlib import Path

def descompactar_arquivos(pasta_origem):
    """
    Descompacta todos os arquivos ZIP encontrados na pasta especificada
    
    Args:
        pasta_origem (str): Caminho da pasta contendo os arquivos ZIP
    """
    
    # Converte para Path object para facilitar manipulação
    pasta = Path(pasta_origem)
    
    # Verifica se a pasta existe
    if not pasta.exists():
        print(f"Erro: A pasta '{pasta_origem}' não existe!")
        return
    
    # Encontra todos os arquivos ZIP na pasta
    arquivos_zip = list(pasta.glob("*.zip"))
    
    if not arquivos_zip:
        print("Nenhum arquivo ZIP encontrado na pasta!")
        return
    
    print(f"Encontrados {len(arquivos_zip)} arquivo(s) ZIP para descompactar...")
    
    # Descompacta cada arquivo ZIP
    for arquivo_zip in arquivos_zip:
        try:
            print(f"\nDescompactando: {arquivo_zip.name}")
            
            # Cria pasta de destino com o nome do arquivo (sem extensão)
            nome_pasta_destino = arquivo_zip.stem
            pasta_destino = pasta / nome_pasta_destino
            
            # Cria a pasta de destino se não existir
            pasta_destino.mkdir(exist_ok=True)
            
            # Descompacta o arquivo
            with zipfile.ZipFile(arquivo_zip, 'r') as zip_ref:
                zip_ref.extractall(pasta_destino)
                
            print(f"✓ Descompactado em: {pasta_destino}")
            
            # Remove o arquivo ZIP após descompactação bem-sucedida
            arquivo_zip.unlink()
            print(f"✓ Arquivo ZIP removido: {arquivo_zip.name}")
            
        except zipfile.BadZipFile:
            print(f"✗ Erro: '{arquivo_zip.name}' não é um arquivo ZIP válido!")
            
        except PermissionError:
            print(f"✗ Erro: Sem permissão para acessar '{arquivo_zip.name}'!")
            
        except Exception as e:
            print(f"✗ Erro ao descompactar '{arquivo_zip.name}': {str(e)}")
            print("  → Arquivo ZIP mantido devido ao erro")
    
    print(f"\nProcesso concluído!")

# Configuração da pasta
PASTA_ORIGEM = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\TESTE"

if __name__ == "__main__":
    print("=== DESCOMPACTADOR DE ARQUIVOS ZIP ===")
    print(f"Pasta de origem: {PASTA_ORIGEM}")
    
    # Executa a descompactação
    descompactar_arquivos(PASTA_ORIGEM)