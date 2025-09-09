from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# Adicione opções para o Chrome
chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--start-maximized") # Inicia o navegador maximizado
chrome_options.add_argument("--disable-infobars") # Evita a barra de "Chrome is being controlled by automated test software"
chrome_options.add_argument("--disable-extensions") # Desabilita extensões
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option('useAutomationExtension', False)

# Configura o driver com as novas opções
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

try:
    print("Acessando a página do Comprasnet Mobile...")
    driver.get("https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/public/compras")
    

    # Espera até que o campo de Unidade de Compra esteja visível
    print("Aguardando os campos de input...")
    unidade_input = WebDriverWait(driver, 20).until(
        EC.visibility_of_element_located((By.XPATH, '//*[@id="pn_id_71_content"]/div/div[2]/div[3]/div[2]/p-inputmask/input'))
    )
    
    # Espera até que o campo de Número da Compra esteja visível
    numero_compra_input = WebDriverWait(driver, 20).until(
        EC.visibility_of_element_located((By.XPATH, '//*[@id="pn_id_71_content"]/div/div[2]/div[4]/div[2]/p-inputmask/input'))
    )

    # Preenche os campos
    print("Preenchendo os dados da licitação...")
    unidade_input.send_keys("158720")
    numero_compra_input.send_keys("900892025")
    
    # Encontra e clica no botão "Acompanhar Compra"
    print("Buscando o botão de 'Acompanhar Compra'...")
    botao_acompanhar = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.XPATH, '//button[contains(.,"Acompanhar Compra")]'))
    )
    botao_acompanhar.click()
    
    print("Botão de 'Acompanhar Compra' clicado. O script continua a partir daqui...")

    # Pausa para visualização
    print("Pausa de 60 segundos para você visualizar a página. Pressione Ctrl+C para encerrar.")
    time.sleep(60)

except Exception as e:
    print(f"Ocorreu um erro: {e}")
finally:
    print("Encerrando o navegador.")
    driver.quit()