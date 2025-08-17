import os
import shutil
import re
import zipfile
from pathlib import Path

def descompactar_arquivos(pasta_origem):
    pasta = Path(pasta_origem)
    if not pasta.exists():
        print(f"Erro: A pasta '{pasta_origem}' não existe!")
        return
    arquivos_zip = list(pasta.glob("*.zip"))
    if not arquivos_zip:
        print("Nenhum arquivo ZIP encontrado na pasta!")
        return
    print(f"Encontrados {len(arquivos_zip)} arquivo(s) ZIP para descompactar...")
    for arquivo_zip in arquivos_zip:
        try:
            print(f"\nDescompactando: {arquivo_zip.name}")
            nome_pasta_destino = arquivo_zip.stem
            pasta_destino = pasta / nome_pasta_destino
            pasta_destino.mkdir(exist_ok=True)
            with zipfile.ZipFile(arquivo_zip, 'r') as zip_ref:
                zip_ref.extractall(pasta_destino)
            print(f"✓ Descompactado em: {pasta_destino}")
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

def extrair_e_copiar_pdfs(pasta_origem, pasta_destino):
    pasta_origem = Path(pasta_origem)
    pasta_destino = Path(pasta_destino)
    pasta_destino.mkdir(parents=True, exist_ok=True)
    padrao_relacao = re.compile(r"RelacaoItens\d+\.pdf", re.IGNORECASE)
    copiados = 0
    print("📁 Iniciando varredura das subpastas...")
    for subpasta in pasta_origem.iterdir():
        if subpasta.is_dir():
            nome_pasta = subpasta.name
            print(f"🔍 Verificando pasta: {nome_pasta}")
            for arquivo in subpasta.glob("*.pdf"):
                if padrao_relacao.fullmatch(arquivo.name):
                    novo_nome = f"{nome_pasta}.pdf"
                    destino_final = pasta_destino / novo_nome
                    shutil.copy2(arquivo, destino_final)
                    print(f"✅ {arquivo.name} copiado e renomeado para {novo_nome}")
                    copiados += 1
                    break  # Considera apenas o primeiro encontrado por pasta
    print(f"\n🎉 Processo concluído: {copiados} arquivo(s) movido(s) para {pasta_destino}")

# Configuração da pasta
PASTA_ORIGEM = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\TESTE"
PASTA_DESTINO = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\TESTE"

if __name__ == "__main__":
    print("=== DESCOMPACTADOR DE ARQUIVOS ZIP ===")
    print(f"Pasta de origem: {PASTA_ORIGEM}")
    descompactar_arquivos(PASTA_ORIGEM)
    print("\n=== EXTRAÇÃO E CÓPIA DE PDFs ===")
    extrair_e_copiar_pdfs(PASTA_ORIGEM, PASTA_DESTINO)