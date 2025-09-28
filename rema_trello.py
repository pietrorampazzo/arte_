import os
import re
import shutil
import requests
from typing import Optional, Tuple, Set, List, Dict

# -------------------------------------------------------------
# CONFIGURAÇÕES DA API E CAMINHOS (Valores do seu trello_controle.py)
# -------------------------------------------------------------

API_KEY = "683cba47b43c3a1cfb10cf809fecb685"
TOKEN = "ATTA89e63b1ce30ca079cef748f3a99cda25de9a37f3ba98c35680870835d6f2cae034C088A8"
BOARD_ID = "68569b7191cc868682152923"

# Listas do Trello para MANTER as pastas ativas no SOURCE_DIR
LISTAS_A_MANTER = ["PREPARANDO", "PREGAO"]

# Caminhos no seu computador
SOURCE_DIR = r"C:\Users\pietr\OneDrive\.vscode\arte_\DOWNLOADS\EDITAIS"
ARCHIVE_DIR = r"C:\Users\pietr\OneDrive\.vscode\arte_\DOWNLOADS\ARQUIVO"

# -------------------------------------------------------------
# FUNÇÕES DA API TRELLO
# -------------------------------------------------------------

def get_lists(board_id: str) -> List[Dict]:
    url = f"https://api.trello.com/1/boards/{board_id}/lists"
    params = {"key": API_KEY, "token": TOKEN, "cards": "none"}
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    return resp.json()

def get_cards(list_id: str) -> List[Dict]:
    url = f"https://api.trello.com/1/lists/{list_id}/cards"
    params = {"key": API_KEY, "token": TOKEN}
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    return resp.json()

# -------------------------------------------------------------
# FUNÇÃO DE EXTRAÇÃO (CORRIGIDA PARA CONCATENAMENTO E ROBUSTEZ)
# -------------------------------------------------------------

def extrair_dados_card(nome_card: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extrai o UASG (XXX) e o Número do Edital/Pregão (YYY) do nome do card,
    lidando com a concatenação do ano.
    Retorna (UASG, NUMERO_NORMALIZADO).
    """
    # 1. Extração do UASG (XXX):
    match_uasg = re.search(r"Uasg:\s*(\d{4,})", nome_card, re.IGNORECASE)
    uasg = match_uasg.group(1) if match_uasg else None

    # 2. Extração do Número do Edital/Pregão (YYY): 
    # Procura por números de 3+ dígitos que apareçam após palavras-chave comuns de pregão/edital.
    # Esta regex ajuda a isolar o número correto e ignorar o UASG se ele for encontrado primeiro.
    match_num = re.search(r"(?:Dispensa|Pregão|Edital).*?\s(\d{3,}(?:/\d{4})?)", nome_card, re.IGNORECASE)
    numero_edital = match_num.group(1) if match_num else None
    
    numero_normalizado = None
    if numero_edital:
        # 3a. Normalização básica: Remove o ano se houver barra (e.g., 90016/2025 -> 90016)
        numero_normalizado = numero_edital.split('/')[0]
        
        # 3b. CORREÇÃO PARA CONCATENAÇÃO: Remove os últimos 4 dígitos se parecer um ano
        # Verifica se o número resultante tem mais de 4 dígitos E termina com anos recentes
        if (len(numero_normalizado) > 4 and 
            numero_normalizado.endswith(('2023', '2024', '2025', '2026', '2027'))):
            
            # Remove os 4 últimos dígitos (o ano)
            numero_normalizado = numero_normalizado[:-4]
            print(f"   [INFO] Corrigido número concatenado: {numero_edital} -> {numero_normalizado}")
        
    # Retorna apenas se ambos os campos forem encontrados
    if not uasg or not numero_normalizado:
        return None, None

    return uasg, numero_normalizado

# -------------------------------------------------------------
# LÓGICA PRINCIPAL DE ARQUIVAMENTO
# -------------------------------------------------------------

def get_active_folder_base_names() -> Set[str]:
    """Busca no Trello e retorna as chaves (U_xxx_E_yyy) que DEVEM ser mantidas."""
    active_folder_names: Set[str] = set()
    
    try:
        print("1. Conectando-se ao Trello e buscando listas ativas...")
        all_lists = get_lists(BOARD_ID)
        
        for lista in all_lists:
            list_name = lista.get('name', '').strip().upper()
            
            if list_name in LISTAS_A_MANTER:
                print(f"-> Buscando cards na lista ATIVA: {list_name}")
                cards = get_cards(lista['id'])
                
                for card in cards:
                    card_name = card.get('name', '')
                    uasg, numero_norm = extrair_dados_card(card_name)
                    
                    if uasg and numero_norm:
                        # CRIAÇÃO DA CHAVE DE COMPARAÇÃO
                        folder_base_name = f"U_{uasg}_E_{numero_norm}"
                        active_folder_names.add(folder_base_name)
                        print(f"   [ATIVO] Chave gerada: {folder_base_name} (Card: {card_name[:40]}...)")
                    else:
                        # Imprime cards que falharam a extração para facilitar o debug
                        if card_name:
                             print(f"   [FALHA] Card '{card_name[:40]}...' não gerou chave válida.")
                        
    except requests.exceptions.RequestException as e:
        print(f"\nERRO CRÍTICO: Falha ao se comunicar com o Trello. O processo de arquivamento foi abortado.")
        print(f"Detalhe do erro: {e}")
        return set()

    print(f"\n{len(active_folder_names)} chaves de pastas identificadas como ATIVAS (para MANTER).")
    return active_folder_names

def mover_pastas_inativas():
    """Executa a lógica de mover as pastas locais que NÃO estão ativas no Trello."""
    
    active_base_names = get_active_folder_base_names()
    
    if not active_base_names:
        print("\nPROCESSO ABORTADO: Nenhuma chave U_xxx_E_yyy foi extraída com sucesso.")
        return

    # 2. Obter a lista de pastas no diretório de origem
    try:
        all_local_folders = [
            d for d in os.listdir(SOURCE_DIR) 
            if os.path.isdir(os.path.join(SOURCE_DIR, d)) and d.startswith('U_')
        ]
    except FileNotFoundError:
        print(f"\nERRO: Diretório de origem '{SOURCE_DIR}' não encontrado.")
        return

    print(f"Total de pastas locais encontradas em EDITAIS: {len(all_local_folders)}")
    
    folders_to_move: List[str] = []

    # 3. Identificar pastas para mover (usando a lógica startswith)
    for local_folder in all_local_folders:
        should_keep = False
        
        # Se a pasta local começar com qualquer chave ativa, ela deve ser MANTIDA.
        for active_base_name in active_base_names:
            if local_folder.startswith(active_base_name):
                should_keep = True
                # print(f"[MANTER] Pasta '{local_folder}' corresponde à chave: {active_base_name}")
                break
        
        # Se NÃO deve ser mantida, adiciona à lista de movimentação
        if not should_keep:
            folders_to_move.append(local_folder)

    if not folders_to_move:
        print("\nNenhuma pasta inativa encontrada para arquivamento. O diretório EDITAIS está limpo.")
        return

    print(f"\n{len(folders_to_move)} pastas identificadas para ARQUIVAMENTO...")
    
    # 4. Criar o diretório de arquivamento e mover as pastas
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    moved_count = 0
    for folder_name in folders_to_move:
        source_path = os.path.join(SOURCE_DIR, folder_name)
        destination_path = os.path.join(ARCHIVE_DIR, folder_name)
        
        try:
            shutil.move(source_path, destination_path)
            moved_count += 1
        except Exception as e:
            print(f"ERRO ao mover a pasta '{folder_name}': {e}")
            
    print(f"\n--- Processo Concluído ---")
    print(f"{moved_count} pastas movidas para ARQUIVO.")
    print(f"{len(all_local_folders) - moved_count} pastas mantidas em EDITAIS.")

if __name__ == "__main__":
    mover_pastas_inativas()