import requests
import pandas as pd
import os
import logging
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import re
from dotenv import load_dotenv  # pip install python-dotenv
import time
from collections import Counter

# Carregar variáveis de ambiente de .env
load_dotenv()

# Configurações
API_KEY = os.getenv('TRELLO_API_KEY')
TOKEN = os.getenv('TRELLO_API_TOKEN')
BOARD_ID = '68569b7191cc868682152923'  # ID do board do JSON atualizado
EXCEL_FILE = 'livro_razao.xlsx'  # Arquivo Excel a ser complementado

# Headers padrão (usados se Excel não existir; ajustados automaticamente se existir)
HEADERS = ['UASG', 'Numero_Pregao', 'Tipo_Processo', 'Comprador', 'Link_Compras_Gov', 'Data_Pregao', 'Nome_Card', 'Status']

# Configurar logging (INFO para resumo; mude para DEBUG se precisar de mais detalhes)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Função para limpar valor para chave (remove '/', '-', espaços extras)
def clean_for_key(value):
    if not value:
        return ''
    # Garante que o valor seja uma string antes de usar regex
    value_str = str(value)
    # Remove '/', '-', e normaliza
    cleaned = re.sub(r'[/\-]', '', value_str)  # Remove / e -
    cleaned = re.sub(r'\s+', '', cleaned)  # Remove espaços
    return cleaned[:50]  # Limita a 50 chars

# Função para obter todos os cards do board com paginação
def get_all_cards_from_board(board_id):
    all_cards = []
    url = f"https://api.trello.com/1/boards/{board_id}/cards"
    params = {'key': API_KEY, 'token': TOKEN, 'limit': 1000, 'fields': 'id,name,idList,due,dueComplete,idLabels'}  # Campos essenciais
    page = 0
    while True:
        logger.debug(f"Buscando página {page + 1} de cards...")
        response = requests.get(url, params=params, timeout=30)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logger.error(f"Erro HTTP na API Trello (página {page}): {e.response.status_code} - {e.response.text[:200]}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão na API Trello: {e}")
            raise
        
        cards_batch = response.json()
        if not cards_batch:
            logger.info("Nenhuma página adicional encontrada.")
            break
        
        all_cards.extend(cards_batch)
        logger.info(f"Página {page + 1}: {len(cards_batch)} cards obtidos. Total acumulado: {len(all_cards)}")
        
        if len(cards_batch) < 1000:
            break  # Última página
        
        # Paginação: use 'before' do último card
        params['before'] = cards_batch[-1]['id']
        page += 1
        time.sleep(0.1)  # Rate limit: 100 req/minuto no Trello free
    
    return all_cards

# Função para buscar anexos de um card
def get_attachments(card_id):
    url = f"https://api.trello.com/1/cards/{card_id}/attachments"
    params = {'key': API_KEY, 'token': TOKEN}
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao buscar anexos para o card {card_id}: {e}")
        return []

# Função para extrair dados de um anexo .txt
def extract_data_from_txt_attachment(attachment):
    logger.debug(f"Baixando conteúdo do anexo: {attachment.get('name')}")
    try:
        response = requests.get(attachment['url'], headers={'Authorization': f'OAuth oauth_consumer_key="{API_KEY}", oauth_token="{TOKEN}"'}, timeout=15)
        response.raise_for_status()
        content = response.text.strip()
        lines = content.splitlines()
        
        data = {}
        # Extrai novo nome do card das primeiras linhas, se houver
        if len(lines) >= 4:
            data['new_card_name'] = f"{lines[1].strip()} - {lines[2].strip()} - {lines[3].strip()}"

        for line in lines:
            line = line.strip()
            if 'UASG' in line or 'Uasg' in line:
                uasg_match = re.search(r'(\d{6})', line)
                if uasg_match:
                    data['UASG'] = uasg_match.group(1)
            if 'Pregão' in line or 'Dispensa' in line:
                pregao_match = re.search(r'(\d+/\d{4})', line)
                if pregao_match:
                    data['Numero_Pregao'] = pregao_match.group(1)
        return data
    except Exception as e:
        logger.error(f"Falha ao processar anexo .txt {attachment.get('id')}: {e}")
        return None

# Função para extrair dados estruturados diretamente do nome do card (sem download)
def extract_structured_data_from_name(card_name):
    data = {}
    temp_name = card_name  # Cria uma cópia temporária para manipulação
    
    # 1. Extrai e REMOVE o UASG do nome temporário para não confundir com o pregão
    uasg_match = re.search(r'UASG[:\s]*(\d+)', temp_name, re.IGNORECASE)
    if uasg_match:
        data['UASG'] = uasg_match.group(1)
        temp_name = temp_name.replace(uasg_match.group(0), '') # Remove a string "UASG XXX"

    # 2. Tenta encontrar o padrão mais comum (número + ano) no nome limpo
    # Ex: 99/2024, 992024, 12345/2024, 123452024
    pregao_match = re.search(r'\b(\d{1,5}[/]?\d{4})\b', temp_name)
    if pregao_match:
        data['Numero_Pregao'] = pregao_match.group(1).strip()
    else:
        # 3. Se falhar, procura por qualquer número com 5 a 10 dígitos que sobrou
        pregao_fallback = re.search(r'\b(\d{5,10})\b', temp_name)
        if pregao_fallback:
            data['Numero_Pregao'] = pregao_fallback.group(1).strip()
    
    # UASG
    uasg_match = re.search(r'UASG[:\s]*(\d+)', card_name, re.IGNORECASE)
    if uasg_match:
        data['UASG'] = uasg_match.group(1)
    
    # Tipo
    tipo_match = re.search(r'(Pregão|Dispensa|SRP|Edital)', card_name, re.IGNORECASE)
    if tipo_match:
        data['Tipo_Processo'] = tipo_match.group(1).upper()
    
    # Comprador: Início do nome até UASG ou Pregão
    comprador_match = re.match(r'^(.+?)(?:\s*[-–]\s*UASG|\s*[-–]\s*(?:Pregão|Dispensa)|$)', card_name)
    if comprador_match:
        data['Comprador'] = comprador_match.group(1).strip()
    
    # Link: Procura por URL no nome
    link_match = re.search(r'https?://compras\.gov\.br/[^ \n]+', card_name)
    if link_match:
        data['Link_Compras_Gov'] = link_match.group(0)
    
    # Data: Procura por data no nome
    data_match = re.search(r'(\d{2}/\d{2}/\d{4})', card_name)
    if data_match:
        data['Data_Pregao'] = data_match.group(1)
    
    return data

# Função para renomear o card no Trello se o Numero_Pregao contiver '/'
def rename_card_if_needed(card_id, card_name, numero_pregao):
    if numero_pregao and '/' in numero_pregao:
        numero_sem_barra = numero_pregao.replace('/', '')
        novo_nome = card_name.replace(numero_pregao, numero_sem_barra)
        
        if novo_nome != card_name:
            logger.info(f"Renomeando card {card_id}: '{card_name[:30]}...' -> '{novo_nome[:30]}...'")
            url = f"https://api.trello.com/1/cards/{card_id}"
            params = {'key': API_KEY, 'token': TOKEN, 'name': novo_nome}
            try:
                response = requests.put(url, params=params, timeout=15)
                response.raise_for_status()
                logger.info(f"Card {card_id} renomeado com sucesso.")
                return novo_nome # Retorna o novo nome para uso imediato
            except requests.exceptions.RequestException as e:
                logger.error(f"Erro ao tentar renomear o card {card_id}: {e}")
    
    return card_name # Retorna o nome original se não houver alteração

# Função principal para processar um card e extrair dados (apenas do JSON do card)
def process_card(card, index, total_cards):
    card_name = card.get('name', '')
    logger.info(f"Processando card {index + 1}/{total_cards}: {card_name} (ID: {card['id']})")
    
    extracted_from_txt = False
    data_from_txt = {}

    # 1. Tenta extrair dados do anexo .txt primeiro
    attachments = get_attachments(card['id'])
    txt_attachment = next((a for a in attachments if a['name'].lower().endswith('.txt')), None)
    
    if txt_attachment:
        logger.info(f"Anexo .txt encontrado: '{txt_attachment['name']}'. Tentando extrair dados.")
        data_from_txt = extract_data_from_txt_attachment(txt_attachment)
        if data_from_txt:
            extracted_from_txt = True
            logger.info("Dados extraídos com sucesso do anexo .txt.")

    card_data = {
        'Nome_Card': card.get('name', ''),
        'Status': card.get('idList', ''),  # ID da lista como status
        'UASG': data_from_txt.get('UASG', ''),
        'Numero_Pregao': data_from_txt.get('Numero_Pregao', ''),
        'Tipo_Processo': '', 'Comprador': '', 'Link_Compras_Gov': '', 'Data_Pregao': ''
    }

    # 2. Se a extração do .txt falhou, usa o nome do card como fallback
    if not extracted_from_txt:
        logger.info("Nenhum anexo .txt válido encontrado. Extraindo dados do nome do card.")
        extracted_from_name = extract_structured_data_from_name(card_name)
        card_data.update(extracted_from_name)
    else:
        # Se extraiu do .txt, renomeia o card se um novo nome foi sugerido
        if 'new_card_name' in data_from_txt and data_from_txt['new_card_name']:
            logger.info(f"Renomeando card com base no .txt para: '{data_from_txt['new_card_name']}'")
            # Aqui você pode chamar uma função de renomeação específica
            # Por simplicidade, vamos apenas atualizar o nome localmente por enquanto
            # e deixar a função `rename_card_if_needed` cuidar da API
            card_name = data_from_txt['new_card_name'] # Atualiza o nome para a próxima etapa

    # Renomeia o card no Trello se necessário e atualiza o nome localmente
    novo_nome = rename_card_if_needed(card['id'], card_name, card_data.get('Numero_Pregao'))
    card_data['Nome_Card'] = novo_nome
    
    # Adicionar outros metadados diretos do card
    if card.get('due'):
        card_data['Data_Pregao'] = card['due'][:10]  # Formato YYYY-MM-DD -> DD/MM/YYYY se necessário
    if card.get('idLabels') and not card_data.get('Tipo_Processo'):
        card_data['Tipo_Processo'] = f"Labels: {','.join(card['idLabels'])}"  # Append labels se não extraído
    
    # Chave de duplicata refinada: UASG + Numero_limpo (remove /)
    uasg = card_data['UASG'] or 'N/A'
    numero_raw = card_data['Numero_Pregao'] or card_data['Nome_Card']
    numero_limpo = clean_for_key(numero_raw)
    chave_duplicata = f"{uasg}_{numero_limpo}" if uasg != 'N/A' else f"N/A_{numero_limpo}"
    
    logger.debug(f"Chave gerada para card {card['id']}: {chave_duplicata}")
    
    return card_data, chave_duplicata

# Função para complementar o Excel com backup
def update_excel(new_data_list, duplicatas_encontradas):
    backup_file = f"{EXCEL_FILE.replace('.xlsx', '')}_backup_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xlsx"
    
    if os.path.exists(EXCEL_FILE):
        # Backup automático
        df_existing = pd.read_excel(EXCEL_FILE)
        df_existing.to_excel(backup_file, index=False)
        logger.info(f"Backup criado: {backup_file}")
        
        # Detectar headers reais
        real_headers = list(df_existing.columns)
        logger.info(f"Headers detectados no Excel existente: {real_headers}")
    else:
        # Criar novo com headers padrão
        real_headers = HEADERS
        logger.info(f"Arquivo não existe. Criando com headers: {real_headers}")
        df_existing = pd.DataFrame(columns=real_headers)
    
    # Chaves existentes no Excel (com limpeza refinada)
    existing_chaves = set()
    for idx, row in df_existing.iterrows():
        uasg = row.get('UASG', '') or 'N/A'
        numero_raw = row.get('Numero_Pregao', '') or row.get('Nome_Card', '')
        numero_limpo = clean_for_key(numero_raw)
        chave = f"{uasg}_{numero_limpo}" if uasg != 'N/A' else f"N/A_{numero_limpo}"
        if chave != 'N/A_' and chave != 'N/A_N/A':  # Ignora chaves genéricas
            existing_chaves.add(chave)
    
    # Filtrar novos dados (com limpeza)
    novos_registros = []
    duplicatas_no_excel = []
    parciais = 0  # Contador de cards sem Numero extraído
    for data in new_data_list:
        uasg = data['UASG'] or 'N/A'
        numero_raw = data['Numero_Pregao'] or data['Nome_Card']
        numero_limpo = clean_for_key(numero_raw)
        chave = f"{uasg}_{numero_limpo}" if uasg != 'N/A' else f"N/A_{numero_limpo}"
        
        if not data['Numero_Pregao']:
            parciais += 1
            logger.debug(f"Card parcial (sem Numero): {data['Nome_Card'][:30]}...")
        
        if chave != 'N/A_' and chave != 'N/A_N/A' and chave not in existing_chaves:
            novos_registros.append(data)
        elif chave != 'N/A_' and chave != 'N/A_N/A':
            duplicatas_no_excel.append(chave)
    
    if novos_registros:
        # Mapear para headers reais (adiciona colunas vazias se necessário)
        df_new = pd.DataFrame(novos_registros)
        for col in real_headers:
            if col not in df_new.columns:
                df_new[col] = ''  # Coluna vazia para headers extras
        df_updated = pd.concat([df_existing, df_new[real_headers]], ignore_index=True)  # Ordena colunas
        df_updated.to_excel(EXCEL_FILE, index=False)
        logger.info(f"Adicionados {len(novos_registros)} novos registros ao {EXCEL_FILE} ( {parciais} parciais sem Numero).")
    else:
        logger.info("Nenhum novo registro adicionado (todos duplicados ou vazios).")
    
    # Atualizar duplicatas
    duplicatas_encontradas.extend(duplicatas_no_excel)
    return len(novos_registros), parciais

# Função principal
def main():
    start_time = time.time()
    logger.info("Iniciando extração de cards do Trello (com lógica de duplicatas corrigida)...")
    duplicatas_encontradas = []
    
    # Teste de autenticação e acesso ao board
    logger.info("Testando autenticação e acesso ao board...")
    test_url = f"https://api.trello.com/1/boards/{BOARD_ID}"
    test_params = {'key': API_KEY, 'token': TOKEN, 'fields': 'name,id'}
    test_response = requests.get(test_url, params=test_params, timeout=30)
    logger.info(f"Teste API: Status {test_response.status_code}")
    if test_response.status_code != 200:
        logger.error(f"Falha no teste da API: {test_response.text[:300]}")
        logger.error("Verifique API_KEY, TOKEN e BOARD_ID. Regenere token em: https://trello.com/app-key")
        raise ValueError("Falha na autenticação/acesso ao board.")
    board_info = test_response.json()
    logger.info(f"Board acessado com sucesso: {board_info.get('name', 'Desconhecido')} (ID: {board_info.get('id')})")
    
    # Obter todos os cards com paginação
    try:
        cards = get_all_cards_from_board(BOARD_ID)
    except Exception as e:
        logger.error(f"Erro ao obter cards: {e}")
        return
    
    if not cards:
        logger.warning("Nenhum card encontrado no board. Verifique se o board tem cards ou permissões.")
        return
    
    logger.info(f"Total de cards obtidos: {len(cards)}")
    
    # Estatísticas por lista (Status)
    status_counter = Counter(card.get('idList', 'Desconhecido') for card in cards)
    logger.info("Distribuição por lista (Status):")
    for status_id, count in status_counter.items():
        logger.info(f"  - {status_id}: {count} cards")
    
    new_data_list = []
    chaves_processadas = set()  # Evitar duplicatas internas no Trello
    
    for index, card in enumerate(cards):
        try:
            card_data, chave_duplicata = process_card(card, index, len(cards))
            if chave_duplicata and chave_duplicata not in chaves_processadas:
                new_data_list.append(card_data)
                chaves_processadas.add(chave_duplicata)
            elif chave_duplicata:
                duplicatas_encontradas.append(f"Trello interno: {chave_duplicata}")
                logger.warning(f"Duplicata interna no Trello: {chave_duplicata}")
        except Exception as e:
            logger.error(f"Erro ao processar card {card.get('id', 'desconhecido')}: {e}")
            continue  # Continua com próximos cards
    
    # Atualizar Excel
    novos_adicionados, parciais = update_excel(new_data_list, duplicatas_encontradas)
    
    # Relatório final
    end_time = time.time()
    print("\n" + "="*60)
    print("RELATÓRIO FINAL DA EXTRAÇÃO (DUPLICATAS CORRIGIDAS)")
    print("="*60)

# Ponto de entrada para execução do script
if __name__ == "__main__":
    main()
