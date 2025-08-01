import uuid
import os
from datetime import datetime
import re
from trello import TrelloClient
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

class Card:
    def __init__(self, title, description, owner=None, attachments=None):
        self.id = str(uuid.uuid4())
        self.title = title
        self.description = description
        self.owner = owner
        self.attachments = attachments or []
        self.status = "Not Started"

class StartupFlow:
    def __init__(self, trello_key, trello_token, google_credentials_file):
        self.cards = []
        self.trello_client = TrelloClient(api_key=trello_key, api_secret=None, token=trello_token)
        self.google_credentials_file = google_credentials_file
        self.principles = [
            "Make Requirements Less Dumb",
            "Delete the Part or Process Step",
            "Optimize",
            "Accelerate",
            "Automate"
        ]
        self.setup_google_sheets()
        self.setup_google_drive()

    def setup_google_sheets(self):
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(self.google_credentials_file, scope)
        self.gspread_client = gspread.authorize(creds)
        self.sheet = self.gspread_client.open("Licitações").sheet1

    def setup_google_drive(self):
        creds = ServiceAccountCredentials.from_json_keyfile_name(self.google_credentials_file, ["https://www.googleapis.com/auth/drive"])
        self.drive_service = build('drive', 'v3', credentials=creds)

    def add_card(self, title, description, owner=None, attachments=None):
        card = Card(title, description, owner, attachments)
        self.cards.append(card)
        return card

    def extract_txt_data(self, txt_content):
        lines = txt_content.split('\n')
        uasg = None
        preg_number = None
        for line in lines[1:4]:  # Linhas 2, 3, 4
            if 'UASG' in line:
                uasg = re.search(r'\d+', line).group()
            if 'Pregão' in line or 'Dispensa' in line:
                preg_number = re.search(r'\d+', line).group()
        return uasg, preg_number

    def job_1_trello_card(self, card_id, list_id):
        # Acessar card no Trello
        board = self.trello_client.get_board(list_id)
        card = board.get_card(card_id)
        attachments = card.fetch_attachments()
        
        for attachment in attachments:
            if attachment['name'].endswith('.txt'):
                txt_url = attachment['url']
                # Simular download do .txt (você precisará implementar a lógica de download real)
                txt_content = "Simulated TXT Content\nUASG: 123456\nPregão: 789\nData: 2025-07-04"  # Substituir por download real
                uasg, preg_number = self.extract_txt_data(txt_content)
                if uasg and preg_number:
                    new_title = f"U_{uasg}_N_{preg_number}"
                    card.set_name(new_title)
                    # Atualizar Google Sheets (Coluna F com URL do edital)
                    self.sheet.append_row([card_id, new_title, txt_url, uasg, preg_number, attachment['url']])
                break

    def job_2_download_files(self, card_id, list_id):
        board = self.trello_client.get_board(list_id)
        card = board.get_card(card_id)
        attachments = card.fetch_attachments()
        
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
        for attachment in attachments:
            if 'comprasnet' in attachment['url']:
                driver.get(attachment['url'])
                try:
                    download_button = driver.find_element(By.XPATH, "/html/body/app-root/div/div/div/app-cabecalho-compra-acesso-publico/app-cabecalho-compra/div[4]/div[2]/div/app-botoes-cabecalho-compra/span/span/app-botao-relatorios-compra/span/app-botao-icone/span/button/i")
                    download_button.click()
                    # Simular espera pelo download
                    downloaded_file = "downloaded_file.zip"  # Substituir por lógica real de captura do arquivo
                    uasg, preg_number = self.extract_txt_data("Simulated TXT Content\nUASG: 123456\nPregão: 789\nData: 2025-07-04")
                    new_filename = f"U_{uasg}_N_{preg_number}_E.{downloaded_file.split('.')[-1]}"
                    
                    # Upload para Google Drive
                    file_metadata = {'name': new_filename, 'parents': ['ID_DA_PASTA_LICITACOES']}
                    media = MediaFileUpload(downloaded_file)
                    self.drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
                except Exception as e:
                    print(f"Erro ao baixar arquivo: {e}")
        driver.quit()

    def apply_musk_principles(self):
        for principle in self.principles:
            print(f"\nApplying Principle: {principle}")
            for card in self.cards:
                print(f"  Card: {card.title}")
                print(f"    Description: {card.description}")
                if principle == "Make Requirements Less Dumb":
                    print(f"    Action: Simplify requirements for {card.title}")
                elif principle == "Delete the Part or Process Step":
                    print(f"    Action: Identify unnecessary steps in {card.title}")
                elif principle == "Optimize":
                    print(f"    Action: Streamline processes in {card.title}")
                elif principle == "Accelerate":
                    print(f"    Action: Speed up execution of {card.title}")
                elif principle == "Automate":
                    print(f"    Action: Automate repetitive tasks in {card.title}")
                print(f"    Owner: {card.owner if card.owner else 'TBD'}")
                print(f"    Status: {card.status}")

    def generate_organogram(self):
        print("\n=== Organogram ===")
        for card in self.cards:
            print(f"Card ID: {card.id}")
            print(f"Title: {card.title}")
            print(f"Owner: {card.owner if card.owner else 'TBD'}")
            print(f"Description: {card.description}")
            print("-" * 50)

    def generate_funnel(self):
        print("\n=== Execution Funnel ===")
        stages = ["Ideation", "Simplification", "Optimization", "Acceleration", "Automation"]
        for stage in stages:
            print(f"\nStage: {stage}")
            for card in self.cards:
                print(f"  - {card.title}: {card.description[:50]}...")
                print(f"    Owner: {card.owner if card.owner else 'TBD'}")

if __name__ == "__main__":
    flow = StartupFlow(
        trello_key="683cba47b43c3a1cfb10cf809fecb685",
        trello_token="ATTA89e63b1ce30ca079cef748f3a99cda25de9a37f3ba98c35680870835d6f2cae034C088A8",
        google_credentials_file=r"C:\Users\pietr\Desktop\credentials.json"


    )
    
    # Adicionar os 8 cards
    flow.add_card("Pipeline - Coleta de Dados", "Captura de licitações via Trello e ComprasNet", "Owner 1")
    flow.add_card("Download do Arquivo", "Leitura e planilhamento de arquivos baixados", "Owner 2")
    flow.add_card("Preparação da Disputa", "Plotagem no bot Wavecode e respostas ao pregoeiro", "Owner 3")
    flow.add_card("Automações", "Integração de ferramentas e bots de IA", "Owner 4")
    flow.add_card("Prompt Agente Edital (GPT)", "Extração de dados para planilha orçamentária", "Owner 5")
    flow.add_card("Prompt Agente Orçamentário (Manus)", "Busca de correspondências em sites de fornecedores", "Owner 6")
    flow.add_card("Prompt DeepSeek", "Cruzamento de editais com planilha de fornecedores", "Owner 7")
    flow.add_card("Prompt Qwen", "Automação de cruzamento de dados com fornecedores", "Owner 8")
    
    # Simular execução dos jobs
    flow.job_1_trello_card("CARD_ID", "LIST_ID")
    flow.job_2_download_files("CARD_ID", "LIST_ID")
    
    # Gerar organograma e funil
    flow.generate_organogram()
    flow.apply_musk_principles()
    flow.generate_funnel()

'''
**Notas sobre o Script**:
- **Job 1**: O método `job_1_trello_card` extrai UASG e número do pregão do `.txt`, renomeia o card no Trello e atualiza a coluna F do Google Sheets com o URL do edital.
- **Job 2**: O método `job_2_download_files` usa Selenium para clicar no botão de download (XPath fornecido) e renomeia arquivos no formato `U_xxx_N_yyy_E`. Os arquivos são enviados ao Google Drive.
- **Credenciais**: Substitua `SUA_TRELLO_KEY`, `SEU_TRELLO_TOKEN` e `credentials.json` pelas suas credenciais reais.
- **Download Simulado**: A lógica de download de arquivos (.txt e arquivos do pregão) está simulada. Você precisará implementar o download real usando `requests` ou outra biblioteca.
- **Google Drive**: Substitua `ID_DA_PASTA_LICITACOES` pelo ID real da pasta no Google Drive.

---

### Prompts para Agentes de IA

Os prompts fornecidos para os agentes (Cards 5, 6, 7, 8) estão bem estruturados. Abaixo, destaco como eles se integram ao pipeline e sugiro pequenas otimizações:

1. **Prompt Agente Edital (GPT, Card 5)**:
   - **Integração**: Este agente é executado no Card 2 (Download do Arquivo), após a leitura de arquivos (2.1). Ele gera a planilha orçamentária padrão, que é usada pelos agentes dos Cards 6, 7 e 8.
   - **Otimização**: Adicionar validação de duplicatas na tabela principal do edital para evitar redundâncias.

2. **Prompt Agente Orçamentário (Manus, Card 6)**:
   - **Integração**: Atua na fase de Optimization, buscando correspondências em sites externos (Hayamax, Musical Express). Alimenta a tabela de disputa com sugestões de produtos.
   - **Otimização**: Incluir cache local para evitar consultas repetidas aos sites, acelerando o processo.

3. **Prompt DeepSeek (Card 7)**:
   - **Integração**: Executado em paralelo com o Card 8, cruza dados do edital com a planilha "FORNECEDOR". Seu output é usado no Card 3 para plotagem no bot Wavecode.
   - **Otimização**: Adicionar logging detalhado para rastrear correspondências com <80% de compatibilidade, facilitando ajustes manuais.

4. **Prompt Qwen (Card 8)**:
   - **Integração**: Similar ao Card 7, mas com foco em automação completa e validação rigorosa de categorias. Também alimenta o Card 3.
   - **Otimização**: Implementar busca na web (usando DeepSearch, se disponível) apenas para casos com <80% de compatibilidade, garantindo maior precisão.

---

### Próximos Passos

1. **Validação do Script**:
   - Teste o script com credenciais reais e um card de exemplo no Trello. Confirme se os jobs 1 e 2 funcionam como esperado.
   - Se necessário, posso ajudar a implementar a lógica de download real para `.txt` e arquivos do pregão.

2. **Diagrama Visual**:
   - Posso gerar um diagrama SVG ou HTML para o organograma, usando ferramentas como Mermaid ou Graphviz. Deseja que eu crie?

3. **Integração dos Agentes**:
   - Posso criar exemplos de chamadas de API para os prompts (GPT, Manus, DeepSeek, Qwen) e integrá-los ao script. Prefere um agente específico?

4. **Funil Detalhado**:
   - Posso expandir o funil com ações específicas para cada card em cada etapa, incluindo prazos e responsáveis.

Por favor, confirme:
- Se o script atende aos jobs solicitados ou se precisa de ajustes.
- Se deseja o diagrama visual ou mais detalhes em alguma parte.
- Quais planilhas ("DISPUTA" e "FORNECEDOR") devo usar para testar os prompts DeepSeek e Qwen (os links fornecidos não são acessíveis para mim).

Com essas informações, posso refinar o processo e entregar um pipeline ainda mais fluido!
'''