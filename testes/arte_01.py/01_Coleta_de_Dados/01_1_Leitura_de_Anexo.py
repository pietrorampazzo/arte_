# Estratégia: Lê anexos de cards do Trello, focando em arquivos .txt ou .pdf.
# Funcionamento: Usa a API do Trello para acessar anexos e extrair conteúdo.
# Integração: Fornece dados brutos para pesquisa no ComprasNet.

from utils.trello_client import TrelloClient

def read_anexo(card_id):
    trello = TrelloClient()
    card = trello.get_card(card_id)
    attachments = card.list_attachments()
    for attachment in attachments:
        if attachment['name'].endswith(('.txt', '.pdf')):
            content = trello.get_attachment_content(attachment['id'])
            return content
    return None