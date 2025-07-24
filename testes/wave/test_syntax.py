"""
Script de teste para validar a sintaxe do código de automação
"""

import ast
import sys

def test_syntax(filename):
    """Testa a sintaxe de um arquivo Python"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Compilar o código para verificar sintaxe
        ast.parse(source)
        print(f"✅ {filename}: Sintaxe válida")
        return True
        
    except SyntaxError as e:
        print(f"❌ {filename}: Erro de sintaxe na linha {e.lineno}: {e.msg}")
        return False
    except Exception as e:
        print(f"❌ {filename}: Erro ao ler arquivo: {e}")
        return False

def test_imports():
    """Testa se as importações necessárias estão disponíveis"""
    print("Testando importações...")
    
    imports_to_test = [
        ("os", "Biblioteca padrão Python"),
        ("time", "Biblioteca padrão Python"),
        ("re", "Biblioteca padrão Python"),
    ]
    
    optional_imports = [
        ("selenium", "Selenium WebDriver"),
        ("webdriver_manager", "WebDriver Manager"),
        ("requests", "Requests HTTP"),
    ]
    
    all_good = True
    
    # Testar importações obrigatórias
    for module, description in imports_to_test:
        try:
            __import__(module)
            print(f"✅ {module}: {description}")
        except ImportError:
            print(f"❌ {module}: {description} - NÃO ENCONTRADO")
            all_good = False
    
    # Testar importações opcionais (que podem ser instaladas)
    for module, description in optional_imports:
        try:
            __import__(module)
            print(f"✅ {module}: {description}")
        except ImportError:
            print(f"⚠️  {module}: {description} - Precisa ser instalado")
    
    return all_good

def main():
    """Função principal de teste"""
    print("=== Teste de Validação do Código ===")
    print()
    
    # Testar sintaxe dos arquivos
    files_to_test = [
        "automacao_wavecode.py",
        "setup_automacao.py"
    ]
    
    syntax_ok = True
    for filename in files_to_test:
        if not test_syntax(filename):
            syntax_ok = False
    
    print()
    
    # Testar importações
    imports_ok = test_imports()
    
    print("\n" + "="*50)
    if syntax_ok and imports_ok:
        print("✅ Todos os testes passaram!")
        print("O código está pronto para execução.")
    else:
        print("❌ Alguns testes falharam.")
        if not syntax_ok:
            print("- Corrija os erros de sintaxe")
        if not imports_ok:
            print("- Execute: python setup_automacao.py")

if __name__ == "__main__":
    main()
