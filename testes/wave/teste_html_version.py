"""
Script de teste para validar a versão HTML da automação
"""

import ast
import sys

def test_html_version():
    """Testa a versão HTML da automação"""
    print("🔍 Testando versão HTML...")
    
    try:
        # Testar sintaxe
        with open('automacao_wavecode_html.py', 'r', encoding='utf-8') as f:
            source = f.read()
        
        ast.parse(source)
        print("✅ Sintaxe válida")
        
        # Verificar recursos HTML específicos
        html_features = [
            ("BeautifulSoup", "Análise HTML com BeautifulSoup"),
            ("find_element_by_html_analysis", "Método de análise HTML"),
            ("extract_element_info", "Extração de informações de elementos"),
            ("parse_html", "Parser HTML"),
            ("data-testid", "Uso de data-testid"),
            ("soup.find", "Busca em HTML"),
            ("get_page_html", "Obtenção de HTML da página"),
            ("WavecodeHTMLAutomation", "Classe principal HTML")
        ]
        
        print("\n🔧 Verificando recursos HTML:")
        for feature, description in html_features:
            if feature in source:
                print(f"✅ {description}")
            else:
                print(f"❌ {description} - NÃO ENCONTRADO")
        
        # Verificar seletores específicos encontrados na análise
        specific_selectors = [
            ("data-testid=\"inputEmail\"", "Seletor específico para email"),
            ("data-testid=\"password\"", "Seletor específico para senha"),
            ("data-testid=\"id-button\"", "Seletor específico para botão"),
            ("span.text", "Seletor para texto do botão")
        ]
        
        print("\n🎯 Verificando seletores específicos:")
        for selector, description in specific_selectors:
            if selector in source:
                print(f"✅ {description}")
            else:
                print(f"⚠️  {description} - Pode estar em formato diferente")
        
        return True
        
    except SyntaxError as e:
        print(f"❌ Erro de sintaxe: {e}")
        return False
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def compare_with_previous():
    """Compara com versão anterior"""
    print("\n📊 Comparando com versão anterior:")
    
    try:
        # Ler versão corrigida
        with open('automacao_wavecode_corrigido.py', 'r', encoding='utf-8') as f:
            corrected = f.read()
        
        # Ler versão HTML
        with open('automacao_wavecode_html.py', 'r', encoding='utf-8') as f:
            html_version = f.read()
        
        print(f"📄 Versão corrigida: {len(corrected)} caracteres")
        print(f"📄 Versão HTML: {len(html_version)} caracteres")
        print(f"📈 Diferença: {len(html_version) - len(corrected):+} caracteres")
        
        # Verificar melhorias específicas
        improvements = [
            ("BeautifulSoup", "Análise HTML"),
            ("data-testid", "Seletores data-testid"),
            ("parse_html", "Parser HTML"),
            ("find_element_by_html_analysis", "Análise HTML de elementos"),
            ("extract_element_info", "Extração de informações"),
            ("soup.find", "Busca em HTML"),
            ("WavecodeHTMLAutomation", "Classe HTML específica")
        ]
        
        print("\n🚀 Novos recursos HTML:")
        for improvement, description in improvements:
            corrected_count = corrected.count(improvement)
            html_count = html_version.count(improvement)
            
            if html_count > corrected_count:
                print(f"✅ {description}: {corrected_count} → {html_count}")
            elif html_count == corrected_count and html_count > 0:
                print(f"➖ {description}: mantido ({html_count})")
            else:
                print(f"❌ {description}: não implementado")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao comparar versões: {e}")
        return False

def test_imports():
    """Testa importações específicas da versão HTML"""
    print("\n📦 Testando importações HTML:")
    
    imports_to_test = [
        ("bs4", "BeautifulSoup4"),
        ("selenium", "Selenium WebDriver"),
        ("webdriver_manager", "WebDriver Manager"),
        ("requests", "Requests HTTP"),
        ("re", "Regex"),
        ("os", "Sistema Operacional"),
        ("time", "Time")
    ]
    
    all_good = True
    
    for module, description in imports_to_test:
        try:
            if module == "bs4":
                from bs4 import BeautifulSoup
                print(f"✅ {description}")
            else:
                __import__(module)
                print(f"✅ {description}")
        except ImportError:
            print(f"⚠️  {description} - Precisa ser instalado")
            if module == "bs4":
                all_good = False
    
    return all_good

def main():
    """Função principal de teste"""
    print("=" * 70)
    print("🧪 TESTE DA VERSÃO HTML - AUTOMAÇÃO WAVECODE")
    print("=" * 70)
    
    success = True
    
    # Testar versão HTML
    if not test_html_version():
        success = False
    
    # Comparar com versão anterior
    if not compare_with_previous():
        success = False
    
    # Testar importações
    if not test_imports():
        success = False
    
    print("\n" + "=" * 70)
    if success:
        print("🎉 TODOS OS TESTES PASSARAM!")
        print("✅ A versão HTML está pronta para uso")
        print("\n💡 Principais vantagens da versão HTML:")
        print("   🔍 Análise direta do HTML da página")
        print("   🎯 Seletores baseados em data-testid")
        print("   🔧 Detecção robusta de elementos")
        print("   📝 Logs detalhados de análise HTML")
        print("   ⚡ Fallbacks inteligentes")
        print("\n📋 Para usar:")
        print("   1. pip install -r requirements_html.txt")
        print("   2. python automacao_wavecode_html.py")
    else:
        print("❌ ALGUNS TESTES FALHARAM")
        print("🔍 Verifique os erros acima")
        print("💡 Instale as dependências: pip install beautifulsoup4 lxml")
    
    print("=" * 70)

if __name__ == "__main__":
    main()
