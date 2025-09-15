"""
TESTE DO SISTEMA - VERIFICAÇÃO DE INTEGRIDADE
=============================================

Script para testar se todos os caminhos, arquivos e dependências estão corretos
antes de executar o pipeline principal.

Autor: arte_comercial
Data: 2025
"""

import os
import sys
import pandas as pd
from pathlib import Path

def test_paths():
    """Testa se todos os caminhos estão corretos"""
    print("🔍 TESTANDO CAMINHOS...")
    
    base_dir = r"C:\Users\pietr\OneDrive\.vscode\arte_"
    downloads_dir = os.path.join(base_dir, "DOWNLOADS")
    
    paths_to_test = [
        (base_dir, "Diretório base"),
        (downloads_dir, "Diretório DOWNLOADS"),
        (os.path.join(downloads_dir, "EDITAIS"), "Diretório EDITAIS"),
        (os.path.join(downloads_dir, "ORCAMENTOS"), "Diretório ORCAMENTOS"),
        (os.path.join(downloads_dir, "PRODUTOS"), "Diretório PRODUTOS"),
        (os.path.join(downloads_dir, "RESULTADO_metadados"), "Diretório RESULTADO_metadados"),
    ]
    
    all_good = True
    for path, description in paths_to_test:
        if os.path.exists(path):
            print(f"✅ {description}: {path}")
        else:
            print(f"❌ {description}: {path} - NÃO ENCONTRADO")
            all_good = False
    
    return all_good

def test_files():
    """Testa se os arquivos principais existem"""
    print("\n📁 TESTANDO ARQUIVOS...")
    
    base_dir = r"C:\Users\pietr\OneDrive\.vscode\arte_"
    downloads_dir = os.path.join(base_dir, "DOWNLOADS")
    
    files_to_test = [
        (os.path.join(base_dir, "EDITAIS", "master.xlsx"), "master.xlsx"),
        (os.path.join(downloads_dir, "summary.xlsx"), "summary.xlsx"),
        (os.path.join(downloads_dir, "livro_razao.xlsx"), "livro_razao.xlsx"),
        (os.path.join(downloads_dir, "PRODUTOS", "base_produtos.xlsx"), "produtos_o4-mini.xlsx"),
        (os.path.join(downloads_dir, "RESULTADO_metadados", "categoria_sonnet.xlsx"), "categoria_sonnet.xlsx"),
    ]
    
    all_good = True
    for file_path, description in files_to_test:
        if os.path.exists(file_path):

            try:
                # Tenta abrir o arquivo Excel
                df = pd.read_excel(file_path)
                print(f"✅ {description}: {len(df)} linhas")
            except Exception as e:
                print(f"⚠️ {description}: Arquivo existe mas não pode ser lido - {e}")
        else:
            print(f"❌ {description}: NÃO ENCONTRADO")
            all_good = False
    
    return all_good

def test_scripts():
    """Testa se os scripts principais existem"""
    print("\n🐍 TESTANDO SCRIPTS...")
    
    base_dir = r"C:\Users\pietr\OneDrive\.vscode\arte_"
    scripts_dir = os.path.join(base_dir, "arte_code")
    
    scripts_to_test = [
        (os.path.join(scripts_dir, "nipsey.py"), "Orquestrador principal"),
        (os.path.join(scripts_dir, "arte_orquestra.py"), "Download de editais"),
        (os.path.join(scripts_dir, "arte_metadados.py"), "Processamento de metadados"),
        (os.path.join(scripts_dir, "arte_heavy.py"), "Matching de produtos"),
    ]
    
    all_good = True
    for script_path, description in scripts_to_test:
        if os.path.exists(script_path):
            
            print(f"✅ {description}: {script_path}")
        else:
            print(f"❌ {description}: NÃO ENCONTRADO")
            all_good = False
    
    return all_good

def test_env():
    """Testa se o arquivo .env existe"""
    print("\n🔐 TESTANDO CONFIGURAÇÃO...")
    
    base_dir = r"C:\Users\pietr\OneDrive\.vscode\arte_"
    env_file = os.path.join(base_dir, ".env")
    
    if os.path.exists(env_file):
        print(f"✅ Arquivo .env encontrado: {env_file}")
        
        # Verifica se contém a API key
        try:
            with open(env_file, 'r') as f:
                content = f.read()
                if 'GOOGLE_API_KEY' in content:
                    print("✅ GOOGLE_API_KEY encontrada no .env")
                    return True
                else:
                    print("⚠️ GOOGLE_API_KEY não encontrada no .env")
                    return False
        except Exception as e:
            print(f"❌ Erro ao ler .env: {e}")
            return False
    else:
        print(f"❌ Arquivo .env não encontrado: {env_file}")
        return False

def test_dependencies():
    """Testa se as dependências principais estão instaladas"""
    print("\n📦 TESTANDO DEPENDÊNCIAS...")
    
    dependencies = [
        ('pandas', 'pandas'),
        ('openpyxl', 'openpyxl'),
        ('selenium', 'selenium'),
        ('fitz', 'PyMuPDF'),
        ('google.generativeai', 'google-generativeai'),
        ('dotenv', 'python-dotenv'),
        ('requests', 'requests'),
        ('bs4', 'beautifulsoup4'),
    ]
    
    all_good = True
    for module_name, package_name in dependencies:
        try:
            __import__(module_name)
            print(f"✅ {package_name}")
        except ImportError:
            print(f"❌ {package_name} - NÃO INSTALADO")
            all_good = False
    
    return all_good

def main():
    """Função principal de teste"""
    print("="*60)
    print("TESTE DE INTEGRIDADE DO SISTEMA ARTE")
    print("="*60)
    
    tests = [
        ("Caminhos", test_paths),
        ("Arquivos", test_files),
        ("Scripts", test_scripts),
        ("Configuração", test_env),
        ("Dependências", test_dependencies),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Erro no teste {test_name}: {e}")
            results.append((test_name, False))
    
    # Resumo final
    print("\n" + "="*60)
    print("📊 RESUMO DOS TESTES")
    print("="*60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSOU" if result else "❌ FALHOU"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nResultado: {passed}/{total} testes passaram")
    
    if passed == total:
        print("\n🎉 SISTEMA PRONTO PARA USO!")
        print("Execute: python arte_code/nipsey.py")
    else:
        print("\n⚠️ ALGUNS PROBLEMAS ENCONTRADOS")
        print("Corrija os problemas antes de executar o pipeline")
    
    return passed == total

if __name__ == "__main__":
    main()
