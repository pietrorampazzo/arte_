"""
Nipsey.py - Orquestrador para automação contínua de licitações governamentais.

Funcionalidades:
- Agenda execução diária às 08:00.
- Executa arte_orquestra_gemini.py para baixar editais e atualizar master.xlsx.
- Executa arte_heavy2.py para mapear fornecedores e gerar orçamento.
- Cria/atualiza cards no Trello com markdown organizado e anexa PDFs (RelacaoItens.pdf) e orçamento (master_proposta_corzinha.xlsx).
- Mantém log detalhado para auditoria.

Autor: arte_comercial
Data: 25/08/2025
Versão: 1.0.0
"""
import os
import sys
import time
import logging
import re
import json
from datetime import datetime
import subprocess
import schedule
import requests
import pandas as pd
from hashlib import md5
from pathlib import Path

# === Configurações ===
BASE_DIR = r"C:\Users\pietr\Meu Drive\arte_comercial"
LOG_DIR = os.path.join(BASE_DIR, "LOGS")
ARTE_ORQUESTRA_SCRIPT = os.path.join(BASE_DIR, "arte_orquestra_gemini.py")
ARTE_HEAVY_SCRIPT = os.path.join(BASE_DIR, "arte_heavy2.py")
MASTER_XLSX = os.path.join(BASE_DIR, "master.xlsx")
PROPOSTA_XLSX = os.path.join(BASE_DIR, "sheets/RESULTADO_proposta/master_proposta_corzinha.xlsx")
DOWNLOAD_DIR = os.path.join(BASE_DIR, "DOWNLOADS")
LIVRO_RAZAO_PATH = os.path.join(BASE_DIR, "livro_razao.xlsx")

# Configurações Trello
API_KEY = "683cba47b43c3a1cfb10cf809fecb685"
TOKEN = "ATTA89e63b1ce30ca079cef748f3a99cda25de9a37f3ba98c35680870835d6f2cae034C088A8"
LISTA_PREPARANDO = "6650f3369bb9bacb525d1dc8"  # ID da lista do Trello

# Configuração de logging
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f"nipsey_{datetime.now().strftime('%Y%m%d')}.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger()

# === Funções de Suporte ===
def run_script(script_path, script_name):
    """Executa um script Python e registra o resultado."""
    logger.info(f"Iniciando execução do script: {script_name}")
    start_time = time.time()
    
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            check=True
        )
        logger.info(f"Script {script_name} concluído em {time.time() - start_time:.2f} segundos.")
        logger.debug(f"Saída do {script_name}:\n{result.stdout}")
        if result.stderr:
            logger.warning(f"Avisos/Erros do {script_name}:\n{result.stderr}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Erro ao executar {script_name}: {e}")
        logger.error(f"Saída de erro: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Erro inesperado ao executar {script_name}: {e}")
        return False

def load_processed_cards():
    """Carrega cards já criados no Trello para evitar duplicatas."""
    try:
        url = f"https://api.trello.com/1/lists/{LISTA_PREPARANDO}/cards?key={API_KEY}&token={TOKEN}"
        response = requests.get(url)
        response.raise_for_status()
        cards = response.json()
        processed = {re.search(r'Edital: (\d+)', card['name']).group(1) for card in cards if re.search(r'Edital: (\d+)', card['name'])}
        logger.info(f"Carregados {len(processed)} cards existentes do Trello.")
        return processed
    except Exception as e:
        logger.error(f"Erro ao carregar cards do Trello: {e}")
        return set()

def generate_markdown_for_card(edital, df_proposta, df_master):
    """Gera conteúdo em markdown para o card do Trello."""
    df_edital = df_master[df_master['ARQUIVO'].str.contains(str(edital), na=False)]
    df_proposta_edital = df_proposta[df_proposta['ARQUIVO'].str.contains(str(edital), na=False)] if os.path.exists(PROPOSTA_XLSX) else pd.DataFrame()

    if df_edital.empty:
        return "Nenhum item encontrado para este edital."

    markdown = "## Itens do Edital\n"
    markdown += "| Nº | Descrição | Unidade | Qtde | Valor Unit. | Valor Total | Local Entrega | Intervalo Lances |\n"
    markdown += "|----|-----------|---------|------|-------------|-------------|---------------|------------------|\n"
    
    for _, row in df_edital.iterrows():
        markdown += (
            f"| {row['Nº']} | {row['DESCRICAO'][:100]}... | {row.get('UNID_FORN', 'N/A')} | {row.get('QTDE', 'N/A')} | "
            f"{row.get('VALOR_UNIT', 'N/A')} | {row.get('VALOR_TOTAL', 'N/A')} | {row.get('LOCAL_ENTREGA', 'N/A')} | "
            f"{row.get('INTERVALO_LANCES', 'N/A')} |\n"
        )

    if not df_proposta_edital.empty:
        markdown += "\n## Sugestões de Fornecedores\n"
        for _, row in df_proposta_edital.iterrows():
            markdown += f"**Item Nº {row['Nº']} - {row['DESCRICAO_EDITAL'][:50]}...**\n"
            markdown += f"- **Marca**: {row.get('MARCA_SUGERIDA', 'N/A')}\n"
            markdown += f"- **Modelo**: {row.get('MODELO_SUGERIDO', 'N/A')}\n"
            markdown += f"- **Valor**: R$ {row.get('CUSTO_FORNECEDOR', 'N/A')} (+53%) = R$ {row.get('PRECO_FINAL_VENDA', 'N/A')}\n"
            markdown += f"- **Descrição Fornecedor**: {row.get('DESCRICAO_FORNECEDOR', 'N/A')}\n"
            markdown += f"- **Análise de Compatibilidade**: {row.get('ANALISE_COMPATIBILIDADE', 'N/A')}\n\n"

    return markdown

def create_or_update_trello_card(uasg, edital, file_name, comprador, dia_disputa, df_proposta, df_master):
    """Cria ou atualiza um card no Trello com anexos."""
    card_name = f"Comprador: {comprador} - UASG: {uasg} - Edital: {edital}"
    card_description = (
        f"**Detalhes do Edital**\n"
        f"- Arquivo: {file_name}\n"
        f"- Comprador: {comprador}\n"
        f"- UASG: {uasg}\n"
        f"- Edital: {edital}\n"
        f"- Data de Disputa: {dia_disputa if dia_disputa else 'Não especificada'}\n"
    )

    # Gerar markdown com itens e sugestões
    markdown_content = generate_markdown_for_card(edital, df_proposta, df_master)
    card_description += f"\n{markdown_content}"

    # Converter data de disputa para formato Trello
    due_date = None
    if dia_disputa:
        try:
            possible_formats = ["%d-%m-%Y - %H:%M", "%d/%m/%Y - %H:%M", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M"]
            for fmt in possible_formats:
                try:
                    parsed_date = datetime.strptime(dia_disputa.replace('h', ':').replace('m', ''), fmt)
                    due_date = parsed_date.strftime("%Y-%m-%dT%H:%M:%S-03:00")
                    break
                except ValueError:
                    continue
        except Exception as e:
            logger.error(f"Erro ao processar data de disputa: {e}")

    # Verificar se o card já existe
    processed_cards = load_processed_cards()
    card_id = None
    if str(edital) in processed_cards:
        logger.info(f"Card para edital {edital} já existe. Atualizando...")
        # Buscar ID do card
        url = f"https://api.trello.com/1/lists/{LISTA_PREPARANDO}/cards?key={API_KEY}&token={TOKEN}"
        response = requests.get(url)
        for card in response.json():
            if re.search(rf'Edital: {edital}\b', card['name']):
                card_id = card['id']
                break
        if card_id:
            url = f"https://api.trello.com/1/cards/{card_id}?key={API_KEY}&token={TOKEN}"
            params = {'desc': card_description}
            if due_date:
                params['due'] = due_date
            response = requests.put(url, params=params)
            logger.info(f"Card atualizado: {card_name}")
    else:
        # Criar novo card
        url = f"https://api.trello.com/1/cards?key={API_KEY}&token={TOKEN}"
        params = {
            'name': card_name,
            'desc': card_description,
            'idList': LISTA_PREPARANDO
        }
        if due_date:
            params['due'] = due_date
        response = requests.post(url, params=params)
        if response.status_code == 200:
            card_id = response.json()['id']
            logger.info(f"Card criado: {card_name} (ID: {card_id})")
        else:
            logger.error(f"Falha ao criar card: {response.text}")
            return False

    # Anexar arquivos
    if card_id:
        # Anexar RelacaoItens.pdf
        file_path = os.path.join(DOWNLOAD_DIR, f"{file_name.replace('.zip', '')}/RelacaoItens.pdf")
        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                files = {'file': f}
                attach_url = f"https://api.trello.com/1/cards/{card_id}/attachments?key={API_KEY}&token={TOKEN}"
                response = requests.post(attach_url, files=files)
                if response.status_code == 200:
                    logger.info(f"Anexo adicionado: {file_path}")
                else:
                    logger.error(f"Falha ao anexar {file_path}: {response.text}")

        # Anexar master_proposta_corzinha.xlsx
        if os.path.exists(PROPOSTA_XLSX):
            with open(PROPOSTA_XLSX, 'rb') as f:
                files = {'file': f}
                attach_url = f"https://api.trello.com/1/cards/{card_id}/attachments?key={API_KEY}&token={TOKEN}"
                response = requests.post(attach_url, files=files)
                if response.status_code == 200:
                    logger.info(f"Anexo adicionado: {PROPOSTA_XLSX}")
                else:
                    logger.error(f"Falha ao anexar {PROPOSTA_XLSX}: {response.text}")

    return True

def pipeline_diario():
    """Executa o pipeline completo: extração, mapeamento e atualização no Trello."""
    logger.info("="*60)
    logger.info(f"Iniciando pipeline diário - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*60)

    # Passo 1: Executar arte_orquestra_gemini.py
    logger.info("Passo 1: Extraindo editais (arte_orquestra_gemini.py)")
    success_orquestra = run_script(ARTE_ORQUESTRA_SCRIPT, "arte_orquestra_gemini.py")
    
    if not success_orquestra:
        logger.error("Falha na extração de editais. Abortando pipeline.")
        return

    # Verificar se master.xlsx foi gerado/atualizado
    if not os.path.exists(MASTER_XLSX):
        logger.error(f"Arquivo master.xlsx não encontrado em {MASTER_XLSX}. Abortando mapeamento.")
        return

    # Passo 2: Executar arte_heavy2.py
    logger.info("Passo 2: Mapeando fornecedores (arte_heavy2.py)")
    success_heavy = run_script(ARTE_HEAVY_SCRIPT, "arte_heavy2.py")
    
    if not success_heavy:
        logger.error("Falha no mapeamento de fornecedores. Prosseguindo para Trello com dados parciais.")
    
    # Passo 3: Criar/atualizar cards no Trello
    logger.info("Passo 3: Criando/atualizando cards no Trello")
    try:
        df_master = pd.read_excel(MASTER_XLSX)
        df_proposta = pd.read_excel(PROPOSTA_XLSX) if os.path.exists(PROPOSTA_XLSX) else pd.DataFrame()
        df_livro_razao = pd.read_excel(LIVRO_RAZAO_PATH) if os.path.exists(LIVRO_RAZAO_PATH) else pd.DataFrame()
        
        # Processar apenas editais novos ou atualizados
        processed_cards = load_processed_cards()
        new_bids = df_livro_razao[df_livro_razao['Timestamp'].str.contains(datetime.now().strftime('%Y-%m-%d'))]
        
        for _, bid in new_bids.iterrows():
            uasg = bid['UASG']
            edital = bid['Edital']
            file_name = bid['Arquivo Download']
            comprador = bid['Comprador']
            dia_disputa = bid['Dia Disputa']
            
            if str(edital) not in processed_cards or os.path.exists(PROPOSTA_XLSX):
                logger.info(f"Processando card para edital {edital}...")
                create_or_update_trello_card(uasg, edital, file_name, comprador, dia_disputa, df_proposta, df_master)
        
        logger.info("Processo de criação/atualização de cards concluído.")
    except Exception as e:
        logger.error(f"Erro ao processar cards no Trello: {e}")

    logger.info("Pipeline diário concluído!")

def main():
    """Configura o agendamento para execução diária."""
    logger.info("Iniciando Nipsey.py - Orquestrador de Pipeline Contínuo")
    
    # Agendar execução diária às 08:00
    schedule.every().day.at("08:00").do(pipeline_diario)
    
    logger.info("Aguardando próxima execução agendada às 08:00...")
    while True:
        schedule.run_pending()
        time.sleep(60)  # Verifica a cada 60 segundos

if __name__ == "__main__":
    main()