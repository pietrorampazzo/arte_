import os
import re
import shutil
import requests
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from typing import Optional, Tuple, Set, List, Dict

# -------------------------------------------------------------
# CONFIGURAÇÕES GERAIS
# -------------------------------------------------------------

# Chaves da API Trello
API_KEY = "683cba47b43c3a1cfb10cf809fecb685"
TOKEN = "ATTA89e63b1ce30ca079cef748f3a99cda25de9a37f3ba98c35680870835d6f2cae034C088A8"
BOARD_ID = "68569b7191cc868682152923"

# --- Configurações para "rema_trello" (arquivamento de pastas) ---

# Listas do Trello para MANTER as pastas ativas
LISTAS_A_MANTER = ["PREPARANDO", "PREGAO"]

# Caminhos de diretórios
SOURCE_DIR = r"C:\Users\pietr\OneDrive\.vscode\arte_\DOWNLOADS\EDITAIS"
ARCHIVE_DIR = r"C:\Users\pietr\OneDrive\.vscode\arte_\DOWNLOADS\ARQUIVO"

# --- Configurações para "new_card_trello" (atualização de cards) ---

# IDs das listas "PREPARANDO" para buscar cards a serem atualizados
LISTAS_PREPARANDO_PARA_ATUALIZAR = [
    '6650f3369bb9bacb525d1dc8',  # Board: Novo Pietro
]

# Armazena os cards já processados para evitar duplicidade
processed_cards = set()


# -------------------------------------------------------------
# FUNÇÕES DA API TRELLO (GENÉRICAS)
# -------------------------------------------------------------

def get_lists(board_id: str) -> List[Dict]:
    """Busca todas as listas de um quadro."""
    url = f"https://api.trello.com/1/boards/{board_id}/lists"
    params = {"key": API_KEY, "token": TOKEN, "cards": "none"}
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    return resp.json()

def get_cards_in_list(list_id: str) -> List[Dict]:
    """Busca todos os cards de uma lista específica."""
    url = f"https://api.trello.com/1/lists/{list_id}/cards"
    params = {'key': API_KEY, 'token': TOKEN}
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def get_attachments(card_id: str) -> List[Dict]:
    """Busca todos os anexos de um card."""
    url = f"https://api.trello.com/1/cards/{card_id}/attachments"
    params = {'key': API_KEY, 'token': TOKEN}
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def update_card_due_date(card_id: str, due_date_iso: str) -> bool:
    """Atualiza a data de entrega de um card."""
    url = f"https://api.trello.com/1/cards/{card_id}"
    params = {'key': API_KEY, 'token': TOKEN, 'due': due_date_iso}
    response = requests.put(url, params=params)
    return response.status_code == 200

def update_card_name(card_id: str, new_name: str) -> bool:
    """Atualiza o nome de um card."""
    url = f"https://api.trello.com/1/cards/{card_id}"
    params = {'key': API_KEY, 'token': TOKEN, 'name': new_name}
    response = requests.put(url, params=params)
    return response.status_code == 200


# -------------------------------------------------------------
# SEÇÃO 1: LÓGICA DE ATUALIZAÇÃO DE CARDS (new_card_trello.py)
# -------------------------------------------------------------

def add_auth_to_url(url: str) -> str:
    """Adiciona autenticação da API Trello a uma URL de anexo."""
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    query['key'] = [API_KEY]
    query['token'] = [TOKEN]
    new_query = urlencode(query, doseq=True)
    return urlunparse(parsed._replace(query=new_query))

def extract_data_from_txt(attachment_id: str, card_id: str) -> Optional[Dict]:
    """Baixa e extrai dados estruturados de um anexo .txt."""
    url = f"https://api.trello.com/1/cards/{card_id}/attachments/{attachment_id}"
    params = {'key': API_KEY, 'token': TOKEN}
    try:
        response = requests.get(url, params=params)
        attachment_info = response.json()
        download_url = attachment_info.get('url')

        if not download_url:
            print("❌ URL de download não encontrada no anexo.")
            return None

        # Tenta baixar o conteúdo do anexo
        headers = {'Authorization': f'OAuth oauth_consumer_key="{API_KEY}", oauth_token="{TOKEN}"'} # Corrected quote escaping
        download_response = requests.get(download_url, headers=headers)
        download_response.raise_for_status()
        
        content = download_response.text.strip()
        lines = content.splitlines()
        return extract_structured_data(lines)

    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao baixar anexo: {e}")
        return None

def extract_structured_data(lines: List[str]) -> Dict:
    """Extrai informações de um conjunto de linhas de texto."""
    data = {}
    if len(lines) >= 4:
        data['new_card_name'] = f"{lines[1]}\n{lines[2]}\n{lines[3]}"
    
    for line in lines:
        if 'UASG' in line:
            data['uasg'] = re.search(r'(\d{6})', line).group(1) if re.search(r'(\d{6})', line) else None
        if 'Pregão' in line or 'Dispensa' in line:
            data['numero_pregao'] = re.search(r'(\d+/\d{{4}})', line).group(1) if re.search(r'(\d+/\d{{4}})', line) else None
        if 'http' in line and 'compras' in line:
            data['link_compras_gov'] = line.strip()
        
        dt_match = re.search(r'(\d{2}/\d{2}/\d{4})\s+às\s+(\d{2}:\d{2})', line)
        if dt_match:
            try:
                dt_obj = datetime.strptime(f"{dt_match.group(1)} {dt_match.group(2)}", "%d/%m/%Y %H:%M")
                data['data_do_pregao'] = dt_obj.isoformat()
            except ValueError:
                pass
    return data

def process_and_update_cards():
    """Função principal para a lógica de atualização de cards."""
    print("🚀 Iniciando processamento de atualização de cards...")
    all_cards = []
    for list_id in LISTAS_PREPARANDO_PARA_ATUALIZAR:
        try:
            cards = get_cards_in_list(list_id)
            print(f"📋 {len(cards)} cards encontrados na lista {list_id}")
            all_cards.extend(cards)
        except Exception as e:
            print(f"❌ Erro ao acessar lista {list_id}: {e}")

    for card in all_cards:
        if card['id'] in processed_cards:
            continue

        attachments = get_attachments(card['id'])
        txt_attachment = next((a for a in attachments if a['name'].endswith('.txt')), None)

        if txt_attachment:
            card_data = extract_data_from_txt(txt_attachment['id'], card['id'])
            if card_data and card_data.get('new_card_name'):
                if card_data.get('data_do_pregao'):
                    if update_card_due_date(card['id'], card_data['data_do_pregao']):
                        print(f"✅ [Card ID: {card['id']}] Data de entrega atualizada.")
                    else:
                        print(f"⚠️ [Card ID: {card['id']}] Falha ao atualizar data de entrega.")
                
                if update_card_name(card['id'], card_data['new_card_name']):
                    print(f"✅ [Card ID: {card['id']}] Nome do card atualizado.")
                else:
                    print(f"⚠️ [Card ID: {card['id']}] Falha ao atualizar nome do card.")
                
                processed_cards.add(card['id'])

# -------------------------------------------------------------
# SEÇÃO 2: LÓGICA DE ARQUIVAMENTO DE PASTAS (rema_trello.py)
# -------------------------------------------------------------

def extrair_dados_card_para_arquivamento(nome_card: str) -> Tuple[Optional[str], Optional[str]]:
    """Extrai UASG e Número do Edital do nome do card para a lógica de arquivamento."""
    match_uasg = re.search(r"Uasg:\s*(\d{{4,}} திறன்", nome_card, re.IGNORECASE)
    uasg = match_uasg.group(1) if match_uasg else None

    match_num = re.search(r"(?:Dispensa|Pregão|Edital).*?\s(\d{{3,}}(?:/\d{{4}})?)", nome_card, re.IGNORECASE)
    numero_edital = match_num.group(1) if match_num else None
    
    numero_normalizado = None
    if numero_edital:
        numero_normalizado = numero_edital.split('/')[0]
        if len(numero_normalizado) > 4 and numero_normalizado.endswith(('2023', '2024', '2025')):
            numero_normalizado = numero_normalizado[:-4]
            
    if not uasg or not numero_normalizado:
        return None, None
    return uasg, numero_normalizado

def get_active_folder_base_names() -> Set[str]:
    """Busca no Trello e retorna as chaves de pastas (U_xxx_E_yyy) que devem ser mantidas."""
    active_folder_names: Set[str] = set()
    try:
        print("1. Buscando listas e cards para determinar pastas ativas...")
        all_lists = get_lists(BOARD_ID)
        
        for lista in all_lists:
            if lista.get('name', '').strip().upper() in LISTAS_A_MANTER:
                print(f"-> Analisando lista ATIVA: {lista.get('name')}")
                cards = get_cards_in_list(lista['id'])
                for card in cards:
                    uasg, numero_norm = extrair_dados_card_para_arquivamento(card.get('name', ''))
                    if uasg and numero_norm:
                        folder_base_name = f"U_{{uasg}}_E_{{numero_norm}}"
                        active_folder_names.add(folder_base_name)
                        
    except requests.exceptions.RequestException as e:
        print(f"\nERRO CRÍTICO: Falha ao comunicar com o Trello. Abortando. Detalhe: {e}")
        return set()

    print(f"\n{len(active_folder_names)} chaves de pastas ativas identificadas.")
    return active_folder_names

def archive_inactive_folders():
    """Função principal para a lógica de arquivamento de pastas."""
    print("🚀 Iniciando processo de arquivamento de pastas inativas...")
    active_base_names = get_active_folder_base_names()
    
    if not active_base_names:
        print("\nPROCESSO ABORTADO: Nenhuma pasta ativa encontrada no Trello.")
        return

    try:
        local_folders = [d for d in os.listdir(SOURCE_DIR) if os.path.isdir(os.path.join(SOURCE_DIR, d)) and d.startswith('U_')]
    except FileNotFoundError:
        print(f"\nERRO: Diretório de origem '{SOURCE_DIR}' não encontrado.")
        return

    folders_to_move = []
    for folder in local_folders:
        if not any(folder.startswith(active_name) for active_name in active_base_names):
            folders_to_move.append(folder)

    if not folders_to_move:
        print("\nNenhuma pasta inativa para arquivar.")
        return

    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    moved_count = 0
    for folder_name in folders_to_move:
        try:
            shutil.move(os.path.join(SOURCE_DIR, folder_name), os.path.join(ARCHIVE_DIR, folder_name))
            moved_count += 1
            print(f"🗂️ Pasta '{folder_name}' arquivada.")
        except Exception as e:
            print(f"❌ ERRO ao mover '{folder_name}': {e}")
            
    print(f"\n--- Processo Concluído: {moved_count} pastas movidas para '{ARCHIVE_DIR}' ---")


# -------------------------------------------------------------
# MENU PRINCIPAL
# -------------------------------------------------------------

if __name__ == "__main__":
    while True:
        print("\n======================================")
        print("    GERENCIADOR TRELLO INTEGRADO    ")
        print("======================================")
        print("Escolha a operação a ser executada:")
        print("1. Atualizar Cards a partir de anexos (.txt)")
        print("2. Arquivar Pastas locais com base nos cards do Trello")
        print("3. Sair")
        
        choice = input("Digite o número da sua escolha: ")
        
        if choice == '1':
            process_and_update_cards()
        elif choice == '2':
            archive_inactive_folders()
        elif choice == '3':
            print("👋 Saindo do programa.")
            break
        else:
            print("❌ Escolha inválida. Por favor, tente novamente.")
