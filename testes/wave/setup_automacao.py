"""
Script de configuração para automação Wavecode
Instala dependências e configura o ambiente
"""

import subprocess
import sys
import os

def install_requirements():
    """Instala as dependências necessárias"""
    print("Instalando dependências...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependências instaladas com sucesso!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao instalar dependências: {e}")
        return False

def install_chromedriver():
    """Instala o ChromeDriver automaticamente"""
    print("Configurando ChromeDriver...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "webdriver-manager"])
        
        # Criar script para configurar ChromeDriver
        setup_code = '''
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.chrome.service import Service

# Baixar e configurar ChromeDriver
driver_path = ChromeDriverManager().install()
print(f"ChromeDriver instalado em: {driver_path}")
'''
        
        exec(setup_code)
        print("✅ ChromeDriver configurado com sucesso!")
        return True
    except Exception as e:
        print(f"❌ Erro ao configurar ChromeDriver: {e}")
        print("Você pode baixar manualmente em: https://chromedriver.chromium.org/")
        return False

def create_directory():
    """Cria o diretório de download se não existir"""
    download_dir = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\TESTE"
    try:
        os.makedirs(download_dir, exist_ok=True)
        print(f"✅ Diretório criado/verificado: {download_dir}")
        return True
    except Exception as e:
        print(f"❌ Erro ao criar diretório: {e}")
        return False

def main():
    """Função principal de configuração"""
    print("=== Configuração da Automação Wavecode ===")
    print()
    
    success = True
    
    # Instalar dependências
    if not install_requirements():
        success = False
    
    # Configurar ChromeDriver
    if not install_chromedriver():
        success = False
    
    # Criar diretório
    if not create_directory():
        success = False
    
    print("\n" + "="*50)
    if success:
        print("✅ Configuração concluída com sucesso!")
        print("\nPara executar a automação, use:")
        print("python automacao_wavecode.py")
    else:
        print("❌ Configuração falhou. Verifique os erros acima.")
    
    print("\n📝 Notas importantes:")
    print("1. Certifique-se de que o Google Chrome está instalado")
    print("2. Verifique se as credenciais no código estão corretas")
    print("3. O diretório de download será criado automaticamente")

if __name__ == "__main__":
    main()
