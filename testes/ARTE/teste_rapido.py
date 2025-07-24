#!/usr/bin/env python3
"""
Teste rápido do sistema de download
"""

import subprocess
import sys
import os
from pathlib import Path

def instalar_dependencias():
    """Instala dependências necessárias"""
    try:
        print("📦 Instalando dependências...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", 
                             "requests", "pandas", "openpyxl", "--quiet"])
        print("✅ Dependências instaladas!")
        return True
    except Exception as e:
        print(f"❌ Erro ao instalar dependências: {e}")
        return False

def testar_download():
    """Testa o download da licitação específica"""
    try:
        print("🔍 Testando download da licitação 98428705900032025...")
        
        # Importar e executar
        from comprasnet_downloader_windows import ComprasnetDownloaderPersonalizado
        
        downloader = ComprasnetDownloaderPersonalizado()
        resultado = downloader.processar_licitacao_completa("98428705900032025")
        
        if resultado:
            print(f"✅ SUCESSO! Arquivos salvos em: {resultado}")
            
            # Abrir pasta
            try:
                os.startfile(resultado)
                print("📂 Pasta aberta no Explorer")
            except:
                pass
            
            return True
        else:
            print("❌ Falha no download")
            return False
            
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        return False

def main():
    print("🧪 TESTE RÁPIDO DO COMPRASNET DOWNLOADER")
    print("=" * 50)
    
    # Verificar diretório
    base_dir = Path(r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\LICITACAO")
    print(f"📁 Diretório alvo: {base_dir}")
    
    # Instalar dependências
    if not instalar_dependencias():
        return
    
    # Testar download
    if testar_download():
        print("\n🎉 TESTE CONCLUÍDO COM SUCESSO!")
        print("🎯 Use o arquivo comprasnet_downloader_windows.py para downloads futuros")
    else:
        print("\n❌ TESTE FALHOU!")
        print("💡 Verifique conexão com internet e permissões de pasta")

if __name__ == "__main__":
    main()