
import requests
from bs4 import BeautifulSoup

def analisar_pagina_comprasnet():
    """
    Esta função busca a página inicial do compras.net e extrai o seu título.
    """
    url = "https://www.gov.br/compras/pt-br"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Lança uma exceção para respostas com erro (4xx ou 5xx)

        soup = BeautifulSoup(response.content, 'html.parser')
        
        titulo = soup.title.string
        print(f"Título da página: {titulo}")

    except requests.exceptions.RequestException as e:
        print(f"Erro ao acessar a página: {e}")

if __name__ == "__main__":
    analisar_pagina_comprasnet()
