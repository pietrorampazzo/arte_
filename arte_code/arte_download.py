"""
Automação e download de editais via Wavecode.

Procesossos automatizados:
- Login no Wavecode
- Download de arquivos .zip e .pdf, evitando editais já processados (via livro_razão.xlsx)
- Tratamento de PDFs e extração de itens para Excel
- Consolidação em uma planilha de resumo (summary.xlsx)
- Filtragem de itens relevantes (instrumentos musicais, áudio) para uma planilha master (master.xlsx)
- Criação de cards no Trello APENAS para editais com itens relevantes no master.xlsx

Autor: arte_comercial
Data: 06/09/2025
Versão: 2.0.0 (Fluxo de Trello condicional e Livro Razão)
"""
import os
import time
import re
import zipfile
import shutil
from pathlib import Path
import fitz # PyMuPDF
import pandas as pd
import openpyxl
import requests
from datetime import datetime
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from lxml import html
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager

from datetime import datetime
try:
    from zoneinfo import ZoneInfo  # Py 3.9+
except Exception:
    ZoneInfo = None

# === Configuration ===
BASE_DIR = r"C:\Users\pietr\OneDrive\.vscode\arte_\DOWNLOADS"
DOWNLOAD_DIR = os.path.join(BASE_DIR, "EDITAIS")  # Arquivos baixados vão para EDITAIS
ORCAMENTOS_DIR = os.path.join(BASE_DIR, "EDITAIS", "aba")
LIVRO_RAZAO_PATH = os.path.join(BASE_DIR, "livro_razao.xlsx") # Ledger de todos os editais processados
SUMMARY_EXCEL_PATH = os.path.join(BASE_DIR, "summary.xlsx") # Este é o arquivo com todos os itens dos novos editais
FINAL_MASTER_PATH = os.path.join(BASE_DIR, "master.xlsx") # Este será o arquivo final filtrado

# Palavras-chave para filtro do arte_orcamento
PALAVRAS_CHAVE = [
    r'Instrumento Musical - Sopro', r'Instrumento Musical - Corda',r'Instrumento Musical - Percursão',
    r'Instrumento Musical', r'Peças e acessórios instrumento musical', r'Cabo Rede Computador'
    r'saxofone', r'trompete', r'tuba', r'clarinete', r'óleo lubrificante',r'trompa', r'sax', r'óleos para válvulas',
    r'violão', r'Guitarra', r'Baixo', r'Violino', r'Viola', r'Cavaquinho',r'Bandolim', r'Ukulele', 
    r'Microfone', r'Microfone direcional', r'Suporte microfone', r'Microfone Dinâmico', r'Microfone de Lapela',
    r'Base microfone', r'Pedestal microfone', r'Medusa para microfone', r'Pré-amplificador microfone',
    r'Caixa Acústica', r'Caixa de Som', r'Caixa som', r'Subwoofer', r'tarol', r'Estante - partitura',
    r'Amplificador de áudio', r'Amplificador som', r'Amplificador fone ouvido',
    r'Piano', r'Suporte para teclado', r'Mesa áudio', r'Interface de Áudio', r'Piano',
    r'Pedestal', r'Pedestal caixa acústica', r'Pedal Efeito', r'fone de ouvido', r'headset', 
    r'Bateria Eletrônica', r'Cabo extensor',r'Tela projeção', r'Projetor Multimídia', 
    r'Peças E Acessórios Instrumento Musical'
    
]
REGEX_FILTRO = re.compile('|'.join(PALAVRAS_CHAVE), re.IGNORECASE)


# Trello API Configuration
API_KEY = '683cba47b43c3a1cfb10cf809fecb685'
TOKEN = 'ATTA89e63b1ce30ca079cef748f3a99cda25de9a37f3ba98c35680870835d6f2cae034C088A8'
LISTAS_PREPARANDO = ['6650f3369bb9bacb525d1dc8']

class WavecodeAutomation:
    def __init__(self, debug=True):
        self.download_dir = DOWNLOAD_DIR
        self.orcamentos_dir = ORCAMENTOS_DIR
        self.base_url = "https://app2.wavecode.com.br/"
        self.login_email = "pietromrampazzo@gmail.com"
        self.login_password = "Piloto@314"
        self.driver = None
        self.wait = None
        self.debug = debug
        os.makedirs(self.download_dir, exist_ok=True)
        os.makedirs(self.orcamentos_dir, exist_ok=True)
        self.processed_cards = set()

    def load_processed_bids(self):
        """
        Carrega os editais já processados do livro razão para evitar reprocessamento.
        Retorna um set de tuplas (UASG, Edital) para busca rápida.
        """
        processed = set()
        if not os.path.exists(LIVRO_RAZAO_PATH):
            self.log(f"Livro razão não encontrado em {LIVRO_RAZAO_PATH}. Será criado um novo.")
            return processed
        
        try:
            df = pd.read_excel(LIVRO_RAZAO_PATH)
            # Garante que as colunas UASG e Edital sejam tratadas como strings para consistência
            if 'UASG' in df.columns and 'Edital' in df.columns:
                for _, row in df.iterrows():
                    uasg = str(row['UASG']).strip()
                    edital = str(row['Edital']).strip()
                    if uasg and edital:
                        processed.add((uasg, edital))
            self.log(f"Carregados {len(processed)} registros do livro razão.")
        except Exception as e:
            self.log(f"❌ Erro ao carregar o livro razão: {e}. Continuando sem dados prévios.")
        
        return processed

    def update_ledger(self, new_bids_data):
        """
        Registra os novos editais baixados no livro razão (livro_razão.xlsx).
        """
        if not new_bids_data:
            return

        self.log(f"Atualizando livro razão com {len(new_bids_data)} novos editais...")
        cols = ['Timestamp', 'Dia Disputa', 'UASG', 'Edital', 'Comprador', 'Arquivo Download', 'Link Compras.gov']
        new_records = [{'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'Dia Disputa': bid.get('dia_disputa', ''), 'UASG': bid.get('uasg', ''), 'Edital': bid.get('edital', ''), 'Comprador': bid.get('comprador', ''), 'Arquivo Download': bid.get('file_name', ''), 'Link Compras.gov': ''} for bid in new_bids_data]
        df_new = pd.DataFrame(new_records)

        try:
            if os.path.exists(LIVRO_RAZAO_PATH):
                df_existing = pd.read_excel(LIVRO_RAZAO_PATH)
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            else:
                df_combined = df_new
            
            df_combined['UASG'] = df_combined['UASG'].astype(str)
            df_combined['Edital'] = df_combined['Edital'].astype(str)
            df_combined.drop_duplicates(subset=['UASG', 'Edital'], keep='first', inplace=True)
            df_combined.to_excel(LIVRO_RAZAO_PATH, index=False, columns=cols)
            self.log(f"✅ Livro razão atualizado com sucesso em {LIVRO_RAZAO_PATH}")
        except Exception as e:
            self.log(f"❌ Erro ao atualizar o livro razão: {e}")

    def log(self, message):
        if self.debug:
            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}] {message}")

    def save_debug_screenshot(self, name):
        if self.debug and self.driver:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"debug_{name}_{timestamp}.png"
            filepath = os.path.join(self.download_dir, filename)
            try:
                self.driver.save_screenshot(filepath)
                self.log(f"📸 Screenshot salvo: {filename}")
            except Exception as e:
                self.log(f"❌ Erro ao salvar screenshot: {e}")

    def setup_driver(self):
        self.log("Configurando Chrome WebDriver...")
        chrome_options = Options()
        prefs = {
            "download.default_directory": self.download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "profile.default_content_settings.popups": 0,
            "profile.default_content_setting_values.notifications": 2
        }
        chrome_options.add_experimental_option("prefs", prefs)
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, 60)
            self.log("Chrome WebDriver configurado com sucesso!")
        except Exception as e:
            self.log(f"Erro ao configurar WebDriver: {str(e)}")
            raise

    def login(self):
        self.log("Acessando portal Wavecode...")
        try:
            self.driver.get(self.base_url)
            email_field = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text'][placeholder*='email']")))
            password_field = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']")))
            login_button = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'ACESSAR')]")))

            email_field.clear()
            email_field.send_keys(self.login_email)
            password_field.clear()
            password_field.send_keys(self.login_password)

            current_url = self.driver.current_url
            login_button.click()

            self.wait.until(EC.url_changes(current_url))
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))

            if "login" not in self.driver.current_url.lower():
                self.log("✅ Login bem-sucedido")
                self.save_debug_screenshot("login_success")
                return True
            else:
                self.log("❌ Login falhou: Retornado para a página de login.")
                self.save_debug_screenshot("login_failed")
                return False
        except TimeoutException:
            self.log("❌ Login falhou: Timeout ao esperar elementos de login.")
            self.save_debug_screenshot("login_timeout_error")
            return False
        except NoSuchElementException:
            self.log("❌ Login falhou: Elemento de login não encontrado.")
            self.save_debug_screenshot("login_element_not_found")
            return False
        except Exception as e:
            self.log(f"❌ Erro no login: {str(e)}")
            self.save_debug_screenshot("login_unexpected_error")
            return False

    def navigate_to_editais(self):
        self.log("Navegando para seção de editais...")
        try:
            # Acesso à lista de editais. Adiciona uma pausa para garantir que a página carregue completamente
            self.driver.get(urljoin(self.base_url, "/prospects/list?company_id=2747"))
            # Aguarda alguns segundos para que o conteúdo inicialize (prevenindo a falta de botões de download por carregamento lento)
            time.sleep(5)
            self.log("Iniciando rolagem para carregar editais...")
            self.scroll_to_load_editais()

            # Espera um pouco para a página assentar após a rolagem
            time.sleep(5) 

            # Verifica se algum edital (qualquer um) foi carregado
            editais_encontrados = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'item-body-block')]//p[text()='UASG']")
            
            if not editais_encontrados:
                self.log("⏭️ Página carregada, mas nenhum edital foi encontrado. Encerrando a etapa de download de forma limpa.")
                self.save_debug_screenshot("no_editais_found")
                return False

            self.log(f"⏭️ Página de editais carregada com {len(editais_encontrados)} itens.")
            self.save_debug_screenshot("editais_page_loaded")
            return True
            
        except Exception as e:
            # Se qualquer erro ocorrer (incluindo timeouts de outras partes), falha de forma segura
            self.log(f"❌ Erro inesperado ao navegar para a página de editais: {str(e)}")
            self.save_debug_screenshot("navigate_editais_error")
            return False

    def scroll_to_load_editais(self):
        self.log("Rolando página para carregar todos os editais...")
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        while True:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(5)
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        self.driver.execute_script("window.scrollTo(0, 0);")
        self.log("⏭️ Rolagem concluída!")

    def find_download_buttons(self):
        """
        Localiza os elementos de download em cada cartão de edital.

        Em vez de capturar qualquer SVG ou links que podem exigir CAPTCHA,
        percorremos cada cabeçalho de ação (``.action-header``) e selecionamos apenas o primeiro
        ícone de seta para baixo, identificado pelo atributo ``viewBox='0 0 256 256'``.
        Caso não seja encontrado esse atributo, usamos o primeiro ``svg`` como fallback.
        Isso evita clicar no ícone de favoritar (estrela) ou em links externos.
        """
        self.log("Procurando botões de download…")
        download_buttons = []
        try:
            action_headers = self.driver.find_elements(By.CSS_SELECTOR, ".action-header")
            self.log(f"Encontrados {len(action_headers)} cabeçalhos de ação.")
            for header in action_headers:
                arrow = None
                try:
                    arrow = header.find_element(By.CSS_SELECTOR, "svg[viewBox='0 0 256 256']")
                except Exception:
                    try:
                        arrow = header.find_element(By.TAG_NAME, "svg")
                    except Exception:
                        pass
                if arrow:
                    download_buttons.append(arrow)
            if download_buttons:
                self.log(f"Encontrados {len(download_buttons)} botões de download (setas).")
            else:
                self.log("Nenhum botão de download (seta) encontrado. Nenhum edital para processar.")
            return download_buttons
        except Exception as e:
            self.log(f"Erro ao encontrar botões de download: {str(e)}")
            return []

    def download_document(self, download_element, uasg, edital, comprador, dia_disputa):
        try:
            files_before = set(os.listdir(self.download_dir))
            self.driver.execute_script("arguments[0].scrollIntoView(true);", download_element)
            time.sleep(8)
            if download_element.tag_name == 'a':
                self.driver.execute_script("window.open(arguments[0].href, '_blank');", download_element)
                self.driver.switch_to.window(self.driver.window_handles[-1])
                time.sleep(1)
                self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])
            else:
                download_element.click()
            max_wait = 2
            waited = 0
            while waited < max_wait:
                time.sleep(8)
                waited += 2
                files_after = set(os.listdir(self.download_dir))
                new_files = files_after - files_before
                for new_file in new_files:
                    if not new_file.endswith(('.tmp', '.crdownload', '.part')) and os.path.exists(os.path.join(self.download_dir, new_file)) and os.path.getsize(os.path.join(self.download_dir, new_file)) > 0:
                        _, ext = os.path.splitext(new_file)
                        ext = ext or '.zip'
                        clean_edital = re.sub(r'[^\w\-]', '_', str(edital))
                        clean_comprador = re.sub(r'[^\w\-]', '_', comprador)
                        clean_dia_disputa = dia_disputa.replace(':', 'h').replace(' - ', '_').replace('/', '-') + 'm'
                        new_name = f"U_{uasg}_E_{clean_edital}_{clean_dia_disputa}{ext}"
                        new_path = os.path.join(self.download_dir, new_name)
                        
                        counter = 1
                        while os.path.exists(new_path):
                            new_path = os.path.join(self.download_dir, f"U_{uasg}_E_{clean_edital}_{clean_dia_disputa}_{counter}{ext}")
                            counter += 1
                        os.rename(os.path.join(self.download_dir, new_file), new_path)
                        self.log(f"✅ Arquivo baixado: {new_name}")
                        return new_name
                if waited % 10 == 0:
                    self.log(f"Aguardando download... ({waited}s/{max_wait}s)")
            self.log(f"❌ Timeout aguardando download")
            return None
        except Exception as e:
            self.log(f"❌ Erro durante download: {str(e)}")
            return None

    def extract_edital_info_from_context(self, download_element, index):
        self.log(f"🔍 Extraindo informações para o item {index+1}…")
        # Inicializa variáveis com valores padrão
        uasg, edital, comprador, dia_disputa = None, None, "Desconhecido", ""
        try:
            # Subir até o contêiner principal do edital.
            # A seta de download fica dentro de `.action-header` -> `.container-header`.
            # O cartão completo é o pai de `container-header`. Portanto, subimos até o pai do container-header.
            try:
                container_header_div = download_element.find_element(
                    By.XPATH,
                    "./ancestor::div[contains(@class, 'container-header')][1]"
                )
                container_principal_item = container_header_div.find_element(By.XPATH, "./..")
            except Exception:
                # Fallback: tenta usar a lógica anterior baseada na presença de ekPPva
                try:
                    container_principal_item = download_element.find_element(
                        By.XPATH,
                        "./ancestor::div[.//p[contains(@class,'ekPPva')]][1]"
                    )
                except Exception:
                    # fallback antigo baseado em wrapper-header
                    container_wrapper_header = download_element.find_element(By.XPATH, "./ancestor::div[contains(@class, 'wrapper-header')]")
                    container_principal_item = container_wrapper_header.find_element(By.XPATH, "./..")

            # Extrai valores do HTML interno usando lxml para robustez contra variações de classes.
            try:
                # Converte o container para HTML e cria um tree lxml
                container_html = container_principal_item.get_attribute('outerHTML')
                tree = html.fromstring(container_html)

                # Extrai o número do edital: procura <p> com classe ekPPva que contenha dígitos (ignora "ComprasNet" e estado)
                edital = None
                for p_elem in tree.xpath(".//p[contains(@class, 'ekPPva')]"):
                    texto = ''.join(p_elem.xpath('.//text()')).strip()
                    m = re.search(r"\d{5,}", texto)
                    if m:
                        edital = m.group(0)
                        break
                if not edital:
                    self.log("Edital não encontrado com base em dígitos.")

                # Função auxiliar para extrair valores de blocos com label/valor
                def get_value_by_label(keyword):
                    keyword = keyword.lower()
                    # Busca em item-body (Comprador)
                    for div in tree.xpath(".//div[contains(@class,'item-body')]"):
                        label = ''.join(div.xpath('./p[1]//text()')).strip().lower().replace(':','')
                        if keyword in label:
                            value = ''.join(div.xpath('./p[2]//text()')).strip()
                            if value:
                                return value
                    # Busca em item-body-block (UASG, Disputa)
                    for block in tree.xpath(".//div[contains(@class,'item-body-block')]"):
                        label = ''.join(block.xpath('./p[1]//text()')).strip().lower().replace(':','')
                        if keyword in label:
                            value = ''.join(block.xpath('./p[2]//text()')).strip()
                            if value:
                                return value
                    return None

                # Extrai comprador
                val_comprador = get_value_by_label('comprador')
                if val_comprador:
                    comprador = val_comprador
                else:
                    self.log("Comprador não encontrado para este item (lógica baseada em lxml).")

                # Extrai UASG
                val_uasg = get_value_by_label('uasg')
                if val_uasg:
                    # Mantém apenas números
                    match = re.search(r"\d+", val_uasg)
                    if match:
                        uasg = match.group(0)
                else:
                    self.log("UASG não encontrado para este item (lógica baseada em lxml).")

                # Extrai data da disputa
                val_disputa = get_value_by_label('disputa')
                if val_disputa:
                    match = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s*-\s*\d{1,2}:\d{1,2})", val_disputa)
                    if match:
                        dia_disputa = match.group(1)
                else:
                    self.log("Data de disputa não encontrada para este item (lógica baseada em lxml).")

            except Exception as parse_exc:
                self.log(f"Erro ao extrair dados via lxml: {parse_exc}")

            # Extrai a UASG: localiza o div cujo primeiro <p> contém 'UASG' e pega o valor no segundo <p>
            try:
                uasg_element = container_principal_item.find_element(
                    By.XPATH,
                    ".//div[p[1][contains(text(), 'UASG')]]/p[2]"
                )
                uasg_text = uasg_element.text.strip()
                uasg_match = re.search(r"(\d+)", uasg_text)
                if uasg_match:
                    uasg = uasg_match.group(1)
            except Exception:
                self.log("UASG não encontrado para este item (lógica baseada em texto).")

            # Extrai a data/hora da disputa: procura o div cujo primeiro <p> contém 'Disputa' e pega o valor no segundo <p>
            try:
                disputa_element = container_principal_item.find_element(
                    By.XPATH,
                    ".//div[p[1][contains(text(), 'Disputa')]]/p[2]"
                )
                disputa_text = disputa_element.text.strip()
                # Procura padrão de data e hora (por exemplo: 18/09/2025 - 09:00)
                disputa_match = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s*-\s*\d{1,2}:\d{1,2})", disputa_text)
                if disputa_match:
                    dia_disputa = disputa_match.group(1)
            except Exception:
                self.log("Data de disputa não encontrada para este item (lógica baseada em texto).")

            # Fallbacks para valores ausentes
            if not uasg:
                uasg = str(999 + index).zfill(6)
            if not edital:
                edital = str(index + 1).zfill(8)
            if not comprador:
                comprador = "Desconhecido"

            self.log(
                f"🔍 Informações extraído: UASG={uasg}, Edital={edital}, Comprador='{comprador}', Disputa='{dia_disputa}'"
            )
            return uasg, edital, comprador, dia_disputa

        except NoSuchElementException as e:
            # Caso o contêiner principal não seja encontrado
            self.log(
                f"❌ Falha ao encontrar o container principal ou um elemento de dados associado ao botão de download: {e}"
            )
            return str(999 + index).zfill(6), str(index + 1).zfill(8), "Desconhecido", ""
        except Exception as e:
            # Qualquer outro erro inesperado
            self.log(f"❌ Erro inesperado na extração de informações do edital: {str(e)}")
            return str(999 + index).zfill(6), str(index + 1).zfill(8), "Desconhecido", ""

    def process_editais_page(self, page_num, processed_bids):
        self.log(f"Processando página {page_num}...")
        newly_downloaded = []
        try:
            download_buttons = self.find_download_buttons()
            
            if not download_buttons:
                self.log("❌ Nenhum botão de download encontrado nesta página.")
                self.save_debug_screenshot(f"no_download_buttons_page_{page_num}")
                return newly_downloaded
            
            self.log(f"Encontrados {len(download_buttons)} botões de download para processar.")
            
            for index, button in enumerate(download_buttons):
                uasg, edital, comprador, dia_disputa = self.extract_edital_info_from_context(button, index)
                
                # Pular se o edital já foi processado
                if (str(uasg), str(edital)) in processed_bids:
                    self.log(f"⏭️  Pulando edital já processado: UASG {uasg}, Edital {edital}")
                    continue

                downloaded_file_name = self.download_document(button, uasg, edital, comprador, dia_disputa)
                
                if downloaded_file_name:
                    bid_data = {'uasg': uasg, 'edital': edital, 'file_name': downloaded_file_name, 'comprador': comprador, 'dia_disputa': dia_disputa}
                    newly_downloaded.append(bid_data)
                
                time.sleep(1)
            
            self.log(f"⏭️ Página {page_num}: {len(newly_downloaded)} novos editais baixados.")
            return newly_downloaded
            
        except Exception as e:
            self.log(f"Erro ao processar a página {page_num}: {str(e)}")
            self.save_debug_screenshot(f"process_page_{page_num}_error")
            return 0

    def limpar_diretorios(self):
        # Obtém o caminho do diretório onde o script está localizado
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # Constrói o caminho para o diretório 'arte_'
        base_dir = os.path.dirname(script_dir)

        # Define os diretórios a serem limpos (apenas na raiz)
        diretorios_para_limpar = [
            os.path.join(base_dir, 'DOWNLOADS', 'EDITAIS'),
        ]

        # Define as extensões dos arquivos a serem deletados
        extensoes_para_deletar = ['.pdf', '.zip', '.xlsx']

        for diretorio in diretorios_para_limpar:
            if not os.path.exists(diretorio):
                print(f"Diretório não encontrado: {diretorio}")
                continue

            print(f"Limpando a raiz do diretório: {diretorio}")
            # Itera apenas sobre os arquivos na raiz do diretório, não nas subpastas
            for item in os.listdir(diretorio):
                item_path = os.path.join(diretorio, item)
                # Verifica se é um arquivo e se a extensão corresponde
                if os.path.isfile(item_path) and any(item.lower().endswith(ext) for ext in extensoes_para_deletar):
                    try:
                        os.remove(item_path)
                        print(f"  Deletado arquivo: {item_path}")
                    except OSError as e:
                        print(f"  Erro ao deletar o arquivo {item_path}: {e}")

    def limpar_patio(self):
        """Limpa os arquivos .xlsx intermediários da pasta 'patio'."""
        diretorio = self.orcamentos_dir
        if not os.path.exists(diretorio):
            self.log(f"Diretório do pátio não encontrado: {diretorio}")
            return

        self.log(f"Limpando o diretório do pátio: {diretorio}")
        for item in os.listdir(diretorio):
            item_path = os.path.join(diretorio, item)
            # Deleta apenas arquivos .xlsx
            if os.path.isfile(item_path) and item.lower().endswith('.xlsx'):
                try:
                    os.remove(item_path)
                    self.log(f"  Deletado arquivo do pátio: {item_path}")
                except OSError as e:
                    self.log(f"  Erro ao deletar o arquivo {item_path}: {e}")

    def descompactar_arquivos(self, input_dir=None):
        pasta = Path(input_dir or self.download_dir)
        for arquivo_zip in pasta.glob("*.zip"):
            try:
                with zipfile.ZipFile(arquivo_zip, 'r') as zip_ref:
                    zip_ref.extractall(pasta / arquivo_zip.stem)
                arquivo_zip.unlink()
                self.log(f"✓ Descompactado: {arquivo_zip.name}")
            except Exception as e:
                self.log(f"✗ Erro ao descompactar {arquivo_zip.name}: {str(e)}")

    def extrair_e_copiar_pdfs(self, input_dir=None, output_dir=None):
        pasta_origem = Path(input_dir or self.download_dir)
        pasta_destino = Path(output_dir or self.download_dir)
        padrao_relacao = re.compile(r"RelacaoItens\d+\.pdf", re.IGNORECASE)
        copiados = 0
        for subpasta in pasta_origem.iterdir():
            if subpasta.is_dir():
                for arquivo in subpasta.glob("*.pdf"):
                    if padrao_relacao.fullmatch(arquivo.name):
                        nome_pasta = subpasta.name
                        novo_nome = f"{nome_pasta}.pdf"
                        destino_final = pasta_destino / novo_nome
                        shutil.copy2(arquivo, destino_final)
                        self.log(f"✅ Copiado: {novo_nome}")
                        copiados += 1
                        break
        self.log(f"🎉 {copiados} PDFs movidos")

    def extract_items_from_text(self, text, arquivo_nome):
        items = []
        text = re.sub(r'\n+', '\n', text)
        text = re.sub(r'\s+', ' ', text)

        item_pattern = re.compile(r'(\d+)\s*-\s*([^0-9]+?)(?=Descrição Detalhada:)', re.DOTALL | re.IGNORECASE)
        item_matches = list(item_pattern.finditer(text))

        for i, match in enumerate(item_matches):
            item_num = match.group(1).strip()
            item_nome = match.group(2).strip()
            start_pos = match.start()
            end_pos = item_matches[i + 1].start() if i + 1 < len(item_matches) else len(text)
            item_text = text[start_pos:end_pos]

            descricao_match = re.search(r'Descrição Detalhada:\s*(.*?)(?=Tratamento Diferenciado:)|Aplicabilidade Decreto|$',
                                       item_text, re.DOTALL | re.IGNORECASE)
            descricao = ""
            if descricao_match:
                descricao = descricao_match.group(1).strip()
                descricao = re.sub(r'\s+', ' ', descricao)
                descricao = re.sub(r'[^\w\s:,.()/-]', '', descricao)

            item_completo = f"{item_nome}"
            if descricao:
                item_completo += f" {descricao}"

            quantidade_match = re.search(r'Quantidade Total:\s*(\d+)', item_text, re.IGNORECASE)
            quantidade = quantidade_match.group(1) if quantidade_match else ""

            valor_unitario = ""
            valor_unitario_match = re.search(r'Valor Unitário[^:]*:\s*R?\$?\s*([\d.,]+)', item_text, re.IGNORECASE)
            if valor_unitario_match:
                valor_unitario = valor_unitario_match.group(1)

            valor_total = ""
            valor_total_match = re.search(r'Valor Total[^:]*:\s*R?\$?\s*([\d.,]+)', item_text, re.IGNORECASE)
            if valor_total_match:
                valor_total = valor_total_match.group(1)

            unidade_match = re.search(r'Unidade de Fornecimento:\s*([^0-9\n]+?)(?=\s|$|\n)', item_text, re.IGNORECASE)
            unidade = unidade_match.group(1).strip() if unidade_match else ""

            intervalo = ""
            for pattern in [r'Intervalo Mínimo entre Lances[^:]*:\s*R?\$?\s*([\d.,]+)', r'Intervalo[^:]*:\s*R?\$?\s*([\d.,]+)']:
                intervalo_match = re.search(pattern, item_text, re.IGNORECASE)
                if intervalo_match:
                    intervalo = intervalo_match.group(1)
                    break

            local = ""
            for pattern in [r'Local de Entrega[^:]*:\s*([^(\n]+?)(?:\s*\(|$|\n)', r'([A-Za-z]+/[A-Z]{2})']:
                local_match = re.search(pattern, item_text, re.IGNORECASE)
                if local_match:
                    local = local_match.group(1).strip()
                    if local and not local.isdigit():
                        break

            item_data = {
                "ARQUIVO": arquivo_nome,
                "Número do Item": item_num,
                "Descrição": item_completo,
                "Quantidade Total": int(quantidade) if quantidade.isdigit() else quantidade,
                "Valor Unitário (R$)": valor_unitario,
                "Valor Total (R$)": valor_total,
                "Unidade de Fornecimento": unidade,
                "Intervalo Mínimo entre Lances (R$)": intervalo,
                "Local de Entrega (Quantidade)": local
            }
            items.append(item_data)

        return items

    def process_pdf_file(self, pdf_path):
        self.log(f"Processando: {pdf_path}")
        text = ""
        try:
            with fitz.open(pdf_path) as doc:
                for page_num, page in enumerate(doc):
                    page_text = page.get_text()
                    text += page_text
        except Exception as e:
            self.log(f"Erro ao processar PDF {pdf_path}: {e}")
            return []
        if not text.strip():
            self.log(f"  Aviso: Nenhum texto extraído de {pdf_path}")
            return []
        return self.extract_items_from_text(text, os.path.basename(pdf_path))

    def tratar_dataframe(self, df):
        if df.empty:
            return df

        df = df.rename(columns={
            'ARQUIVO': 'ARQUIVO',
            'Número do Item': 'Nº',
            'Descrição': 'DESCRICAO',
            'Quantidade Total': 'QTDE',
            'Valor Unitário (R$)': 'VALOR_UNIT',
            'Valor Total (R$)': 'VALOR_TOTAL',
            'Unidade de Fornecimento': 'UNID_FORN',
            'Intervalo Mínimo entre Lances (R$)': 'INTERVALO_LANCES',
            'Local de Entrega (Quantidade)': 'LOCAL_ENTREGA'
        })

        if 'QTDE' in df.columns:
            df['QTDE'] = pd.to_numeric(df['QTDE'], errors='coerce').fillna(0)

        for col in ['VALOR_UNIT', 'VALOR_TOTAL']:
            if col in df.columns:
                df[col] = (
                    df[col]
                    .astype(str)
                    .str.replace('.', '', regex=False)
                    .str.replace(',', '.', regex=False)
                )
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        mask = (df['VALOR_UNIT'] == 0) & (df['VALOR_TOTAL'] > 0) & (df['QTDE'] > 0)
        df.loc[mask, 'VALOR_UNIT'] = df.loc[mask, 'VALOR_TOTAL'] / df.loc[mask, 'QTDE']

        if 'QTDE' in df.columns and 'VALOR_UNIT' in df.columns:
            df['VALOR_TOTAL'] = df['QTDE'] * df['VALOR_UNIT']

        for col in ['VALOR_UNIT', 'VALOR_TOTAL']:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: f"{x:.2f}".replace(".", ","))

        colunas_desejadas = ['ARQUIVO', 'Nº', 'DESCRICAO', 'UNID_FORN', 'QTDE',
                            'VALOR_UNIT', 'VALOR_TOTAL', 'LOCAL_ENTREGA']
        colunas_desejadas = [c for c in colunas_desejadas if c in df.columns]
        outras_colunas = [c for c in df.columns if c not in colunas_desejadas]

        return df[colunas_desejadas + outras_colunas]

    def pdfs_para_xlsx(self, input_dir=None, output_dir=None):
        input_dir = input_dir or self.download_dir
        output_dir = output_dir or self.orcamentos_dir
        os.makedirs(output_dir, exist_ok=True)
        if not os.path.exists(input_dir):
            self.log(f"Erro: Diretório de entrada não encontrado: {input_dir}")
            return
        pdf_files = [f for f in os.listdir(input_dir) if f.lower().endswith('.pdf')]
        if not pdf_files:
            self.log(f"Nenhum arquivo PDF encontrado em: {input_dir}")
            return
        self.log(f"Encontrados {len(pdf_files)} arquivos PDF para processar:")
        for pdf_file in pdf_files:
            self.log(f"  - {pdf_file}")
        self.log("-" * 60)
        for file_name in pdf_files:
            try:
                pdf_path = os.path.join(input_dir, file_name)
                items = self.process_pdf_file(pdf_path)
                if items:
                    df = pd.DataFrame(items)
                    xlsx_name = os.path.splitext(file_name)[0] + ".xlsx"
                    df['ARQUIVO'] = xlsx_name # Garante consistência no nome do arquivo para etapas futuras
                    df = self.tratar_dataframe(df)
                    output_path = os.path.join(output_dir, xlsx_name)
                    df.to_excel(output_path, index=False)
                    self.log(f"✅ Processado: {file_name} → {xlsx_name} ({len(items)} itens)")
                else:
                    self.log(f"❌ Nenhum item encontrado em: {file_name}")
            except Exception as e:
                self.log(f"❌ Erro ao processar {file_name}: {e}")
        self.log(f"\nProcessamento concluído! Arquivos salvos em: {output_dir}")

    def clean_dataframe(self, df):
        if df.empty:
            return df
        df = df.replace('', pd.NA)
        for col in ['Quantidade Total', 'Valor Unitário (R$)', 'Valor Total (R$)', 'Intervalo Mínimo entre Lances (R$)']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(' ', '').replace('nan', '')
        return df

    def combine_excel_files(self, input_dir=None, output_file=None):
        input_dir = input_dir or self.orcamentos_dir
        output_file = output_file or SUMMARY_EXCEL_PATH
        excel_files = [f for f in os.listdir(input_dir) if f.endswith('.xlsx') and f != os.path.basename(output_file)]
        if not excel_files:
            self.log("Nenhum arquivo Excel encontrado para combinar.")
            return
        dados_combinados = []
        for arquivo in excel_files:
            try:
                df = self.clean_dataframe(pd.read_excel(os.path.join(input_dir, arquivo)))
                dados_combinados.append(df)
            except Exception as e:
                self.log(f"Erro ao processar {arquivo}: {e}")

        if dados_combinados:
            df_combinado = pd.concat(dados_combinados, ignore_index=True)
            df_combinado = self.tratar_dataframe(df_combinado)
            df_combinado.to_excel(output_file, index=False, sheet_name='Resumo')
            self.log(f"✅ Master Excel salvo: {output_file}")
            
    def filtrar_e_atualizar_master(self):
        """
        Filtra itens da planilha de resumo gerada (summary.xlsx) com base em palavras-chave
        e os adiciona ao topo da planilha principal (master.xlsx).
        """
        self.log("Iniciando filtragem de itens para a planilha master...")
        
        # Passo 1: Carregar summary.xlsx
        if not os.path.exists(SUMMARY_EXCEL_PATH):
            self.log(f"❌ Arquivo de resumo não encontrado: {SUMMARY_EXCEL_PATH}. Abortando a filtragem.")
            return

        df_summary = pd.read_excel(SUMMARY_EXCEL_PATH)
        self.log(f"Planilha summary carregada: {len(df_summary)} linhas.")

        # Passo 2: Filtrar itens relevantes
        if 'DESCRICAO' not in df_summary.columns:
            self.log("❌ Coluna 'DESCRICAO' não encontrada na planilha. Não é possível filtrar.")
            return
        
        mask = df_summary['DESCRICAO'].apply(lambda x: bool(REGEX_FILTRO.search(str(x))))
        df_filtrado = df_summary[mask].copy()
        
        if df_filtrado.empty:
            self.log("Nenhum item relevante encontrado para adicionar à master. Encerrando.")
            return
            
        self.log(f"Itens filtrados: {len(df_filtrado)} de {len(df_summary)} totais.")

        # Passo 3: Carregar master.xlsx (ou criar se não existir)
        if os.path.exists(FINAL_MASTER_PATH):
            df_master = pd.read_excel(FINAL_MASTER_PATH)
            self.log(f"Planilha master carregada: {len(df_master)} linhas existentes.")
        else:
            df_master = pd.DataFrame(columns=df_filtrado.columns)
            self.log("Planilha master não encontrada. Criando uma nova.")

        # Garantir que as colunas sejam compatíveis
        for col in df_filtrado.columns:
            if col not in df_master.columns:
                df_master[col] = pd.NA

        # Passo 4: Concatenar filtrados no topo e remover duplicatas
        df_atualizado = pd.concat([df_filtrado, df_master], ignore_index=True)
        df_atualizado = df_atualizado.drop_duplicates(subset=['ARQUIVO', 'Nº', 'DESCRICAO'], keep='first')

        # Passo 5: Salvar master atualizada
        df_atualizado.to_excel(FINAL_MASTER_PATH, index=False)
        self.log(f"✅ Master atualizada salva: {len(df_atualizado)} linhas totais. Novos itens adicionados: {len(df_filtrado)}.")

    def create_trello_card(self, uasg, edital, file_name, comprador, dia_disputa):
        try:
            card_name = f"Comprador: {comprador} - UASG: {uasg} - Edital: {edital}"
            
            clean_file_name = file_name if file_name else "N/A"

            card_description = (
                f"Arquivo Associado: {clean_file_name}\n"
                f"Comprador: {comprador}\n"
                f"UASG: {uasg}\n"
                f"Edital: {edital}\n"
                f"Data de Disputa: {dia_disputa if dia_disputa else 'Não especificada'}"
            )

            url = f"https://api.trello.com/1/cards"
            params = {
                'key': API_KEY,
                'token': TOKEN,
                'idList': LISTAS_PREPARANDO[0],
                'name': card_name,
                'desc': card_description
            }

            parsed_date_for_trello = None
            if dia_disputa:
                try:
                    dia_disputa_cleaned = dia_disputa.strip().replace('h', ':').replace('m', '')
                    possible_formats = [
                        "%d-%m-%Y - %H:%M", "%d/%m/%Y - %H:%M",
                        "%Y-%m-%d %H:%M",   "%Y/%m/%d %H:%M",
                        "%d-%m-%Y %H:%M",   "%d/%m/%Y %H:%M"
                    ]

                    parsed_date = None
                    for fmt in possible_formats:
                        try:
                            parsed_date = datetime.strptime(dia_disputa_cleaned, fmt)
                            break
                        except ValueError:
                            continue

                    if parsed_date:
                        # Torna a data "aware" em America/Sao_Paulo e envia com offset (-03:00)
                        if ZoneInfo is not None:
                            aware = parsed_date.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
                            params['due'] = aware.isoformat(timespec='seconds')  # ex: 2025-08-21T09:00:00-03:00
                        else:
                            # Fallback estático (Brasil sem DST desde 2019): -03:00
                            params['due'] = parsed_date.strftime("%Y-%m-%dT%H:%M:%S-03:00")

                        self.log(f"✅ Data de disputa formatada p/ Trello: {params['due']}")
                        parsed_date_for_trello = parsed_date.strftime("%d/%m/%Y")
                    else:
                        self.log(f"⚠️ Não foi possível converter a data de disputa '{dia_disputa}'.")
                except Exception as date_err:
                    self.log(f"❌ Erro ao processar data de disputa para Trello: {date_err}")


            
            response = requests.post(url, params=params)
            response.raise_for_status()

            if response.status_code == 200:
                card_id = response.json()['id']
                self.log(f"✅ Card Trello criado com sucesso: '{card_name}' (ID: {card_id})")
                self.processed_cards.add(card_id)
                return True
            else:
                self.log(f"❌ Falha ao criar card Trello. Status: {response.status_code}, Resposta: {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            self.log(f"❌ Erro de rede ou API ao criar card Trello: {str(e)}")
            return False
        except Exception as e:
            self.log(f"❌ Erro inesperado ao criar card Trello: {str(e)}")
            return False

    def create_trello_cards_for_master_items(self, newly_downloaded_bids):
        """
        Cria cards no Trello apenas para os editais que tiveram itens filtrados para o master.xlsx.
        """
        self.log("\n[7/7] Verificando itens no master.xlsx para criação de cards no Trello...")
        if not newly_downloaded_bids:
            self.log("Nenhum edital novo para verificar.")
            return

        if not os.path.exists(FINAL_MASTER_PATH):
            self.log(f"❌ Arquivo master não encontrado em {FINAL_MASTER_PATH}. Nenhum card será criado.")
            return

        try:
            df_master = pd.read_excel(FINAL_MASTER_PATH)
            if df_master.empty or 'ARQUIVO' not in df_master.columns:
                self.log("Master.xlsx está vazio ou não contém a coluna 'ARQUIVO'. Nenhum card será criado.")
                return
            
            # Garante que a coluna 'ARQUIVO' seja do tipo string para evitar erros com os.path
            df_master['ARQUIVO'] = df_master['ARQUIVO'].astype(str)
            
            master_file_basenames = {os.path.splitext(f)[0] for f in df_master['ARQUIVO'].unique()}
            self.log(f"Encontrados {len(master_file_basenames)} editais únicos com itens relevantes no master.xlsx.")

            bids_with_cards_created = set()
            cards_created_count = 0

            for bid_data in newly_downloaded_bids:
                file_name = bid_data.get('file_name')
                if not file_name: continue
                
                bid_basename = os.path.splitext(file_name)[0]
                bid_key = (bid_data.get('uasg'), bid_data.get('edital'))

                if bid_basename in master_file_basenames and bid_key not in bids_with_cards_created:
                    self.log(f"➡️  Encontrado item relevante para o edital {bid_basename}. Criando card no Trello...")
                    success = self.create_trello_card(uasg=bid_data['uasg'], edital=bid_data['edital'], file_name=bid_data['file_name'], comprador=bid_data['comprador'], dia_disputa=bid_data['dia_disputa'])
                    if success:
                        bids_with_cards_created.add(bid_key)
                        cards_created_count += 1
            
            self.log(f"🎉 Processo de criação de cards concluído. {cards_created_count} novos cards criados.")

        except Exception as e:
            self.log(f"❌ Erro ao processar master.xlsx para criar cards no Trello: {e}")

    def run(self, max_pages_to_process=5):
        """
        Executa o pipeline completo de automação, incluindo a lógica de paginação por número de página.
        :param max_pages_to_process: O número máximo de páginas a serem processadas.
        """
        print("="*60)
        print("🤖 WAVECODE AUTOMATION - PIPELINE v2.0")
        print("="*60)
        
        newly_downloaded_bids = []
        try:
            self.log("[1/8] Iniciando automação do navegador...")
            self.setup_driver()
            processed_bids = self.load_processed_bids()

            if self.login() and self.navigate_to_editais():
                for page_num in range(1, max_pages_to_process + 1):
                    self.log(f"--- Iniciando ciclo para a Página {page_num} ---")
                    if page_num > 1:
                        self.log(f"Navegando para a página de número {page_num}...")
                        try:
                            page_button = self.wait.until(
                                EC.element_to_be_clickable(
                                    (By.XPATH, f"//ul[contains(@class, 'pagination')]//li[text()='{page_num}']")
                                )
                            )
                            self.driver.execute_script("arguments[0].click();", page_button)
                            self.log(f"⏭️ Clique na página '{page_num}' realizado.")
                            time.sleep(8)
                            self.scroll_to_load_editais()

                        except TimeoutException:
                            self.log(f"⚠️ Página de número '{page_num}' não foi encontrada. Fim da paginação.")
                            break
                        except Exception as e:
                            self.log(f"❌ Erro ao tentar navegar para a página {page_num}: {e}")
                            self.save_debug_screenshot(f"pagination_error_page_{page_num}")
                            break

                    downloads_in_page = self.process_editais_page(page_num, processed_bids)
                    newly_downloaded_bids.extend(downloads_in_page)
        
        except Exception as e:
            self.log(f"❌ Erro geral na automação do navegador: {str(e)}")
            self.save_debug_screenshot("main_run_error")
        finally:
            if self.driver:
                self.driver.quit()
                self.log("Navegador fechado.")
        
        if not newly_downloaded_bids:
            self.log("✅ Nenhum edital novo encontrado ou baixado. Pipeline concluído sem processamento de arquivos.")
            return
        
        self.log(f"\n[2/8] Atualizando livro razão com {len(newly_downloaded_bids)} novos editais...")
        self.update_ledger(newly_downloaded_bids)

        self.log(f"\n[3/8] Descompactando arquivos...")
        self.descompactar_arquivos()
        
        self.log("\n[4/8] Extraindo e processando PDFs...")
        self.extrair_e_copiar_pdfs()
        self.pdfs_para_xlsx()
        
        self.log("\n[5/8] Consolidando itens no summary.xlsx...")
        self.combine_excel_files()
        
        self.log("[6/8] Filtrando itens relevantes para o master.xlsx...")
        self.filtrar_e_atualizar_master()

        self.log("[7/8] Limpando arquivos temporários...")
        self.limpar_diretorios()
        self.limpar_patio()

        self.log("[8/8] Create cards no Trello para novos editais com itens no master...")
        self.create_trello_cards_for_master_items(newly_downloaded_bids)



        print("\n🎉 PIPELINE CONCLUÍDO!")
        print(f"📁 Arquivos de orçamento em: {self.orcamentos_dir}")
        print(f"📊 Master Final Filtrada: {FINAL_MASTER_PATH}")
        print(f"📖 Livro Razão atualizado: {LIVRO_RAZAO_PATH}")

if __name__ == "__main__":
    automation = WavecodeAutomation()
    automation.run()