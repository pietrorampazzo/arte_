import os
from pathlib import Path

def excluir_arquivos_por_extensao(diretorio_raiz, extensoes):
    """
    Exclui arquivos com as extensões especificadas dentro de um diretório
    e de todas as suas subpastas.

    AVISO: Esta operação é permanente.

    :param diretorio_raiz: O caminho para a pasta principal onde a busca começará.
    :param extensoes: Uma lista de extensões de arquivo a serem excluídas (ex: ['.txt', '.xlsx']).
    """
    pasta_raiz = Path(diretorio_raiz)
    
    if not pasta_raiz.is_dir():
        print(f"❌ ERRO: O diretório '{diretorio_raiz}' não foi encontrado.")
        return

    print(f"🧹 Iniciando a limpeza no diretório: {pasta_raiz}")
    print(f"🔎 Procurando por arquivos com extensões: {', '.join(extensoes)}")

    arquivos_excluidos = 0
    erros = 0

    # Itera por cada extensão fornecida
    for ext in extensoes:
        # O método rglob('*' + ext) encontra todos os arquivos com a extensão recursivamente
        for arquivo in pasta_raiz.rglob(f'*{ext}'):
            try:
                arquivo.unlink()  # Exclui o arquivo
                print(f"  🗑️ Excluído: {arquivo}")
                arquivos_excluidos += 1
            except Exception as e:
                print(f"  ❌ Falha ao excluir {arquivo}: {e}")
                erros += 1
    
    print("\n" + "="*40)
    if arquivos_excluidos == 0 and erros == 0:
        print("✅ Limpeza concluída. Nenhum arquivo correspondente foi encontrado.")
    else:
        print(f"✅ Limpeza concluída!")
        print(f"   - Arquivos excluídos: {arquivos_excluidos}")
        if erros > 0:
            print(f"   - Falhas: {erros}")
    print("="*40)


if __name__ == "__main__":
    # --- CONFIGURAÇÃO ---
    # Especifique o diretório principal aqui
    diretorio_alvo = r"C:\Users\pietr\OneDrive\.vscode\arte_\DOWNLOADS\EDITAIS"
    
    # Especifique as extensões dos arquivos a serem excluídos
    extensoes_alvo = ['.xlsx', '.txt']

    # --- EXECUÇÃO ---
    excluir_arquivos_por_extensao(diretorio_alvo, extensoes_alvo)
