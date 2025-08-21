"""
Sistema de Filtragem Inteligente de Editais para Trello

Este script implementa um sistema que:
1. Analisa editais baixados via WaveCode
2. Filtra apenas editais que contêm itens interessantes (instrumentos musicais, áudio, etc.)
3. Cria cards no Trello apenas para editais qualificados
4. Gera relatórios de análise

Autor: arte_comercial
Data: 2025
Versão: 2.0.0 (Sistema de Filtragem Inteligente)
"""

import os
import time
import re
import zipfile
import shutil
from pathlib import Path
import fitz  # PyMuPDF
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
from datetime import datetime
try:
    from zoneinfo import ZoneInfo  # Py 3.9+
except Exception:
    ZoneInfo = None

# === Configuration ===
BASE_DIR = r"G:\Meu Drive\arte_comercial"
DOWNLOAD_DIR = os.path.join(BASE_DIR, "DOWNLOADS")
ORCAMENTOS_DIR = os.path.join(BASE_DIR, "ORCAMENTOS")
EXCEL_PATH = os.path.join(BASE_DIR, "EDITAIS_PC.xlsx")
MASTER_EXCEL = os.path.join(BASE_DIR, "summary.xlsx")
FINAL_MASTER_PATH = os.path.join(BASE_DIR, "master.xlsx")
RELATORIO_FILTRAGEM = os.path.join(BASE_DIR, "relatorio_filtragem.xlsx")

# Palavras-chave para filtro do arte_orca
PALAVRAS_CHAVE = [
    r'Instrumento Musical - Sopro', r'Instrumento Musical - Corda', r'Instrumento Musical - Percursão',
    r'Instrumento Musical', r'Peças e acessórios instrumento musical',
    r'saxofone', r'trompete', r'tuba', r'clarinete', r'óleo lubrificante', r'trompa', r'sax', r'óleos para válvulas',
    r'violão', r'Guitarra', r'Baixo', r'Violino', r'Viola', r'Cavaquinho', r'Bandolim', r'Ukulele', 
    r'Microfone', r'Microfone direcional', r'Suporte microfone', r'Microfone Dinâmico', r'Microfone de Lapela',
    r'Base microfone', r'Pedestal microfone', r'Medusa para microfone', r'Pré-amplificador microfone',
    r'Caixa Acústica', r'Caixa de Som', r'Caixa som', r'Subwoofer', 
    r'Amplificador de áudio', r'Amplificador som', r'Amplificador fone ouvido',
    r'Piano', r'Suporte para teclado', r'Mesa áudio', r'Interface de Áudio',
    r'Pedestal', r'Pedestal caixa acústica', r'Pedal Efeito', r'fone de ouvido', r'headset', 
    r'Bateria Eletrônica', r'Cabo extensor', r'Tela projeção', r'Projetor Multimídia',
]

REGEX_FILTRO = re.compile('|'.join(PALAVRAS_CHAVE), re.IGNORECASE)

# Trello API Configuration
API_KEY = '683cba47b43c3a1cfb10cf809fecb685'
TOKEN = 'ATTA89e63b1ce30ca079cef748f3a99cda25de9a37f3ba98c35680870835d6f2cae034C088A8'
LISTAS_PREPARANDO = ['6650f3369bb9bacb525d1dc8']

class EditalAnalyzer:
    """Classe para análise e filtragem de editais"""
    
    def __init__(self):
        self.palavras_chave = PALAVRAS_CHAVE
        self.regex_filtro = REGEX_FILTRO
        
    def analisar_edital(self, pdf_path):
        """
        Analisa um edital PDF e retorna informações sobre itens interessantes
        """
        try:
            with fitz.open(pdf_path) as doc:
                text = ""
                for page in doc:
                    text += page.get_text()
            
            # Extrair itens do texto
            items = self.extract_items_from_text(text, os.path.basename(pdf_path))
            
            # Analisar cada item
            itens_interessantes = []
            total_itens = len(items)
            itens_com_match = 0
            
            for item in items:
                descricao = item.get('DESCRICAO', '')
                if self.regex_filtro.search(descricao):
                    itens_com_match += 1
                    itens_interessantes.append({
                        'numero_item': item.get('Número do Item', ''),
                        'descricao': descricao,
                        'quantidade': item.get('Quantidade Total', 0),
                        'valor_unitario': item.get('Valor Unitário (R$)', ''),
                        'valor_total': item.get('Valor Total (R$)', ''),
                        'palavras_encontradas': self.encontrar_palavras_chave(descricao)
                    })
            
            return {
                'arquivo': os.path.basename(pdf_path),
                'total_itens': total_itens,
                'itens_interessantes': len(itens_interessantes),
                'percentual_interesse': (len(itens_interessantes) / total_itens * 100) if total_itens > 0 else 0,
                'itens_detalhados': itens_interessantes,
                'qualificado': len(itens_interessantes) > 0
            }
            
        except Exception as e:
            return {
                'arquivo': os.path.basename(pdf_path),
                'erro': str(e),
                'qualificado': False
            }
    
    def encontrar_palavras_chave(self, texto):
        """Encontra quais palavras-chave estão presentes no texto"""
        encontradas = []
        for palavra in self.palavras_chave:
            if re.search(palavra, texto, re.IGNORECASE):
                encontradas.append(palavra)
        return encontradas
    
    def extract_items_from_text(self, text, arquivo_nome):
        """Extrai itens do texto do PDF (método herdado do código original)"""
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

            item_data = {
                "ARQUIVO": arquivo_nome,
                "Número do Item": item_num,
                "DESCRICAO": item_completo,
                "Quantidade Total": int(quantidade) if quantidade.isdigit() else quantidade,
                "Valor Unitário (R$)": valor_unitario,
                "Valor Total (R$)": valor_total,
            }
            items.append(item_data)

        return items

class WavecodeAutomationFiltrado:
    def __init__(self, debug=True):
        self.download_dir = DOWNLOAD_DIR
        self.orcamentos_dir = ORCAMENTOS_DIR
        self.base_url = "https://app2.wavecode.com.br/"
        self.login_email = "pietromrampazzo@gmail.com"
        self.login_password = "Piloto@314"
        self.driver = None
        self.wait = None
        self.debug = debug
        self.analyzer = EditalAnalyzer()
        self.editais_qualificados = []
        self.editais_rejeitados = []
        
        os.makedirs(self.download_dir, exist_ok=True)
        os.makedirs(self.orcamentos_dir, exist_ok=True)
        self.processed_cards = set()

    def log(self, message):
        if self.debug:
            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}] {message}")

    def setup_driver(self):
        """Configura o Chrome WebDriver"""
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

    def login(self):
        """Realiza login no WaveCode"""
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
                return True
            else:
                self.log("❌ Login falhou: Retornado para a página de login.")
                return False
        except Exception as e:
            self.log(f"❌ Erro no login: {str(e)}")
            return False

    def navigate_to_editais(self):
        """Navega para a seção de editais"""
        self.log("Navegando para seção de editais...")
        try:
            self.driver.get(urljoin(self.base_url, "/prospects/list?company_id=2747"))
            self.scroll_to_load_editais()
            self.wait.until(EC.presence_of_element_located((By.XPATH, "//p[contains(text(), 'Disputa:') or contains(text(), 'Edital:')]")))
            self.log("✅ Página de editais carregada.")
            return True
        except Exception as e:
            self.log(f"❌ Erro ao navegar para editais: {str(e)}")
            return False

    def scroll_to_load_editais(self):
        """Rola a página para carregar todos os editais"""
        self.log("Rolando página para carregar todos os editais...")
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        while True:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        self.driver.execute_script("window.scrollTo(0, 0);")
        self.log("✅ Rolagem concluída!")

    def find_download_buttons(self):
        """Encontra botões de download"""
        self.log("Procurando botões de download...")
        try:
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

    def download_document(self, download_element, uasg, edital, comprador, dia_disputa):
        """Baixa um documento"""
        try:
            files_before = set(os.listdir(self.download_dir))
            self.driver.execute_script("arguments[0].scrollIntoView(true);", download_element)
            time.sleep(1)
            
            if download_element.tag_name == 'a':
                self.driver.execute_script("window.open(arguments[0].href, '_blank');", download_element)
                self.driver.switch_to.window(self.driver.window_handles[-1])
                time.sleep(5)
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
                        ext = ext or '.zip'
                        clean_edital = re.sub(r'[^\w\-]', '_', str(edital))
                        clean_comprador = re.sub(r'[^\w\-]', '_', comprador)
                        clean_dia_disputa = dia_disputa.replace(':', 'h').replace(' - ', '_').replace('/', '-') + 'm'
                        new_name = f"U_{uasg}_E_{clean_edital}_C_{clean_comprador}_{clean_dia_disputa}{ext}"
                        new_path = os.path.join(self.download_dir, new_name)
                        counter = 1
                        while os.path.exists(new_path):
                            new_path = os.path.join(self.download_dir, f"U_{uasg}_E_{clean_edital}_C_{clean_comprador}_{clean_dia_disputa}_{counter}{ext}")
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
        """Extrai informações do edital do contexto da página"""
        self.log(f"🔍 Extraindo informações para o item {index+1}...")
        uasg, edital, comprador, dia_disputa = None, None, "Desconhecido", ""
        
        try:
            container_wrapper_header = download_element.find_element(By.XPATH, "./ancestor::div[contains(@class, 'wrapper-header')]")
            container_principal_item = container_wrapper_header.find_element(By.XPATH, "./..")

            try:
                disputa_label = container_principal_item.find_element(By.XPATH, ".//div[contains(@class, 'item-header')]//p[text()='Disputa:']")
                disputa_value_element = disputa_label.find_element(By.XPATH, "./following-sibling::p")
                disputa_text = disputa_value_element.text
                disputa_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s*-\s*\d{1,2}:\d{1,2})', disputa_text)
                if disputa_match:
                    dia_disputa = disputa_match.group(1)
            except NoSuchElementException:
                self.log("Disputa não encontrada para este item.")

            try:
                uasg_label = container_principal_item.find_element(By.XPATH, ".//div[contains(@class, 'item-body-block')]//p[text()='UASG']")
                uasg_value_element = uasg_label.find_element(By.XPATH, "./following-sibling::p")
                uasg_text = uasg_value_element.text
                uasg_match = re.search(r'(\d+)', uasg_text)
                if uasg_match:
                    uasg = uasg_match.group(1)
            except NoSuchElementException:
                self.log("UASG não encontrado para este item.")

            try:
                edital_label = container_principal_item.find_element(By.XPATH, ".//div[contains(@class, 'item-header')]//p[text()='Edital:']")
                edital_value_element = edital_label.find_element(By.XPATH, "./following-sibling::p")
                edital_text = edital_value_element.text
                edital_match = re.search(r'(\d+)', edital_text)
                if edital_match:
                    edital = edital_match.group(1)
            except NoSuchElementException:
                self.log("Edital não encontrado para este item.")

            try:
                comprador_label = container_principal_item.find_element(By.XPATH, ".//div[contains(@class, 'item-body')]//p[text()='Comprador:']")
                comprador_value_element = comprador_label.find_element(By.XPATH, "./following-sibling::p")
                comprador_text = comprador_value_element.text
                comprador = comprador_text.strip()
            except NoSuchElementException:
                self.log("Comprador não encontrado para este item.")
            
            if not uasg: uasg = str(999 + index).zfill(6)
            if not edital: edital = str(index + 1).zfill(8)
            if not comprador: comprador = "Desconhecido"
            
            self.log(f"✅ Extraído: UASG={uasg}, Edital={edital}, Comprador='{comprador}', Disputa='{dia_disputa}'")
            
            return uasg, edital, comprador, dia_disputa

        except Exception as e:
            self.log(f"❌ Erro inesperado na extração de informações do edital: {str(e)}")
            return str(999 + index).zfill(6), str(index + 1).zfill(8), "Desconhecido", ""

    def process_editais_page(self, page_num):
        """Processa uma página de editais com filtragem inteligente"""
        self.log(f"Processando página {page_num}...")
        try:
            download_buttons = self.find_download_buttons()
            
            if not download_buttons:
                self.log("❌ Nenhum botão de download encontrado nesta página.")
                return 0
            
            self.log(f"Encontrados {len(download_buttons)} botões de download para processar.")
            processed_count = 0
            
            for index, button in enumerate(download_buttons):
                uasg, edital, comprador, dia_disputa = self.extract_edital_info_from_context(button, index)
                
                downloaded_file_name = self.download_document(button, uasg, edital, comprador, dia_disputa)
                
                if downloaded_file_name:
                    # Analisar o edital antes de criar card no Trello
                    analise = self.analisar_edital_baixado(downloaded_file_name, uasg, edital, comprador, dia_disputa)
                    
                    if analise['qualificado']:
                        self.log(f"✅ Edital QUALIFICADO: {downloaded_file_name}")
                        self.create_trello_card(uasg, edital, downloaded_file_name, comprador, dia_disputa, analise)
                        self.editais_qualificados.append(analise)
                    else:
                        self.log(f"❌ Edital REJEITADO: {downloaded_file_name}")
                        self.editais_rejeitados.append(analise)
                    
                    processed_count += 1
                else:
                    self.log(f"Falha ao baixar o edital para o item {index+1}.")
                
                time.sleep(2)
            
            self.log(f"✅ Página {page_num}: {processed_count} de {len(download_buttons)} editais processados.")
            return processed_count
            
        except Exception as e:
            self.log(f"Erro ao processar a página {page_num}: {str(e)}")
            return 0

    def analisar_edital_baixado(self, file_name, uasg, edital, comprador, dia_disputa):
        """Analisa um edital baixado para determinar se é interessante"""
        self.log(f"🔍 Analisando edital: {file_name}")
        
        file_path = os.path.join(self.download_dir, file_name)
        
        # Se for um arquivo ZIP, descompactar primeiro
        if file_name.endswith('.zip'):
            try:
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    extract_dir = os.path.join(self.download_dir, file_name.replace('.zip', ''))
                    zip_ref.extractall(extract_dir)
                
                # Procurar por PDFs na pasta extraída
                for root, dirs, files in os.walk(extract_dir):
                    for file in files:
                        if file.lower().endswith('.pdf'):
                            pdf_path = os.path.join(root, file)
                            analise = self.analyzer.analisar_edital(pdf_path)
                            analise.update({
                                'uasg': uasg,
                                'edital': edital,
                                'comprador': comprador,
                                'dia_disputa': dia_disputa,
                                'arquivo_original': file_name
                            })
                            return analise
                
                # Se não encontrou PDF, retornar como não qualificado
                return {
                    'arquivo_original': file_name,
                    'uasg': uasg,
                    'edital': edital,
                    'comprador': comprador,
                    'dia_disputa': dia_disputa,
                    'qualificado': False,
                    'erro': 'Nenhum PDF encontrado no arquivo ZIP'
                }
                
            except Exception as e:
                return {
                    'arquivo_original': file_name,
                    'uasg': uasg,
                    'edital': edital,
                    'comprador': comprador,
                    'dia_disputa': dia_disputa,
                    'qualificado': False,
                    'erro': f'Erro ao descompactar: {str(e)}'
                }
        
        # Se for um PDF direto
        elif file_name.endswith('.pdf'):
            analise = self.analyzer.analisar_edital(file_path)
            analise.update({
                'uasg': uasg,
                'edital': edital,
                'comprador': comprador,
                'dia_disputa': dia_disputa,
                'arquivo_original': file_name
            })
            return analise
        
        else:
            return {
                'arquivo_original': file_name,
                'uasg': uasg,
                'edital': edital,
                'comprador': comprador,
                'dia_disputa': dia_disputa,
                'qualificado': False,
                'erro': 'Formato de arquivo não suportado'
            }

    def create_trello_card(self, uasg, edital, file_name, comprador, dia_disputa, analise):
        """Cria card no Trello apenas para editais qualificados"""
        try:
            card_name = f"🎵 {comprador} - UASG: {uasg} - Edital: {edital}"
            
            # Criar descrição detalhada com informações dos itens interessantes
            descricao_base = (
                f"📁 Arquivo: {file_name}\n"
                f"🏢 Comprador: {comprador}\n"
                f"🔢 UASG: {uasg}\n"
                f"📋 Edital: {edital}\n"
                f"📅 Data de Disputa: {dia_disputa if dia_disputa else 'Não especificada'}\n"
                f"📊 Total de Itens: {analise.get('total_itens', 0)}\n"
                f"🎯 Itens Interessantes: {analise.get('itens_interessantes', 0)}\n"
                f"📈 Percentual de Interesse: {analise.get('percentual_interesse', 0):.1f}%\n\n"
            )
            
            # Adicionar detalhes dos itens interessantes
            if analise.get('itens_detalhados'):
                descricao_base += "🎵 ITENS INTERESSANTES ENCONTRADOS:\n"
                for item in analise['itens_detalhados'][:5]:  # Limitar a 5 itens
                    descricao_base += f"• Item {item['numero_item']}: {item['descricao'][:100]}...\n"
                    descricao_base += f"  💰 Valor: R$ {item['valor_unitario']} | Qtd: {item['quantidade']}\n"
                    descricao_base += f"  🏷️ Palavras-chave: {', '.join(item['palavras_encontradas'][:3])}\n\n"
                
                if len(analise['itens_detalhados']) > 5:
                    descricao_base += f"... e mais {len(analise['itens_detalhados']) - 5} itens\n\n"

            url = f"https://api.trello.com/1/cards"
            params = {
                'key': API_KEY,
                'token': TOKEN,
                'idList': LISTAS_PREPARANDO[0],
                'name': card_name,
                'desc': descricao_base
            }

            # Processar data de disputa
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
                        if ZoneInfo is not None:
                            aware = parsed_date.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
                            params['due'] = aware.isoformat(timespec='seconds')
                        else:
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
                
                self.register_in_spreadsheet({
                    'new_card_name': card_name,
                    'uasg': uasg,
                    'numero_pregao': edital,
                    'downloads_pregao': file_name,
                    'comprador': comprador,
                    'dia_pregao': dia_disputa,
                    'data_do_pregao': parsed_date_for_trello,
                    'itens_interessantes': analise.get('itens_interessantes', 0),
                    'percentual_interesse': analise.get('percentual_interesse', 0)
                }, len(self.processed_cards))
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

    def register_in_spreadsheet(self, card_data, item_number):
        """Registra informações na planilha"""
        row_data = [
            item_number,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            card_data.get('dia_pregao', ''),
            card_data.get('uasg', ''),
            card_data.get('numero_pregao', ''),
            card_data.get('link_compras_gov', ''),
            card_data.get('downloads_pregao', ''),
            card_data.get('comprador', ''),
            card_data.get('itens_interessantes', 0),
            card_data.get('percentual_interesse', 0)
        ]
        try:
            wb = openpyxl.load_workbook(EXCEL_PATH)
            ws = wb.active
            ws.append(row_data)
            wb.save(EXCEL_PATH)
            self.log(f"✅ Registrado na planilha: {card_data['new_card_name']}")
        except Exception as e:
            self.log(f"❌ Erro ao registrar na planilha: {e}")

    def gerar_relatorio_filtragem(self):
        """Gera relatório detalhado da filtragem"""
        self.log("📊 Gerando relatório de filtragem...")
        
        # Dados para o relatório
        dados_relatorio = []
        
        # Editais qualificados
        for edital in self.editais_qualificados:
            dados_relatorio.append({
                'Status': 'QUALIFICADO',
                'Arquivo': edital.get('arquivo_original', ''),
                'UASG': edital.get('uasg', ''),
                'Edital': edital.get('edital', ''),
                'Comprador': edital.get('comprador', ''),
                'Data Disputa': edital.get('dia_disputa', ''),
                'Total Itens': edital.get('total_itens', 0),
                'Itens Interessantes': edital.get('itens_interessantes', 0),
                'Percentual Interesse': f"{edital.get('percentual_interesse', 0):.1f}%",
                'Erro': ''
            })
        
        # Editais rejeitados
        for edital in self.editais_rejeitados:
            dados_relatorio.append({
                'Status': 'REJEITADO',
                'Arquivo': edital.get('arquivo_original', ''),
                'UASG': edital.get('uasg', ''),
                'Edital': edital.get('edital', ''),
                'Comprador': edital.get('comprador', ''),
                'Data Disputa': edital.get('dia_disputa', ''),
                'Total Itens': edital.get('total_itens', 0),
                'Itens Interessantes': edital.get('itens_interessantes', 0),
                'Percentual Interesse': f"{edital.get('percentual_interesse', 0):.1f}%",
                'Erro': edital.get('erro', '')
            })
        
        # Criar DataFrame e salvar
        if dados_relatorio:
            df_relatorio = pd.DataFrame(dados_relatorio)
            df_relatorio.to_excel(RELATORIO_FILTRAGEM, index=False)
            self.log(f"✅ Relatório salvo: {RELATORIO_FILTRAGEM}")
            
            # Estatísticas
            total_editais = len(dados_relatorio)
            qualificados = len(self.editais_qualificados)
            rejeitados = len(self.editais_rejeitados)
            
            self.log(f"📈 ESTATÍSTICAS DA FILTRAGEM:")
            self.log(f"   Total de Editais: {total_editais}")
            self.log(f"   Qualificados: {qualificados} ({qualificados/total_editais*100:.1f}%)")
            self.log(f"   Rejeitados: {rejeitados} ({rejeitados/total_editais*100:.1f}%)")
        else:
            self.log("⚠️ Nenhum dado para gerar relatório")

    def run(self, max_pages_to_process=5):
        """Executa o pipeline completo com filtragem inteligente"""
        print("="*60)
        print("🤖 WAVECODE AUTOMATION - SISTEMA DE FILTRAGEM INTELIGENTE")
        print("="*60)
        
        self.log(f"[1/5] Baixando e analisando editais (processando até {max_pages_to_process} páginas)...")
        total_downloads = 0
        
        try:
            self.setup_driver()
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
                            self.log(f"✅ Clique direto na página '{page_num}' realizado.")
                            time.sleep(5)
                            self.scroll_to_load_editais()
                        except TimeoutException:
                            self.log(f"⚠️ Página de número '{page_num}' não foi encontrada. Fim da paginação.")
                            break
                        except Exception as e:
                            self.log(f"❌ Erro ao tentar navegar para a página {page_num}: {e}")
                            break

                    downloads_in_page = self.process_editais_page(page_num)
                    total_downloads += downloads_in_page
        
        except Exception as e:
            self.log(f"❌ Erro geral na automação: {str(e)}")
        finally:
            if self.driver:
                self.driver.quit()
        
        if total_downloads == 0:
            self.log("⚠️ Nenhum edital foi baixado. Abortando o restante do pipeline.")
            return
        
        self.log(f"\n[2/2] Gerando relatório de filtragem...")
        self.gerar_relatorio_filtragem()

        print("\n🎉 PIPELINE DE FILTRAGEM CONCLUÍDO!")
        print(f"📊 Relatório de Filtragem: {RELATORIO_FILTRAGEM}")
        print(f"✅ Cards criados no Trello: {len(self.editais_qualificados)}")
        print(f"❌ Editais rejeitados: {len(self.editais_rejeitados)}")

if __name__ == "__main__":
    automation = WavecodeAutomationFiltrado()
    automation.run()
