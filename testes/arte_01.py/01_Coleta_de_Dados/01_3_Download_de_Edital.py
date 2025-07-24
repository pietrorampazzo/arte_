# Estratégia: Baixa arquivos de editais a partir de URLs.
# Funcionamento: Usa requests para baixar PDFs e salvá-los localmente.
# Integração: Prepara arquivos para processamento na fase 2.

import requests
import os

def download_edital(url, output_dir='data/downloads'):
    os.makedirs(output_dir, exist_ok=True)
    response = requests.get(url)
    if response.status_code == 200:
        filename = os.path.join(output_dir, url.split('/')[-1])
        with open(filename, 'wb') as f:
            f.write(response.content)
        return filename
    return None