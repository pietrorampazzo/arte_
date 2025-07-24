"""
Automação para download de documentos do Portal Wavecode - VERSÃO HTML
Autor: Assistente IA
Data: 18/07/2025

Esta versão usa análise HTML direta com BeautifulSoup para resolver
problemas de detecção de elementos de forma mais robusta.
"""

import os
import time
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import requests
from urllib.parse import urljoin, urlparse

class WavecodeHTMLAutomation:
    def __init__(self, download_dir=r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\TESTE", debug=True):
        """
        Inicializa a automação do Wavecode com análise HTML
        
        Args:
            download_dir (str): Diretório onde os arquivos serão salvos
            debug (bool): Ativa modo debug com logs detalhados
        """
        self.download_dir = download_dir
        self.base_url = "https://app2.wavecode.com.br/"
        self.login_email = "pietromrampazzo@gmail.com"
        self.login_password = "Piloto@314"
        self.driver = None
        self.wait = None
        self.debug = debug
        
        # Criar diretório se não existir
        os.makedirs(self.download_dir, exist_ok=True)
        
    def log(self, message):
        """Log com timestamp"""
        if self.debug:
            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}] {message}")
        
    def setup_driver(self):
        """Configura o driver do Chrome com opções otimizadas"""
        self.log("Configurando Chrome WebDriver...")
        
        chrome_options = Options()
        
        # Configurações de download
        prefs = {
            "download.default_directory": self.download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "profile.default_content_settings.popups": 0,
            "profile.default_content_setting_values.notifications": 2
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        # Flags para resolver erros de GPU e melhorar estabilidade
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-gpu-sandbox")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        chrome_options.add_argument("--disable-renderer-backgrounding")
        chrome_options.add_argument("--disable-features=TranslateUI")
        chrome_options.add_argument("--disable-ipc-flooding-protection")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        
        # Configurações anti-detecção
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Configurar user agent
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        try:
            # Configurar ChromeDriver automaticamente
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Scripts anti-detecção
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            
            self.wait = WebDriverWait(self.driver, 15)
            self.log("Chrome WebDriver configurado com sucesso!")
            
        except Exception as e:
            self.log(f"Erro ao configurar WebDriver: {str(e)}")
            raise
    
    def get_page_html(self):
        """Obtém o HTML da página atual"""
        try:
            return self.driver.page_source
        except Exception as e:
            self.log(f"Erro ao obter HTML da página: {str(e)}")
            return None
    
    def parse_html(self, html):
        """Analisa HTML com BeautifulSoup"""
        try:
            return BeautifulSoup(html, 'html.parser')
        except Exception as e:
            self.log(f"Erro ao analisar HTML: {str(e)}")
            return None
    
    def find_element_by_html_analysis(self, soup, element_type):
        """
        Encontra elementos usando análise HTML direta
        
        Args:
            soup: Objeto BeautifulSoup
            element_type: Tipo do elemento ('email', 'password', 'login_button')
        
        Returns:
            dict: Informações do elemento encontrado
        """
        try:
            if element_type == 'email':
                # Procurar campo de email
                selectors = [
                    {'attr': 'data-testid', 'value': 'inputEmail'},
                    {'attr': 'id', 'value': 'username'},
                    {'attr': 'type', 'value': 'text', 'placeholder': 'email'},
                    {'attr': 'placeholder', 'value': 'email@email.com...'}
                ]
                
                for selector in selectors:
                    if 'placeholder' in selector and selector['attr'] == 'type':
                        # Busca especial para type + placeholder
                        element = soup.find('input', {'type': selector['value']})
                        if element and 'email' in element.get('placeholder', '').lower():
                            return self.extract_element_info(element, 'email')
                    else:
                        element = soup.find('input', {selector['attr']: selector['value']})
                        if element:
                            return self.extract_element_info(element, 'email')
            
            elif element_type == 'password':
                # Procurar campo de senha
                selectors = [
                    {'attr': 'data-testid', 'value': 'password'},
                    {'attr': 'id', 'value': 'password'},
                    {'attr': 'type', 'value': 'password'},
                    {'attr': 'placeholder', 'value': '********'}
                ]
                
                for selector in selectors:
                    element = soup.find('input', {selector['attr']: selector['value']})
                    if element:
                        return self.extract_element_info(element, 'password')
            
            elif element_type == 'login_button':
                # Procurar botão de login
                selectors = [
                    {'tag': 'button', 'attr': 'data-testid', 'value': 'id-button'},
                    {'tag': 'button', 'class': 'sc-aXZVg'},
                    {'tag': 'button', 'text': 'ACESSAR'},
                    {'tag': 'span', 'class': 'text', 'text': 'ACESSAR'}
                ]
                
                for selector in selectors:
                    if 'text' in selector:
                        if selector['tag'] == 'span':
                            # Procurar span com texto e pegar o botão pai
                            span = soup.find('span', string=selector['text'])
                            if span:
                                button = span.find_parent('button')
                                if button:
                                    return self.extract_element_info(button, 'login_button')
                        else:
                            # Procurar botão que contenha o texto
                            button = soup.find('button', string=selector['text'])
                            if button:
                                return self.extract_element_info(button, 'login_button')
                    else:
                        element = soup.find(selector['tag'], {selector['attr']: selector['value']})
                        if element:
                            return self.extract_element_info(element, 'login_button')
            
            return None
            
        except Exception as e:
            self.log(f"Erro ao buscar elemento {element_type}: {str(e)}")
            return None
    
    def extract_element_info(self, element, element_type):
        """Extrai informações úteis de um elemento HTML"""
        try:
            info = {
                'tag': element.name,
                'type': element_type,
                'attributes': dict(element.attrs),
                'text': element.get_text(strip=True) if element.get_text(strip=True) else None
            }
            
            # Gerar seletores CSS possíveis
            selectors = []
            
            # Por ID
            if element.get('id'):
                selectors.append(f"#{element['id']}")
            
            # Por data-testid
            if element.get('data-testid'):
                selectors.append(f"[data-testid='{element['data-testid']}']")
            
            # Por classe
            if element.get('class'):
                classes = ' '.join(element['class'])
                selectors.append(f".{element['class'][0]}")
            
            # Por tipo
            if element.get('type'):
                selectors.append(f"input[type='{element['type']}']")
            
            # Por placeholder
            if element.get('placeholder'):
                selectors.append(f"[placeholder='{element['placeholder']}']")
            
            info['selectors'] = selectors
            
            self.log(f"Elemento {element_type} encontrado: {selectors[0] if selectors else 'sem seletor'}")
            return info
            
        except Exception as e:
            self.log(f"Erro ao extrair informações do elemento: {str(e)}")
            return None
    
    def find_selenium_element(self, element_info):
        """Encontra elemento usando Selenium baseado nas informações HTML"""
        try:
            for selector in element_info['selectors']:
                try:
                    if selector.startswith('#'):
                        # Por ID
                        element = self.driver.find_element(By.ID, selector[1:])
                        return element
                    elif selector.startswith('[data-testid'):
                        # Por data-testid
                        testid = selector.split("'")[1]
                        element = self.driver.find_element(By.CSS_SELECTOR, f"[data-testid='{testid}']")
                        return element
                    elif selector.startswith('.'):
                        # Por classe
                        element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        return element
                    else:
                        # Seletor CSS genérico
                        element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        return element
                except NoSuchElementException:
                    continue
            
            self.log(f"Nenhum seletor funcionou para {element_info['type']}")
            return None
            
        except Exception as e:
            self.log(f"Erro ao encontrar elemento com Selenium: {str(e)}")
            return None
    
    def login(self):
        """Realiza o login no portal Wavecode usando análise HTML"""
        try:
            self.log("Acessando portal Wavecode...")
            self.driver.get(self.base_url)
            
            # Aguardar página carregar completamente
            time.sleep(3)
            
            # Obter HTML da página
            self.log("Analisando HTML da página...")
            html = self.get_page_html()
            if not html:
                self.log("❌ Não foi possível obter HTML da página")
                return False
            
            # Analisar HTML com BeautifulSoup
            soup = self.parse_html(html)
            if not soup:
                self.log("❌ Não foi possível analisar HTML")
                return False
            
            # Encontrar elementos usando análise HTML
            self.log("Procurando campo de email...")
            email_info = self.find_element_by_html_analysis(soup, 'email')
            if not email_info:
                self.log("❌ Campo de email não encontrado")
                return False
            
            self.log("Procurando campo de senha...")
            password_info = self.find_element_by_html_analysis(soup, 'password')
            if not password_info:
                self.log("❌ Campo de senha não encontrado")
                return False
            
            self.log("Procurando botão de login...")
            button_info = self.find_element_by_html_analysis(soup, 'login_button')
            if not button_info:
                self.log("❌ Botão de login não encontrado")
                return False
            
            # Encontrar elementos com Selenium
            self.log("Localizando elementos com Selenium...")
            email_element = self.find_selenium_element(email_info)
            password_element = self.find_selenium_element(password_info)
            button_element = self.find_selenium_element(button_info)
            
            if not email_element:
                self.log("❌ Elemento de email não encontrado com Selenium")
                return False
            
            if not password_element:
                self.log("❌ Elemento de senha não encontrado com Selenium")
                return False
            
            if not button_element:
                self.log("❌ Elemento de botão não encontrado com Selenium")
                return False
            
            # Preencher credenciais
            self.log("Preenchendo credenciais...")
            
            # Limpar e preencher email
            email_element.clear()
            time.sleep(0.5)
            email_element.send_keys(self.login_email)
            
            time.sleep(1)
            
            # Limpar e preencher senha
            password_element.clear()
            time.sleep(0.5)
            password_element.send_keys(self.login_password)
            
            time.sleep(1)
            
            # Fazer login
            self.log("Clicando no botão de login...")
            current_url = self.driver.current_url
            button_element.click()
            
            # Aguardar resposta do login
            self.log("Aguardando resposta do login...")
            time.sleep(5)
            
            # Verificar se login foi bem-sucedido
            return self.check_login_success(current_url)
            
        except Exception as e:
            self.log(f"❌ Erro durante login: {str(e)}")
            return False
    
    def check_login_success(self, original_url):
        """Verifica se o login foi bem-sucedido"""
        try:
            current_url = self.driver.current_url
            self.log(f"URL original: {original_url}")
            self.log(f"URL atual: {current_url}")
            
            # Verificar mudança de URL
            if current_url != original_url and "login" not in current_url:
                self.log("✅ Login bem-sucedido - URL mudou")
                return True
            
            # Analisar HTML para verificar login
            html = self.get_page_html()
            if html:
                soup = self.parse_html(html)
                if soup:
                    # Procurar indicadores de erro
                    error_indicators = soup.find_all(string=re.compile(r'inválid|erro|error', re.IGNORECASE))
                    if error_indicators:
                        self.log(f"❌ Erro de login detectado: {error_indicators[0]}")
                        return False
                    
                    # Procurar indicadores de sucesso
                    success_indicators = soup.find_all(['a', 'button'], string=re.compile(r'editais|dashboard|menu', re.IGNORECASE))
                    if success_indicators:
                        self.log("✅ Login bem-sucedido - Elementos do dashboard encontrados")
                        return True
            
            # Aguardar mais tempo e verificar novamente
            time.sleep(3)
            final_url = self.driver.current_url
            if "login" not in final_url:
                self.log("✅ Login bem-sucedido - Não está mais na página de login")
                return True
            
            self.log("❌ Login falhou - Ainda na página de login")
            return False
            
        except Exception as e:
            self.log(f"❌ Erro ao verificar login: {str(e)}")
            return False

    def wait_for_editais_page_load(self):
        """Aguarda o carregamento completo da página de editais"""
        try:
            self.log("Aguardando carregamento da página de editais...")
            
            # Lista de indicadores que a página de editais carregou
            load_indicators = [
                # Elementos típicos da página de editais
                (By.XPATH, "//*[contains(text(), 'UASG')]"),
                (By.XPATH, "//*[contains(text(), 'Edital')]"),
                (By.XPATH, "//*[contains(text(), 'Número')]"),
                (By.CSS_SELECTOR, "[class*='edital']"),
                (By.CSS_SELECTOR, "[class*='prospect']"),
                (By.CSS_SELECTOR, "[class*='card']"),
                (By.CSS_SELECTOR, "table"),
                (By.CSS_SELECTOR, "[class*='list']"),
                (By.CSS_SELECTOR, "[class*='grid']")
            ]
            
            # Tentar aguardar qualquer um dos indicadores
            for by, selector in load_indicators:
                try:
                    element = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((by, selector))
                    )
                    if element:
                        self.log("✅ Página de editais carregada!")
                        return True
                except TimeoutException:
                    continue
            
            # Se nenhum indicador específico foi encontrado, aguardar um tempo mínimo
            self.log("⚠️ Indicadores específicos não encontrados, aguardando tempo mínimo...")
            time.sleep(5)
            return True
            
        except Exception as e:
            self.log(f"Erro ao aguardar carregamento: {str(e)}")
            return True  # Continuar mesmo com erro

    def navigate_to_editais(self):
        """Navega para a seção de editais usando análise HTML"""
        try:
            self.log("Navegando para seção de editais...")
            
            # Aguardar carregamento da página de editais
            self.wait_for_editais_page_load()
            time.sleep(2)
            
            # Lista de seletores baseados no HTML fornecido
            editais_selectors = [
                # Seletor baseado no HTML fornecido - container principal
                ".sc-dorvvM.ioFjWB",
                # Seletor pelo texto do elemento
                "//p[text()='Editais']",
                # Seletor mais específico usando a estrutura completa
                ".sc-dorvvM.ioFjWB .title .sc-elDIKY.bAJZNH",
                # XPath que busca pelo texto "Editais"
                "//span[@class='title']//p[text()='Editais']",
                # XPath pelo elemento pai que contém o ícone e o texto
                "//div[contains(@class, 'sc-dorvvM') and contains(@class, 'ioFjWB')]",
                # Fallback - buscar qualquer elemento com texto "Editais"
                "//*[contains(text(), 'Editais')]",
                # Seletor genérico para links de editais
                "a[href*='editais']",
                # Seletor por data-testid se existir
                "[data-testid*='editais']"
            ]
            
            # Tentar cada seletor
            for selector in editais_selectors:
                try:
                    self.log(f"Tentando seletor: {selector}")
                    
                    if selector.startswith("//") or selector.startswith("//*"):
                        # XPath
                        element = self.wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    else:
                        # CSS Selector
                        element = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                    
                    if element:
                        # Scroll para o elemento
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                        time.sleep(1)
                        
                        # Tentar clicar
                        try:
                            element.click()
                        except Exception:
                            # Se click normal falhar, usar JavaScript
                            self.driver.execute_script("arguments[0].click();", element)
                        
                        time.sleep(3)
                        
                        # Verificar se a navegação foi bem-sucedida
                        current_url = self.driver.current_url
                        if "editais" in current_url.lower() or self.check_editais_page():
                            self.log("✅ Navegação para editais realizada!")
                            return True
                
                except TimeoutException:
                    self.log(f"Seletor {selector} não encontrado")
                    continue
                except Exception as e:
                    self.log(f"Erro com seletor {selector}: {str(e)}")
                    continue
            
            # Fallback: tentar encontrar por análise HTML
            self.log("Tentando fallback com análise HTML...")
            return self.navigate_to_editais_html_fallback()
            
        except Exception as e:
            self.log(f"❌ Erro ao navegar para editais: {str(e)}")
            return False

    def check_editais_page(self):
        """Verifica se está na página de editais"""
        try:
            # Verificar se existem elementos típicos da página de editais
            editais_indicators = [
                "//h1[contains(text(), 'Editais')]",
                "//h2[contains(text(), 'Editais')]",
                "//*[contains(@class, 'edital')]",
                "//*[contains(text(), 'UASG')]",
                "//*[contains(text(), 'Número do Edital')]"
            ]
            
            for indicator in editais_indicators:
                try:
                    element = self.driver.find_element(By.XPATH, indicator)
                    if element:
                        return True
                except NoSuchElementException:
                    continue
            
            return False
            
        except Exception:
            return False

    def navigate_to_editais_html_fallback(self):
        """Fallback usando análise HTML direta"""
        try:
            html = self.get_page_html()
            if not html:
                return False
            
            soup = self.parse_html(html)
            if not soup:
                return False
            
            # Procurar elementos que contenham "Editais"
            editais_elements = soup.find_all(string=re.compile(r'editais', re.IGNORECASE))
            
            for text_element in editais_elements:
                parent = text_element.parent
                while parent and parent.name not in ['a', 'button', 'div']:
                    parent = parent.parent
                
                if parent:
                    # Tentar gerar seletores únicos
                    selectors = []
                    
                    if parent.get('id'):
                        selectors.append(f"#{parent['id']}")
                    
                    if parent.get('class'):
                        classes = '.'.join(parent['class'])
                        selectors.append(f".{classes}")
                    
                    # Tentar encontrar com Selenium
                    for selector in selectors:
                        try:
                            element = self.driver.find_element(By.CSS_SELECTOR, selector)
                            if element and element.is_displayed():
                                self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                                time.sleep(1)
                                element.click()
                                time.sleep(3)
                                
                                if self.check_editais_page():
                                    self.log("✅ Navegação para editais realizada via fallback!")
                                    return True
                        except Exception:
                            continue
            
            return False
            
        except Exception as e:
            self.log(f"Erro no fallback HTML: {str(e)}")
            return False

    def extract_document_info_html(self, row_html):
        """Extrai informações UASG e Edital usando análise HTML"""
        try:
            soup = BeautifulSoup(row_html, 'html.parser')
            row_text = soup.get_text()
            
            self.log(f"Analisando linha: {row_text[:100]}...")
            
            # Padrões para extrair UASG e Edital
            uasg_patterns = [
                r'UASG[:\s]*(\d+)',
                r'U[:\s]*(\d+)',
                r'Unidade[:\s]*(\d+)',
                r'(\d{6,})'
            ]
            
            edital_patterns = [
                r'Edital[:\s]*(\d+)',
                r'N[:\s]*(\d+)',
                r'Número[:\s]*(\d+)',
                r'(\d{1,5})'
            ]
            
            uasg = None
            edital = None
            
            # Tentar extrair UASG
            for pattern in uasg_patterns:
                match = re.search(pattern, row_text, re.IGNORECASE)
                if match:
                    uasg = match.group(1)
                    break
            
            # Tentar extrair Edital
            for pattern in edital_patterns:
                match = re.search(pattern, row_text, re.IGNORECASE)
                if match:
                    edital = match.group(1)
                    break
            
            # Fallback: usar números sequenciais
            if not uasg:
                uasg = "000000"
            if not edital:
                edital = str(int(time.time()) % 10000)
            
            self.log(f"Informações extraídas - UASG: {uasg}, Edital: {edital}")
            return uasg, edital
            
        except Exception as e:
            self.log(f"❌ Erro ao extrair informações: {str(e)}")
            return "000000", str(int(time.time()) % 10000)

    def process_editais_page_html(self, page_num):
        """Processa uma página de editais usando análise HTML"""
        try:
            self.log(f"Processando página {page_num}...")
            time.sleep(3)
            
            # Aguardar carregamento da página
            time.sleep(2)
            
            processed_count = 0
            
            # Procurar todos os botões de download na página
            download_buttons = self.find_download_buttons()
            
            if not download_buttons:
                self.log("❌ Nenhum botão de download encontrado na página")
                return False
            
            self.log(f"Encontrados {len(download_buttons)} botões de download")
            
            # Processar cada botão de download
            for i, button in enumerate(download_buttons):
                try:
                    # Extrair informações do edital
                    uasg, edital = self.extract_edital_info_from_context(button, i)
                    
                    # Fazer download
                    success = self.download_document_html(button, uasg, edital)
                    if success:
                        processed_count += 1
                        self.log(f"✅ Download {i+1} concluído")
                    else:
                        self.log(f"❌ Falha no download {i+1}")
                    
                    # Aguardar entre downloads
                    time.sleep(2)
                    
                except Exception as e:
                    self.log(f"Erro processando download {i+1}: {str(e)}")
                    continue
            
            self.log(f"✅ Página {page_num}: {processed_count} documentos processados")
            return processed_count > 0
            
        except Exception as e:
            self.log(f"❌ Erro processando página {page_num}: {str(e)}")
            return False

    def find_download_buttons(self):
        """Encontra todos os botões de download na página"""
        try:
            download_buttons = []
            
            # Lista de seletores para encontrar botões de download
            download_selectors = [
                # Seletor específico baseado no HTML fornecido
                "#app-content-wrapper > div > div > div.sc-iMWBWc.jexXsF > div.sc-fvtEUL.iStkcC > div > div.wrapper-header > div.action-header > svg:nth-child(1)",
                # Seletores mais genéricos
                "svg[viewBox='0 0 256 256'][style*='cursor: pointer']",
                ".action-header svg:first-child",
                ".wrapper-header .action-header svg",
                "svg[stroke='currentColor'][fill='currentColor']",
                # Fallback por estrutura
                ".sc-fvtEUL .action-header svg",
                ".sc-iMWBWc .action-header svg"
            ]
            
            # Tentar cada seletor
            for selector in download_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        self.log(f"Encontrados {len(elements)} elementos com seletor: {selector}")
                        download_buttons.extend(elements)
                        break  # Se encontrou elementos, usar este seletor
                except Exception as e:
                    self.log(f"Erro com seletor {selector}: {str(e)}")
                    continue
            
            # Remover duplicatas mantendo ordem
            unique_buttons = []
            for button in download_buttons:
                if button not in unique_buttons:
                    unique_buttons.append(button)
            
            return unique_buttons
            
        except Exception as e:
            self.log(f"Erro ao encontrar botões de download: {str(e)}")
            return []

    def extract_edital_info_from_context(self, download_button, index):
        """Extrai informações UASG e Edital do contexto do botão de download"""
        try:
            # Tentar encontrar o container pai do edital
            parent_container = download_button.find_element(By.XPATH, "./ancestor::div[contains(@class, 'sc-fvtEUL') or contains(@class, 'sc-iMWBWc')]")
            
            if parent_container:
                container_text = parent_container.text
                self.log(f"Texto do container {index+1}: {container_text[:100]}...")
                
                # Padrões para extrair UASG e Edital
                uasg_patterns = [
                    r'UASG[:\s]*(\d+)',
                    r'Unidade[:\s]*(\d+)',
                    r'(\d{6,})'  # Números com 6+ dígitos
                ]
                
                edital_patterns = [
                    r'Edital[:\s]*(\d+)',
                    r'Número[:\s]*(\d+)',
                    r'N[°º][:\s]*(\d+)',
                    r'(\d{1,5})'  # Números com 1-5 dígitos
                ]
                
                uasg = None
                edital = None
                
                # Tentar extrair UASG
                for pattern in uasg_patterns:
                    match = re.search(pattern, container_text, re.IGNORECASE)
                    if match:
                        uasg = match.group(1)
                        break
                
                # Tentar extrair Edital
                for pattern in edital_patterns:
                    match = re.search(pattern, container_text, re.IGNORECASE)
                    if match:
                        edital = match.group(1)
                        break
                
                # Se não encontrou, usar valores padrão
                if not uasg:
                    uasg = f"999{index:03d}"  # 999001, 999002, etc.
                if not edital:
                    edital = f"{index+1:04d}"  # 0001, 0002, etc.
                
                self.log(f"Informações extraídas - UASG: {uasg}, Edital: {edital}")
                return uasg, edital
            
        except Exception as e:
            self.log(f"Erro ao extrair informações do contexto: {str(e)}")
        
        # Fallback: usar índice
        uasg = f"999{index:03d}"
        edital = f"{index+1:04d}"
        self.log(f"Usando valores fallback - UASG: {uasg}, Edital: {edital}")
        return uasg, edital

    def download_document_html(self, download_element, uasg, edital):
        """Faz download de um documento"""
        try:
            # Verificar se o elemento está visível e clicável
            if not download_element.is_displayed() or not download_element.is_enabled():
                self.log(f"❌ Elemento de download não está disponível")
                return False
            
            files_before = set(os.listdir(self.download_dir))
            
            # Scroll para o elemento
            self.driver.execute_script("arguments[0].scrollIntoView(true);", download_element)
            time.sleep(1)
            
            self.log(f"Iniciando download para UASG {uasg}, Edital {edital}...")
            
            # Tentar clicar no elemento
            try:
                download_element.click()
            except Exception:
                # Se click normal falhar, usar JavaScript
                self.driver.execute_script("arguments[0].click();", download_element)
            
            # Aguardar download
            max_wait = 30  # Reduzido para 30 segundos
            waited = 0
            check_interval = 2
            
            while waited < max_wait:
                time.sleep(check_interval)
                waited += check_interval
                
                files_after = set(os.listdir(self.download_dir))
                new_files = files_after - files_before
                
                if new_files:
                    for new_file in new_files:
                        # Ignorar arquivos temporários
                        if (new_file.endswith('.tmp') or 
                            new_file.endswith('.crdownload') or 
                            new_file.endswith('.part')):
                            continue
                        
                        file_path = os.path.join(self.download_dir, new_file)
                        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                            _, ext = os.path.splitext(new_file)
                            if not ext:
                                ext = '.pdf'  # Assumir PDF se não tiver extensão
                            
                            new_name = f"U_{uasg}_N_{edital}{ext}"
                            new_path = os.path.join(self.download_dir, new_name)
                            
                            # Evitar sobrescrever arquivos existentes
                            counter = 1
                            while os.path.exists(new_path):
                                name_part = f"U_{uasg}_N_{edital}_{counter}"
                                new_path = os.path.join(self.download_dir, f"{name_part}{ext}")
                                counter += 1
                            
                            try:
                                os.rename(file_path, new_path)
                                self.log(f"✅ Arquivo baixado e renomeado: {os.path.basename(new_path)}")
                                return True
                            except Exception as e:
                                self.log(f"❌ Erro ao renomear arquivo: {str(e)}")
                                return False
                
                if waited % 10 == 0:
                    self.log(f"Aguardando download... ({waited}s/{max_wait}s)")
            
            self.log(f"❌ Timeout aguardando download ({max_wait}s)")
            return False
            
        except Exception as e:
            self.log(f"❌ Erro durante download: {str(e)}")
            return False

    def navigate_to_next_page_html(self, current_page):
        """Navega para próxima página usando análise HTML"""
        try:
            self.log(f"Tentando navegar para página {current_page + 1}...")
            
            html = self.get_page_html()
            if not html:
                return False
            
            soup = self.parse_html(html)
            if not soup:
                return False
            
            # Procurar elementos de paginação
            next_elements = []
            
            # Buscar por texto
            next_texts = soup.find_all(string=re.compile(rf'{current_page + 1}|próxima|next', re.IGNORECASE))
            for text in next_texts:
                parent = text.parent
                if parent and parent.name in ['a', 'button']:
                    next_elements.append(parent)
            
            # Buscar por classes
            next_classes = soup.find_all(['a', 'button'], class_=re.compile(r'next|pagination', re.IGNORECASE))
            next_elements.extend(next_classes)
            
            if next_elements:
                for element in next_elements:
                    try:
                        # Gerar seletores
                        selectors = []
                        
                        if element.get('id'):
                            selectors.append(f"#{element['id']}")
                        
                        if element.get('class'):
                            selectors.append(f".{element['class'][0]}")
                        
                        if element.get('href'):
                            selectors.append(f"a[href='{element['href']}']")
                        
                        # Tentar encontrar com Selenium
                        for selector in selectors:
                            try:
                                if selector.startswith('#'):
                                    selenium_element = self.driver.find_element(By.ID, selector[1:])
                                else:
                                    selenium_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                                
                                if selenium_element.is_displayed() and selenium_element.is_enabled():
                                    self.driver.execute_script("arguments[0].scrollIntoView(true);", selenium_element)
                                    time.sleep(1)
                                    selenium_element.click()
                                    time.sleep(3)
                                    self.log(f"✅ Navegou para página {current_page + 1}")
                                    return True
                            except NoSuchElementException:
                                continue
                    
                    except Exception as e:
                        continue
            
            self.log("❌ Não foi possível encontrar botão para próxima página")
            return False
            
        except Exception as e:
            self.log(f"❌ Erro ao navegar para próxima página: {str(e)}")
            return False

    def save_debug_screenshot(self, name):
        """Salva screenshot para debug"""
        try:
            if self.driver and self.debug:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"debug_{name}_{timestamp}.png"
                filepath = os.path.join(self.download_dir, filename)
                self.driver.save_screenshot(filepath)
                self.log(f"📸 Screenshot salvo: {filename}")
        except Exception as e:
            self.log(f"Erro ao salvar screenshot: {str(e)}")

    def run(self):
        """Executa o processo completo de automação com análise HTML"""
        try:
            self.log("=== INICIANDO AUTOMAÇÃO WAVECODE - VERSÃO HTML ===")
            self.log(f"📁 Diretório de download: {self.download_dir}")
            self.log(f"🌐 URL base: {self.base_url}")
            self.log(f"👤 Email: {self.login_email}")
            
            # Configurar driver
            self.setup_driver()
            
            # Fazer login
            self.log("--- FASE 1: LOGIN COM ANÁLISE HTML ---")
            if not self.login():
                self.log("❌ Falha no login. Verifique as credenciais.")
                self.log("🔍 Salvando screenshot para debug...")
                self.save_debug_screenshot("login_failed")
                return False
            
            self.log("✅ Login realizado com sucesso!")
            self.save_debug_screenshot("login_success")
            
            # Navegar para editais
            self.log("--- FASE 2: NAVEGAÇÃO PARA EDITAIS ---")
            if not self.navigate_to_editais():
                self.log("❌ Falha ao navegar para editais.")
                self.log("🔍 Salvando screenshot para debug...")
                self.save_debug_screenshot("navigation_failed")
                return False
            
            self.log("✅ Navegação para editais realizada!")
            self.save_debug_screenshot("editais_page")
            
            # Processar 3 primeiras páginas
            self.log("--- FASE 3: PROCESSAMENTO DE PÁGINAS ---")
            total_processed = 0
            
            for page in range(1, 4):
                self.log(f"\n>>> Processando página {page} <<<")
                
                success = self.process_editais_page_html(page)
                if success:
                    total_processed += 1
                
                # Navegar para próxima página (exceto na última)
                if page < 3:
                    if not self.navigate_to_next_page_html(page):
                        self.log(f"❌ Não foi possível navegar para página {page + 1}")
                        break
            
            self.log(f"\n=== AUTOMAÇÃO CONCLUÍDA ===")
            self.log(f"✅ {total_processed} páginas processadas com sucesso")
            self.log(f"📁 Arquivos salvos em: {self.download_dir}")
            
            return True
            
        except Exception as e:
            self.log(f"❌ Erro durante execução: {str(e)}")
            return False
            
        finally:
            if self.driver:
                self.log("Fechando navegador...")
                try:
                    self.driver.quit()
                except:
                    pass

def main():
    """Função principal com interface melhorada"""
    print("=" * 70)
    print("🤖 AUTOMAÇÃO PORTAL WAVECODE - VERSÃO HTML ANALYSIS")
    print("=" * 70)
    print()
    print("📋 Este script usa análise HTML direta para:")
    print("   1. Fazer login no portal Wavecode")
    print("   2. Navegar para seção de editais")
    print("   3. Baixar documentos das 3 primeiras páginas")
    print("   4. Renomear arquivos conforme padrão U_xxx_N_yyy")
    print()
    print("🔧 Tecnologias utilizadas:")
    print("   ✅ BeautifulSoup para análise HTML")
    print("   ✅ Selenium para automação")
    print("   ✅ Múltiplos seletores baseados em HTML")
    print("   ✅ Detecção robusta de elementos")
    print("   ✅ Logs detalhados para debug")
    print()
    
    # Confirmar execução
    response = input("🚀 Deseja continuar? (s/n): ").lower().strip()
    if response != 's':
        print("❌ Execução cancelada.")
        return
    
    print("\n" + "=" * 70)
    
    # Executar automação
    automation = WavecodeHTMLAutomation(debug=True)
    success = automation.run()
    
    print("\n" + "=" * 70)
    if success:
        print("🎉 AUTOMAÇÃO EXECUTADA COM SUCESSO!")
        print("📁 Verifique os arquivos baixados no diretório especificado.")
    else:
        print("❌ AUTOMAÇÃO FALHOU!")
        print("📝 Verifique os logs acima para identificar o problema.")
        print("💡 A versão HTML oferece melhor detecção de elementos.")
    print("=" * 70)

if __name__ == "__main__":
    main()