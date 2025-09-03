import os
import time
import re
import zipfile
import shutil
from pathlib import Path
import fitz
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

# === Configuration ===
BASE_DIR = r"C:\Users\pietr\OneDrive\.vscode\arte_"
DOWNLOAD_DIR = os.path.join(BASE_DIR, "EDITAIS")
ORCAMENTOS_DIR = os.path.join(BASE_DIR, "ORCAMENTOS")
EXCEL_PATH = os.path.join(ORCAMENTOS_DIR, "EDITAIS_PC.xlsx")
MASTER_EXCEL = os.path.join(ORCAMENTOS_DIR, "master.xlsx")

# Trello API Q
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

    def log(self, message):
        if self.debug:
            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}] {message}")

    def save_debug_screenshot(self, name):
        if self.debug and self.driver:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"debug_{name}_{timestamp}.png"
            filepath = os.path.join(self.download_dir, filename)
            self.driver.save_screenshot(filepath)
            self.log(f"📸 Screenshot salvo: {filename}")

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
            self.wait = WebDriverWait(self.driver, 30)
            self.log("Chrome WebDriver configurado com sucesso!")
        except Exception as e:
            self.log(f"Erro ao configurar WebDriver: {str(e)}")
            raise

    def find_element_by_html_analysis(self, soup, element_type):
        try:
            if element_type == 'email':
                selectors = [{'attr': 'type', 'value': 'text', 'placeholder': re.compile('email', re.IGNORECASE)}]
                for selector in selectors:
                    element = soup.find('input', {'type': selector['value'], 'placeholder': selector['placeholder']})
                    if element:
                        return self.extract_element_info(element, 'email')
            elif element_type == 'password':
                selectors = [{'attr': 'type', 'value': 'password'}]
                for selector in selectors:
                    element = soup.find('input', {selector['attr']: selector['value']})
                    if element:
                        return self.extract_element_info(element, 'password')
            elif element_type == 'login_button':
                selectors = [{'tag': 'button', 'text': 'ACESSAR'}]
                for selector in selectors:
                    element = soup.find(selector['tag'], string=selector['text'])
                    if element:
                        return self.extract_element_info(element, 'login_button')
            return None
        except Exception as e:
            self.log(f"Erro ao buscar elemento {element_type}: {str(e)}")
            return None

    def extract_element_info(self, element, element_type):
        info = {'tag': element.name, 'type': element_type, 'attributes': dict(element.attrs), 'text': element.get_text(strip=True), 'selectors': []}
        if element.get('id'):
            info['selectors'].append(f"#{element['id']}")
        if element.get('class'):
            info['selectors'].append(f".{element['class'][0]}")
        if element.get('type'):
            info['selectors'].append(f"input[type='{element['type']}']")
        self.log(f"Elemento {element_type} encontrado: {info['selectors'][0]}")
        return info

    def find_selenium_element(self, element_info):
        for selector in element_info['selectors']:
            try:
                if selector.startswith('#'):
                    return self.driver.find_element(By.ID, selector[1:])
                else:
                    return self.driver.find_element(By.CSS_SELECTOR, selector)
            except NoSuchElementException:
                continue
        self.log(f"Nenhum seletor funcionou para {element_info['type']}")
        return None

    def login(self):
        self.log("Acessando portal Wavecode...")
        try:
            self.driver.get(self.base_url)
            time.sleep(5)
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            email_info = self.find_element_by_html_analysis(soup, 'email')
            password_info = self.find_element_by_html_analysis(soup, 'password')
            button_info = self.find_element_by_html_analysis(soup, 'login_button')
            if not all([email_info, password_info, button_info]):
                self.log("❌ Elementos de login não encontrados")
                self.save_debug_screenshot("login_failed")
                return False
            email_element = self.find_selenium_element(email_info)
            password_element = self.find_selenium_element(password_info)
            button_element = self.find_selenium_element(button_info)
            if not all([email_element, password_element, button_element]):
                self.log("❌ Elementos não localizados com Selenium")
                self.save_debug_screenshot("login_elements_failed")
                return False
            email_element.clear()
            email_element.send_keys(self.login_email)
            password_element.clear()
            password_element.send_keys(self.login_password)
            current_url = self.driver.current_url
            button_element.click()
            self.wait.until(EC.url_changes(current_url))
            time.sleep(5)
            if "login" not in self.driver.current_url.lower():
                self.log("✅ Login bem-sucedido")
                self.save_debug_screenshot("login_success")
                return True
            self.log("❌ Login falhou")
            self.save_debug_screenshot("login_failed")
            return False
        except Exception as e:
            self.log(f"❌ Erro no login: {str(e)}")
            self.save_debug_screenshot("login_error")
            return False

    def navigate_to_editais(self):
        self.log("Navegando para seção de editais...")
        try:
            self.driver.get(urljoin(self.base_url, "/prospects/list?company_id=2747"))
            time.sleep(5)
            self.log("Iniciando rolagem para carregar editais...")
            self.scroll_to_load_editais()
            load_indicators = [
                (By.CSS_SELECTOR, ".sc-cdmAjP"),
                (By.XPATH, "//*[contains(text(), 'UASG')]"),
                (By.XPATH, "//*[contains(text(), 'Edital')]")
            ]
            for by, selector in load_indicators:
                try:
                    self.wait.until(EC.presence_of_element_located((by, selector)))
                    self.log(f"✅ Elemento de editais encontrado: {selector}")
                    self.save_debug_screenshot("editais_page_loaded")
                    return True
                except TimeoutException:
                    continue
            self.log("❌ Não foi possível confirmar carregamento da página de editais")
            self.save_debug_screenshot("editais_load_failed")
            return False
        except Exception as e:
            self.log(f"❌ Erro ao navegar para editais: {str(e)}")
            self.save_debug_screenshot("navigate_error")
            return False

    def scroll_to_load_editais(self):
        self.log("Rolando página para carregar todos os editais...")
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        while True:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # Aguarda elementos carregarem
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        self.driver.execute_script("window.scrollTo(0, 0);")  # Volta ao topo
        self.log("✅ Rolagem concluída!")

    def find_download_buttons(self):
        self.log("Procurando botões de download...")
        try:
            # Seletores baseados no HTML fornecido (ícone SVG no action-header)
            selectors = [
                ".action-header svg",
                "a.text-lik[href*='download']",
                "a.text-lik[href*='edital']"
            ]
            download_buttons = []
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        self.log(f"Encontrados {len(elements)} botões com seletor: {selector}")
                        download_buttons.extend(elements)
                        break
                except:
                    continue
            return list(dict.fromkeys(download_buttons))
        except Exception as e:
            self.log(f"Erro ao encontrar botões de download: {str(e)}")
            return []

    def extract_edital_info_from_context(self, download_button, index):
        self.log(f"🔍 Extraindo informações para download {index+1}...")
        try:
            # Encontrar o container pai .sc-cdmAjP
            container = download_button.find_element(By.XPATH, "./ancestor::div[@class='sc-cdmAjP']")
            text = container.text
            uasg = re.search(r'UASG\s*(\d+)', text).group(1) if re.search(r'UASG\s*(\d+)', text) else None
            edital = re.search(r'Edital:\s*(\d+)', text).group(1) if re.search(r'Edital:\s*(\d+)', text) else str(index + 1).zfill(8)
            comprador = re.search(r'Comprador:\s*(.+?)(?=\n|$)', text).group(1) if re.search(r'Comprador:\s*(.+?)(?=\n|$)', text) else ""
            dia_disputa = re.search(r'Disputa:\s*(\d{2}/\d{2}/\d{4}\s*-\s*\d{2}:\d{2})', text).group(1) if re.search(r'Disputa:\s*(\d{2}/\d{2}/\d{4}\s*-\s*\d{2}:\d{2})', text) else ""
            if uasg and edital:
                self.log(f"✅ UASG {uasg}, Edital {edital}, Comprador {comprador}, Dia {dia_disputa}")
                return uasg, edital, comprador, dia_disputa
            return str(999 + index).zfill(6), str(index + 1).zfill(8), "Desconhecido", ""
        except Exception as e:
            self.log(f"❌ Erro na extração: {str(e)}")
            return str(999 + index).zfill(6), str(index + 1).zfill(8), "Desconhecido", ""

    def download_document(self, download_element, uasg, edital, comprador, dia_disputa):
        try:
            files_before = set(os.listdir(self.download_dir))
            self.driver.execute_script("arguments[0].scrollIntoView(true);", download_element)
            time.sleep(1)
            # Verifica se é um link <a> e abre em nova aba ou clica diretamente
            if download_element.tag_name == 'a':
                self.driver.execute_script("window.open(arguments[0].href, '_blank');", download_element)
                self.driver.switch_to.window(self.driver.window_handles[-1])
                time.sleep(5)  # Aguarda download iniciar
                self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])
            else:
                download_element.click()
            max_wait = 10
            waited = 0
            while waited < max_wait:
                time.sleep(2)
                waited += 2
                files_after = set(os.listdir(self.download_dir))
                new_files = files_after - files_before
                for new_file in new_files:
                    if not new_file.endswith(('.tmp', '.crdownload', '.part')) and os.path.exists(os.path.join(self.download_dir, new_file)) and os.path.getsize(os.path.join(self.download_dir, new_file)) > 0:
                        _, ext = os.path.splitext(new_file)
                        ext = ext or '.pdf'
                        clean_edital = re.sub(r'[^\w\-]', '_', str(edital))
                        new_name = f"U_{uasg}_E_{clean_edital}_C_{re.sub(r'[^\w\-]', '_', comprador)}_{dia_disputa.replace('/', '-')}{ext}"
                        new_path = os.path.join(self.download_dir, new_name)
                        counter = 1
                        while os.path.exists(new_path):
                            new_path = os.path.join(self.download_dir, f"U_{uasg}_E_{clean_edital}_C_{re.sub(r'[^\w\-]', '_', comprador)}_{dia_disputa.replace('/', '-')}_{counter}{ext}")
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

    def process_editais_page(self, page):
        try:
            self.log(f"Processando página {page}...")
            time.sleep(3)
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".sc-cdmAjP")))
            download_buttons = self.find_download_buttons()
            if not download_buttons:
                self.log("❌ Nenhum botão de download encontrado")
                self.save_debug_screenshot("no_download_buttons")
                return False
            self.log(f"Encontrados {len(download_buttons)} botões de download")
            processed_count = 0
            for index, button in enumerate(download_buttons):
                uasg, edital, comprador, dia_disputa = self.extract_edital_info_from_context(button, index)
                success = self.download_document(button, uasg, edital, comprador, dia_disputa)
                if success:
                    processed_count += 1
                    self.create_trello_card(uasg, edital, success, comprador, dia_disputa)
                time.sleep(2)
            self.log(f"✅ Página {page}: {processed_count} documentos processados")
            return processed_count > 0
        except Exception as e:
            self.log(f"Erro ao processar página {page}: {str(e)}")
            self.save_debug_screenshot(f"process_page_{page}_error")
            return False

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

    def extract_items_from_text(self, text):
        items = []
        text = re.sub(r'\n+', '\n', text)
        item_pattern = re.compile(r'(\d+)\s*-\s*([^0-9]+?)(?=Descrição Detalhada:)', re.DOTALL | re.IGNORECASE)
        for i, match in enumerate(item_pattern.finditer(text)):
            item_num = match.group(1)
            item_nome = match.group(2).strip()
            start_pos = match.start()
            end_pos = list(item_pattern.finditer(text))[i+1].start() if i+1 < len(list(item_pattern.finditer(text))) else len(text)
            item_text = text[start_pos:end_pos]
            descricao = re.search(r'Descrição Detalhada:\s*(.*?)(?=Tratamento Diferenciado:|Aplicabilidade Decreto|$)', item_text, re.DOTALL | re.IGNORECASE)
            descricao = re.sub(r'\s+', ' ', descricao.group(1).strip()) if descricao else ""
            quantidade = re.search(r'Quantidade Total:\s*(\d+)', item_text, re.IGNORECASE)
            valor_unitario = re.search(r'Valor Unitário[^:]*:\s*R?\$?\s*([\d.,]+)', item_text, re.IGNORECASE)
            valor_unitario = valor_unitario.group(1).replace('.', '').replace(',', '.') if valor_unitario else ""
            unidade = re.search(r'Unidade de Fornecimento:\s*([^0-9\n]+?)(?=\s|$|\n)', item_text, re.IGNORECASE)
            local = re.search(r'Local de Entrega[^:]*:\s*([^(\n]+?)(?:\s*\(|$|\n)', item_text, re.IGNORECASE)
            items.append({
                "ARQUIVO": f"item_{i+1}.pdf",
                "Número do Item": item_num,
                "Descrição": f"{item_nome} {descricao}",
                "Quantidade Total": int(quantidade.group(1)) if quantidade else "",
                "Valor Unitário (R$)": valor_unitario,
                "Unidade de Fornecimento": unidade.group(1).strip() if unidade else "",
                "Local de Entrega (Quantidade)": local.group(1).strip() if local else ""
            })
        return items

    def process_pdf_file(self, pdf_path):
        try:
            with fitz.open(pdf_path) as doc:
                text = "".join(page.get_text() for page in doc)
            return self.extract_items_from_text(text) if text.strip() else []
        except Exception as e:
            self.log(f"Erro ao processar PDF {pdf_path}: {e}")
            return []

    def tratar_dataframe(self, df):
        if df.empty:
            return df
        df = df.rename(columns={
            'ARQUIVO': 'ARQUIVO',
            'Número do Item': 'Nº',
            'Descrição': 'DESCRICAO',
            'Quantidade Total': 'QTDE',
            'Valor Unitário (R$)': 'VALOR_UNIT',
            'Unidade de Fornecimento': 'UNID_FORN',
            'Local de Entrega (Quantidade)': 'LOCAL_ENTREGA'
        })
        if 'QTDE' in df.columns:
            df['QTDE'] = pd.to_numeric(df['QTDE'], errors='coerce')
        if 'VALOR_UNIT' in df.columns:
            df['VALOR_UNIT'] = df['VALOR_UNIT'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
            df['VALOR_UNIT'] = pd.to_numeric(df['VALOR_UNIT'], errors='coerce')
        if 'QTDE' in df.columns and 'VALOR_UNIT' in df.columns:
            df['VALOR_TOTAL'] = df['QTDE'] * df['VALOR_UNIT']
        colunas_desejadas = ['ARQUIVO', 'Nº', 'DESCRICAO', 'UNID_FORN', 'QTDE', 'VALOR_UNIT', 'VALOR_TOTAL', 'LOCAL_ENTREGA']
        colunas_desejadas = [col for col in colunas_desejadas if col in df.columns]
        outras_colunas = [col for col in df.columns if col not in colunas_desejadas]
        return df[colunas_desejadas + outras_colunas]

    def pdfs_para_xlsx(self, input_dir=None, output_dir=None):
        input_dir = input_dir or self.download_dir
        output_dir = output_dir or self.orcamentos_dir
        pdf_files = [f for f in os.listdir(input_dir) if f.lower().endswith('.pdf')]
        for file_name in pdf_files:
            pdf_path = os.path.join(input_dir, file_name)
            items = self.process_pdf_file(pdf_path)
            if items:
                df = pd.DataFrame(items)
                df = self.tratar_dataframe(df)
                xlsx_name = os.path.splitext(file_name)[0] + ".xlsx"
                output_path = os.path.join(output_dir, xlsx_name)
                with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Itens')
                    worksheet = writer.sheets['Itens']
                    for column in worksheet.columns:
                        max_length = max(len(str(cell.value or "")) for cell in column)
                        worksheet.column_dimensions[column[0].column_letter].width = min(max_length + 2, 50)
                self.log(f"✅ Convertido: {xlsx_name}")
            else:
                    self.log(f"❌ Nenhum item em: {file_name}")
    def clean_dataframe(df):
        if df.empty:
            return df
        df = df.replace('', pd.NA)
        for col in ['Quantidade Total', 'Valor Unitário (R$)', 'Intervalo Mínimo entre Lances (R$)']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(' ', '').replace('nan', '')
        return df

    def combine_excel_files(self, input_dir=None, output_file=None):
        input_dir = input_dir or self.orcamentos_dir
        output_file = output_file or MASTER_EXCEL
        excel_files = [f for f in os.listdir(input_dir) if f.endswith('.xlsx') and f != os.path.basename(output_file)]
        if not excel_files:
            self.log("Nenhum arquivo Excel encontrado para combinar.")
            return
        dados_combinados = []
        for arquivo in excel_files:
            try:
                xls = pd.ExcelFile(os.path.join(input_dir, arquivo))
                for nome_planilha in xls.sheet_names:
                    df = pd.read_excel(xls, sheet_name=nome_planilha)
                    df['Arquivo'] = arquivo
                    df['Planilha'] = nome_planilha
                    dados_combinados.append(df)
            except Exception as e:
                self.log(f"Erro ao processar {arquivo}: {e}")
        if dados_combinados:
            df_combinado = pd.concat(dados_combinados, ignore_index=True)
            df_combinado.to_excel(output_file, index=False, sheet_name='Resumo')
            self.log(f"✅ Master Excel salvo: {output_file}")

    def create_trello_card(self, uasg, edital, file_name, comprador, dia_disputa):
        try:
            card_name = f"UASG: {uasg} Edital: {edital}"
            url = f"https://api.trello.com/1/cards"
            params = {
                'key': API_KEY,
                'token': TOKEN,
                'idList': LISTAS_PREPARANDO[0],
                'name': card_name,
                'desc': f"Arquivo: {file_name}\nComprador: {comprador}\nDia da Disputa: {dia_disputa}"
            }
            response = requests.post(url, params=params)
            if response.status_code == 200:
                card_id = response.json()['id']
                self.log(f"✅ Card criado: {card_name}")
                self.processed_cards.add(card_id)
                self.register_in_spreadsheet({
                    'new_card_name': card_name,
                    'uasg': uasg,
                    'numero_pregao': edital,
                    'downloads_pregao': file_name,
                    'comprador': comprador,
                    'dia_pregao': dia_disputa,
                    'data_do_pregao': ""
                }, len(self.processed_cards))
        except Exception as e:
            self.log(f"❌ Erro ao criar card: {str(e)}")

    def register_in_spreadsheet(self, card_data, item_number):
        row_data = [
            item_number,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            card_data.get('dia_pregao', ''),
            card_data.get('uasg', ''),
            card_data.get('numero_pregao', ''),
            card_data.get('link_compras_gov', ''),
            card_data.get('downloads_pregao', ''),
            card_data.get('comprador', '')
        ]
        try:
            wb = openpyxl.load_workbook(EXCEL_PATH)
            ws = wb.active
            ws.append(row_data)
            wb.save(EXCEL_PATH)
            self.log(f"✅ Registrado na planilha: {card_data['new_card_name']}")
        except Exception as e:
            self.log(f"❌ Erro ao registrar na planilha: {e}")

    def run(self):
        print("="*60)
        print("🤖 WAVECODE AUTOMATION - PIPELINE COMPLETO")
        print("="*60)
        
        self.log("[1/5] Baixando editais...")
        total_processed = 0
        try:
            self.setup_driver()
            if self.login() and self.navigate_to_editais():
                for page in range(1, 4):
                    self.log(f"Processando página {page}")
                    if self.process_editais_page(page):
                        total_processed += 1
                    if page < 3:
                        try:
                            next_btn = self.driver.find_element(By.CSS_SELECTOR, "a.next, button.next, [aria-label*='next']")
                            next_btn.click()
                            time.sleep(5)
                            self.scroll_to_load_editais()
                        except NoSuchElementException:
                            self.log("Não há mais páginas para processar")
                            break
        except Exception as e:
            self.log(f"Erro no download: {str(e)}")
            self.save_debug_screenshot("download_error")
        finally:
            if self.driver:
                self.driver.quit()
        
        if total_processed == 0:
            self.log("⚠️ Nenhum edital baixado. Abortando pipeline.")
            return
        
        self.log("\n[2/5] Descompactando arquivos...")
        self.descompactar_arquivos()
        
        self.log("\n[3/5] Extraindo PDFs...")
        self.extrair_e_copiar_pdfs()
        
        self.log("\n[4/5] Convertendo para Excel...")
        self.pdfs_para_xlsx()
        
        self.log("\n[5/5] Gerando master Excel...")
        self.combine_excel_files()
        
        print("\n🎉 PIPELINE CONCLUÍDO!")
        print(f"📁 Arquivos em: {self.orcamentos_dir}")
        print(f"📊 Master Excel: {MASTER_EXCEL}")

if __name__ == "__main__":
    automation = WavecodeAutomation(debug=True)
    automation.run()