import os
import re
from pathlib import Path
import shutil
from io import StringIO, BytesIO
import base64
import time
import pandas as pd
import fitz  # PyMuPDF
import zipfile
import rarfile
from pdf2image import convert_from_path
import pytesseract
import requests
import json
from dotenv import load_dotenv
from datetime import datetime
from PIL import Image

# =====================================================================================
# 1. CONFIGURAÇÕES E CONSTANTES
# =====================================================================================

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# --- Configurações de Caminhos ---
PROJECT_ROOT = Path(r"c:\\Users\\pietr\\OneDrive\\.vscode\\arte_")
BASE_DIR = PROJECT_ROOT / "DOWNLOADS"
PASTA_EDITAIS = BASE_DIR / "EDITAIS"
SUMMARY_EXCEL_PATH = BASE_DIR / "summary.xlsx"
FINAL_MASTER_PATH = BASE_DIR / "master.xlsx"

# --- Configurações de Ferramentas Externas ---
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
POPLER_PATH = SCRIPTS_DIR / "Release-25.07.0-0" / "poppler-25.07.0" / "Library" / "bin"
TESSERACT_CMD = SCRIPTS_DIR / "Tesseract-OCR" / "tesseract.exe"
pytesseract.pytesseract.tesseract_cmd = str(TESSERACT_CMD)
UNRAR_CMD = SCRIPTS_DIR / "unrar" / "UnRAR.exe"
rarfile.UNRAR_TOOL = str(UNRAR_CMD)

# --- Configuração da API Generativa com Fallback ---
LLM_MODELS_FALLBACK = [
    'gryphe/mythomist-7b-lightning:free',     # Modelo multimodal
    'google/gemini-pro-vision:free',          # Modelo multimodal
    'openai/gpt-4-vision-preview',            # Modelo multimodal
    'anthropic/claude-3-opus',                # Modelo multimodal
    'anthropic/claude-3-sonnet',              # Modelo multimodal
    'deepseek/deepseek-vision-base-7b:free',  # Modelo multimodal
    'stabilityai/stable-vision-xl:free',      # Modelo multimodal
]

# --- Configuração da API Generativa ---
API_KEY = os.getenv("OPENROUTER_API_KEY")
if not API_KEY:
    print("ERRO: A variável de ambiente OPENROUTER_API_KEY não foi definida.")

# --- Configurações do Processamento ---
MAX_RETRIES = 3
DELAY_BETWEEN_RETRIES = 5  # segundos
MAX_TOKENS = 4096
TIMEOUT = 300  # segundos

# --- Configurações de Filtro ---
PALAVRAS_CHAVE = [
    # ------------------ Categorias principais ------------------
    r'Instrumento Musical',r'Instrumento Musical - Sopro',r'Instrumento Musical - Corda',r'Instrumento Musical - Percussão',
    r'Peças e acessórios instrumento musical',
    r'Peças E Acessórios Instrumento Musical',

    # ------------------ Sopros ------------------
    r'saxofone',r'trompete',r'tuba',r'clarinete',r'trompa', 
    r'óleo lubrificante', r'óleos para válvulas', r'Corneta Longa',

    # ------------------ Cordas ------------------
    r'violão',r'Guitarra',r'Violino',
    r'Viola',r'Cavaquinho',r'Bandolim',
    r'Ukulele',

    # ------------------ Percussão ------------------
    r'tarol', r'Bombo', r'CAIXA TENOR', r'Caixa tenor', r'Caixa de guerra',
    r'Bateria completa', r'Bateria eletrônica',
    r'Pandeiro', r'Pandeiro profissional',
    r'Atabaque', r'Congas', r'Timbau',
    r'Xilofone', r'Glockenspiel', r'Vibrafone',
    r'Tamborim', r'Reco-reco', r'Agogô', r'Chocalho',
    r'Prato de bateria', r'Prato de Bateria', r'TRIÂNGULO',
    r'Baqueta', r'Baquetas', r'PAD ESTUDO', r'QUADRITOM', 

    # ------------------ Teclas ------------------
    r'Piano',
    r'Suporte para teclado',

    # ------------------ Microfones e acessórios ------------------
    r'Microfone', r'palheta', r'PALHETA',
    r'Microfone direcional',
    r'Microfone Dinâmico',
    r'Microfone de Lapela',
    r'Suporte microfone',
    r'Base microfone',
    r'Medusa para microfone',
    r'Pré-amplificador microfone',
    r'Fone Ouvido', r'Gooseneck',

    # ------------------ Áudio (caixas, amplificação, interfaces) ------------------
    r'Caixa Acústica', r'Caixa de Som',
    r'Subwoofer',
    r'Amplificador de áudio',
    r'Amplificador som',
    r'Amplificador fone ouvido',
    r'Interface de Áudio',
    r'Mesa áudio', r'Mesa de Som', 
    r'Equipamento Amplificador', r'Rack para Mesa',

    # ------------------ Pedestais e suportes ------------------
    r'Pedestal caixa acústica',
    r'Pedestal microfone',
    r'Estante - partitura',
    r'Suporte de videocassete',

    # ------------------ Projeção ------------------
    r'Tela projeção',
    r'Projetor Multimídia', r'PROJETOR MULTIMÍDIA', r'Projetor imagem',

    # ------------------ Efeitos ------------------
    r'drone', r'DRONE', r'Aeronave', r'Energia solar',
]

REGEX_FILTRO = re.compile('|'.join(PALAVRAS_CHAVE), re.IGNORECASE)

# --- Configurações de Exclusão ---
PALAVRAS_EXCLUIR = [
    r'notebook', r'Dosímetro Digital', r'Radiação',r'Raios X', r'Aparelho eletroestimulador', r'Armário', r'Aparelho ar',
    r'webcam', r'Porteiro Eletrônico', r'Alicate Amperímetro',r'multímetro', r'Gabinete Para Computador', 
    r'Microcomputador', r'Lâmpada projetor', r'Furadeira', r'Luminária', r'Parafusadeira', r'Brinquedo em geral', 
    r'Aparelho Telefônico', r'Decibelímetro', r'Termohigrômetro', r'Trenador', r'Balança Eletrônica', r'BATERIA DE LÍTIO', 
    r'Câmera', r'smart TV', r'bombona', r'LAMPADA', r'LUMINARIA', r'ortopedia', r'Calculadora eletrônica', r'Luz Emergência', r'Desfibrilador',
    r'Colorímetro', r'Peagâmetro', r'Rugosimetro', r'Nível De Precisão', r'Memória Flash', r'Fechadura Biometrica', r'Bateria Telefone',
    r'Testador Bateria', r'Analisador cabeamento', r'Termômetro', r'Sensor infravermelho', r'Relógio Material', r'Armário de aço',
    r'Bateria recarregável', r'Serra portátil', r'Ultrassom', r'Bateria não recarregável', r'Arduino', r'ALICATE TERRÔMETRO'
    r'Lâmina laboratório', r'Medidor E Balanceador', r'Trena eletrônica', r'Acumulador Tensão', r'Sirene Multiaplicação', r'Clinômetro',
    r'COLETOR DE ASSINATURA', r'Localizador cabo', r'Laserpoint', r'Bateria Filmadora', 
]
REGEX_EXCLUIR = re.compile('|'.join(PALAVRAS_EXCLUIR), re.IGNORECASE)

# --- Configurações de Exceção ao Filtro ---
PALAVRAS_EXCECAO = [
    r'drone', r'DRONE', r'Aeronave',
]
REGEX_EXCECAO = re.compile('|'.join(PALAVRAS_EXCECAO), re.IGNORECASE)

# =====================================================================================
# 2. FUNÇÕES DE PROCESSAMENTO DE IMAGENS
# =====================================================================================

def pdf_to_base64_images(pdf_path: Path) -> list[str]:
    """
    Converte cada página de um PDF em uma imagem codificada em base64.
    """
    images_base64 = []
    print(f"    > Convertendo PDF para imagens: {pdf_path.name}")
    try:
        images = convert_from_path(pdf_path, dpi=200, poppler_path=POPLER_PATH)
        for i, img in enumerate(images):
            print(f"      - Processando página {i+1}/{len(images)}...")
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            images_base64.append(img_str)
        print("      - ✅ PDF convertido para imagens com sucesso.")
        return images_base64
    except Exception as e:
        print(f"      - ❌ ERRO: Falha ao converter PDF {pdf_path.name} para imagens: {e}")
        return []

def resize_image_if_needed(image_base64: str, max_size_mb: float = 20.0) -> str:
    """
    Redimensiona a imagem se ela exceder o tamanho máximo especificado.
    """
    # Decodifica a string base64
    image_data = base64.b64decode(image_base64)
    image_size_mb = len(image_data) / (1024 * 1024)
    
    if image_size_mb <= max_size_mb:
        return image_base64
    
    # Carrega a imagem
    image = Image.open(BytesIO(image_data))
    
    # Calcula o fator de redução necessário
    reduction_factor = (max_size_mb / image_size_mb) ** 0.5
    new_size = tuple(int(dim * reduction_factor) for dim in image.size)
    
    # Redimensiona a imagem
    resized_image = image.resize(new_size, Image.Resampling.LANCZOS)
    
    # Converte de volta para base64
    buffered = BytesIO()
    resized_image.save(buffered, format=image.format or "PNG", quality=85)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

# =====================================================================================
# 3. FUNÇÕES DE INTERAÇÃO COM A API
# =====================================================================================

def gerar_conteudo_com_fallback(prompt: str, image_base64: str = None) -> str:
    """
    Tenta gerar conteúdo usando diferentes modelos de linguagem com suporte a imagens.
    """
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    for nome_modelo in LLM_MODELS_FALLBACK:
        print(f"Tentando modelo: {nome_modelo}")
        
        messages = [{"role": "user", "content": []}]
        
        # Adiciona o texto do prompt
        messages[0]["content"].append({
            "type": "text",
            "text": prompt
        })
        
        # Se houver imagem, adiciona ao conteúdo
        if image_base64:
            messages[0]["content"].append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{image_base64}",
                    "detail": "high"
                }
            })

        payload = {
            "model": nome_modelo,
            "messages": messages,
            "max_tokens": MAX_TOKENS,
            "temperature": 0.1,
            "top_p": 0.9
        }

        for tentativa in range(MAX_RETRIES):
            try:
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=TIMEOUT
                )

                if response.status_code == 429:  # Rate limit
                    if tentativa < MAX_RETRIES - 1:
                        time.sleep(DELAY_BETWEEN_RETRIES)
                        continue
                    print(f"   - Rate limit excedido para o modelo '{nome_modelo}'. Tentando o próximo.")
                    break

                response.raise_for_status()
                response_json = response.json()
                
                content = response_json.get('choices', [{}])[0].get('message', {}).get('content')
                if not content:
                    print(f"API retornou resposta vazia para o modelo {nome_modelo}.")
                    continue

                print(f"   - Sucesso com o modelo '{nome_modelo}'.")
                return content

            except requests.exceptions.RequestException as e:
                print(f"Erro de requisição com o modelo '{nome_modelo}': {e}")
                if tentativa < MAX_RETRIES - 1:
                    time.sleep(DELAY_BETWEEN_RETRIES)
                    continue
                break
            except Exception as e:
                print(f"Erro inesperado e crítico com o modelo '{nome_modelo}': {e}")
                break

    print("FALHA TOTAL: Todos os modelos multimodais na lista de fallback falharam.")
    return None

# =====================================================================================
# 4. FUNÇÕES DE PROCESSAMENTO DE DOCUMENTOS
# =====================================================================================

def processar_pdf_direto(pdf_path: Path) -> list[dict]:
    """
    Processa um PDF diretamente usando modelos multimodais, página por página.
    """
    print(f"Processando PDF: {pdf_path.name}")
    itens_encontrados = []
    
    # Converte PDF para lista de imagens em base64
    imagens_base64 = pdf_to_base64_images(pdf_path)
    if not imagens_base64:
        print("Falha ao converter PDF para imagens.")
        return []
    
    # Processa cada página do PDF
    for num_pagina, imagem_base64 in enumerate(imagens_base64, 1):
        print(f"Processando página {num_pagina}/{len(imagens_base64)}...")
        
        # Redimensiona a imagem se necessário
        imagem_base64 = resize_image_if_needed(imagem_base64)
        
        # Gera o prompt para extração
        prompt = f"""
        Você é um assistente especializado em extrair informações de editais de licitação.
        
        Analise a imagem da página de um edital de licitação e extraia TODOS os itens que estão sendo licitados.
        Para cada item encontrado, extraia:
        
        1. Número do item
        2. Descrição completa e detalhada
        3. Quantidade
        4. Valor unitário
        5. Unidade de fornecimento
        6. Local de entrega (se disponível)

        Retorne no seguinte formato usando '<--|-->' como separador:
        Nº<--|-->DESCRICAO<--|-->QTDE<--|-->VALOR_UNIT<--|-->UNID_FORN<--|-->LOCAL_ENTREGA

        Exemplo:
        1<--|-->Violão Clássico Acústico<--|-->10<--|-->1500,00<--|-->Unidade<--|-->Campus São Paulo
        
        IMPORTANTE:
        - Retorne APENAS os dados no formato especificado
        - NÃO inclua textos explicativos ou informações adicionais
        - Se alguma informação não estiver disponível, deixe o campo vazio mas mantenha os separadores
        - Inclua TODOS os itens visíveis na imagem
        - Certifique-se de capturar a descrição detalhada completa de cada item
        """
        
        # Obtém o conteúdo da página usando modelo multimodal
        conteudo = gerar_conteudo_com_fallback(prompt, imagem_base64)
        if not conteudo:
            print(f"Falha ao processar página {num_pagina}.")
            continue
        
        # Processa os itens encontrados
        for linha in conteudo.strip().split('\n'):
            if not linha or '<--|-->' not in linha:
                continue
                
            campos = linha.split('<--|-->')
            if len(campos) != 6:
                continue
                
            num, desc, qtd, val_unit, unid, local = campos
            
            # Verifica se o item é relevante usando os filtros existentes
            if REGEX_FILTRO.search(desc) and not REGEX_EXCLUIR.search(desc):
                item = {
                    "Nº": num,
                    "DESCRICAO": desc,
                    "QTDE": qtd,
                    "VALOR_UNIT": val_unit,
                    "UNID_FORN": unid,
                    "LOCAL_ENTREGA": local
                }
                itens_encontrados.append(item)
    
    print(f"Total de itens relevantes encontrados: {len(itens_encontrados)}")
    return itens_encontrados

def processar_pasta_edital(pasta_path: Path) -> list[dict]:
    """
    Processa uma pasta de edital completa usando extração direta dos PDFs.
    """
    print(f"\nProcessando pasta: {pasta_path.name}")
    itens_encontrados = []

    # Procura por PDFs na pasta e subpastas
    for pdf_path in pasta_path.rglob('*.pdf'):
        if "relacao" in pdf_path.name.lower() or "itens" in pdf_path.name.lower():
            itens_pdf = processar_pdf_direto(pdf_path)
            if itens_pdf:
                itens_encontrados.extend(itens_pdf)

    return itens_encontrados

def main():
    """
    Função principal que coordena o processamento direto dos editais.
    """
    print("Iniciando processamento direto dos editais...")
    
    # Processa cada pasta na pasta de editais
    for pasta_edital in PASTA_EDITAIS.iterdir():
        if not pasta_edital.is_dir():
            continue
            
        try:
            # Processa a pasta do edital
            itens = processar_pasta_edital(pasta_edital)
            
            if not itens:
                print(f"Nenhum item relevante encontrado em: {pasta_edital.name}")
                continue
            
            # Cria DataFrame com os itens encontrados
            df = pd.DataFrame(itens)
            
            # Salva os resultados em um arquivo Excel
            output_file = pasta_edital / f"itens_extraidos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            df.to_excel(output_file, index=False)
            print(f"Resultados salvos em: {output_file}")
            
        except Exception as e:
            print(f"Erro ao processar pasta {pasta_edital.name}: {e}")

if __name__ == "__main__":
    main()