import requests
import re
from prettytable import PrettyTable  # pip install prettytable

# 🔐 Configurações da API Trello
API_KEY = "683cba47b43c3a1cfb10cf809fecb685"
TOKEN = "ATTA89e63b1ce30ca079cef748f3a99cda25de9a37f3ba98c35680870835d6f2cae034C088A8"
BOARD_ID = "68569b7191cc868682152923"  # ID do seu board

LISTAS_DE_INTERESSE = ["PREPARANDO", "PREGAO"]

def get_lists(board_id):
    """Busca todas as listas de um board"""
    url = f"https://api.trello.com/1/boards/{board_id}/lists"
    params = {"key": API_KEY, "token": TOKEN, "cards": "none"}
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    return resp.json()

def get_cards(list_id):
    """Busca todos os cards de uma lista"""
    url = f"https://api.trello.com/1/lists/{list_id}/cards"
    params = {"key": API_KEY, "token": TOKEN}
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    return resp.json()

def normalizar_numero_edital(numero: str) -> str:
    """Remove a barra '/' do número de edital/pregão"""
    if numero:
        return numero.replace("/", "")
    return numero

def extrair_dados_card(card_name: str):
    """Extrai UASG e número do edital/pregão do nome do card"""
    # UASG (6 dígitos)
    match_uasg = re.search(r"Uasg:\s*(\d+)", card_name, re.IGNORECASE)
    uasg = match_uasg.group(1) if match_uasg else None

    # Número do edital/pregão (com ou sem '/')
    match_num = re.search(r"(\d{4,}/?\d{4})", card_name)
    numero = match_num.group(1) if match_num else None
    numero_normalizado = normalizar_numero_edital(numero)

    return uasg, numero, numero_normalizado

def update_card_name(card_id: str, new_name: str):
    """Atualiza o nome de um card no Trello"""
    url = f"https://api.trello.com/1/cards/{card_id}"
    params = {"key": API_KEY, "token": TOKEN, "name": new_name}
    resp = requests.put(url, params=params)
    resp.raise_for_status()
    return resp.json()

def renomear_cards(board_id):
    listas = get_lists(board_id)

    # Criar tabela para saída
    tabela = PrettyTable()
    tabela.field_names = ["Lista", "Nome Antigo", "Nome Novo", "UASG", "Nº Edital/Pregão", "Normalizado"]

    for lista in listas:
        if lista["name"].upper() in LISTAS_DE_INTERESSE:
            cards = get_cards(lista["id"])
            for card in cards:
                uasg, numero, numero_norm = extrair_dados_card(card["name"])
                if numero and '/' in numero:
                    # Substituir apenas o número no nome do card
                    new_name = re.sub(r"(\d{4,}/?\d{4})", numero_norm, card["name"])
                    update_card_name(card["id"], new_name)
                    tabela.add_row([lista["name"], card["name"], new_name, uasg, numero, numero_norm])
                else:
                    tabela.add_row([lista["name"], card["name"], card["name"], uasg, numero, numero_norm])

    print(tabela)

if __name__ == "__main__":
    renomear_cards(BOARD_ID)