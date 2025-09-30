# Conteúdo do novo arquivo: arte_code/arte_edital_multimodal_v2.py

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
import google.generativeai as genai
import google.api_core.exceptions as google_exceptions

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

    "gemini-2.5-flash-lite", # Modelo multimodal Gemini
    "gemini-2.0-flash-lite", # Modelo multimodal Gemini
    "gemini-2.0-flash",      # Modelo multimodal Gemini
    "gemini-1.5-flash",      # Modelo multimodal Gemini
    "gemini-2.5-pro",        # Modelo multimodal Gemini
    "gemini-2.5-flash",      # Modelo multimodal Gemini
]

# --- Configuração da API Generativa ---
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    print("ERRO: A variável de ambiente GOOGLE_API_KEY não foi definida.")
else:
    genai.configure(api_key=API_KEY)

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
    r'Microfone', r'palheta', r'PALHETA'
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
    r'Caixa de Som',
    r'Caixa som',
    r'Subwoofer',
    r'Amplificador de áudio',
    r'Amplificador som',
    r'Amplificador fone ouvido',
    r'Interface de Áudio',
    r'Mesa áudio', r'Mesa de Som', 
    r'Equipamento Amplificador', r'Rack para Mesa'

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

# --- Configurações do Processamento ---
MAX_RETRIES = 3
DELAY_BETWEEN_RETRIES = 5  # segundos
MAX_TOKENS = 4096
TIMEOUT = 300  # segundos
REGEX_EXCLUIR = re.compile('|'.join(PALAVRAS_EXCLUIR), re.IGNORECASE)

# --- Configurações de Exceção ao Filtro ---
PALAVRAS_EXCECAO = [
    r'drone', r'DRONE', r'Aeronave',
]
REGEX_EXCECAO = re.compile('|'.join(PALAVRAS_EXCECAO), re.IGNORECASE)



# =====================================================================================
# 2. FUNÇÕES DE EXTRAÇÃO E PROCESSAMENTO
# =====================================================================================

def pdf_to_base64_images(pdf_path: Path) -> list[str]:
    """
    Converts each page of a PDF into a base64 encoded image.
    """
    images_base64 = []
    print(f"    > Converting PDF to images: {pdf_path.name}")
    try:
        images = convert_from_path(pdf_path, dpi=200, poppler_path=POPLER_PATH)
        for i, img in enumerate(images):
            print(f"      - Processing page {i+1}/{len(images)}...")
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            images_base64.append(img_str)
        print("      - ✅ PDF converted to images successfully.")
        return images_base64
    except Exception as e:
        print(f"      - ❌ ERROR: Failed to convert PDF {pdf_path.name} to images: {e}")
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

def extrair_itens_pdf_texto(text):
    """Extrai itens estruturados do texto de um PDF 'Relação de Itens'."""
    items = []
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r'\s+', ' ', text)
    item_pattern = re.compile(r'(\d+)\s*-\s*([^0-9]+?)(?=Descrição Detalhada:)', re.DOTALL | re.IGNORECASE)
    item_matches = list(item_pattern.finditer(text))

    for i, match in enumerate(item_matches):
        item_num = match.group(1).strip()
        item_nome = match.group(2).strip()
        start_pos = match.start()
        end_pos = item_matches[i + 1].start() if i + 1 < len(item_matches) else len(text)
        item_text = text[start_pos:end_pos]

        descricao_match = re.search(r'Descrição Detalhada:\s*(.*?)(?=Tratamento Diferenciado:|Aplicabilidade Decreto|$\s*)', item_text, re.DOTALL | re.IGNORECASE)
        descricao = descricao_match.group(1).strip() if descricao_match else ""
        item_completo = f"{item_nome} {re.sub(r'\s+', ' ', re.sub(r'[^\w\s:,.()/-]', '', descricao))}"

        quantidade_match = re.search(r'Quantidade Total:\s*(\d+)', item_text, re.IGNORECASE)
        quantidade = quantidade_match.group(1) if quantidade_match else ""

        valor_unitario_match = re.search(r'Valor Unitário[^:]*:\s*R?\$?\s*([\d.,]+)', item_text, re.IGNORECASE)
        valor_unitario = valor_unitario_match.group(1) if valor_unitario_match else ""

        valor_total_match = re.search(r'Valor Total[^:]*:\s*R?\$?\s*([\d.,]+)', item_text, re.IGNORECASE)
        valor_total = valor_total_match.group(1) if valor_total_match else ""

        unidade_match = re.search(r'Unidade de Fornecimento:\s*([^0-9\n]+?)(?=\s|$|\n)', item_text, re.IGNORECASE)
        unidade = unidade_match.group(1).strip() if unidade_match else ""

        local_match = re.search(r'Local de Entrega[^:]*:\s*([^(\n]+?)(?:\s*\(|$|\n)', item_text, re.IGNORECASE)
        local = local_match.group(1).strip() if local_match else ""

        items.append({
            "Nº": item_num, "DESCRICAO": item_completo, "QTDE": quantidade,
            "VALOR_UNIT": valor_unitario, "VALOR_TOTAL": valor_total,
            "UNID_FORN": unidade, "LOCAL_ENTREGA": local
        })
    return items

# REMOVIDA: A função processar_pdf_multimodal será integrada na lógica principal
# def processar_pdf_multimodal(pdf_path: Path) -> list[dict]:
#     """
#     Processa um PDF usando modelos multimodais, página por página.
#     """
#     print(f"Processando PDF: {pdf_path.name}")
#     itens_encontrados = []
    
#     # Converte PDF para lista de imagens em base64
#     imagens_base64 = pdf_to_base64_images(pdf_path)
#     if not imagens_base64:
#         print("Falha ao converter PDF para imagens.")
#         return []
    
#     # Processa cada página do PDF
#     for num_pagina, imagem_base64 in enumerate(imagens_base64, 1):
#         print(f"Processando página {num_pagina}/{len(imagens_base64)}...")
        
#         # Redimensiona a imagem se necessário
#         imagem_base64 = resize_image_if_needed(imagem_base64)
        
#         # Gera o prompt para extração
#         prompt = construir_prompt_extracao_multimodal()
        
#         # Obtém o conteúdo da página usando modelo multimodal
#         conteudo = gerar_conteudo_com_fallback(prompt, imagem_base64) # <-- AQUI
#         if not conteudo:
#             print(f"Falha ao processar página {num_pagina}.")
#             continue
        
#         # Processa os itens encontrados
#         for linha in conteudo.strip().split('\n'):
#             if not linha or '<--|-->' not in linha:
#                 continue
                
#             campos = linha.split('<--|-->')
#             if len(campos) != 6:
#                 continue
                
#             num, desc, qtd, val_unit, unid, local = campos
            
#             # Verifica se o item é relevante usando os filtros existentes
#             if REGEX_FILTRO.search(desc) and not REGEX_EXCLUIR.search(desc):
#                 item = {
#                     "Nº": num,
#                     "DESCRICAO": desc,
#                     "QTDE": qtd,
#                     "VALOR_UNIT": val_unit,
#                     "UNID_FORN": unid,
#                     "LOCAL_ENTREGA": local
#                 }
#                 itens_encontrados.append(item)
    
#     print(f"Total de itens relevantes encontrados: {len(itens_encontrados)}")
#     return itens_encontrados

def processar_pdf_relacao_itens(pdf_path):
    """Processa um PDF 'Relação de Itens' para extrair o texto e os itens."""
    print(f"    > Processando Relação de Itens: {pdf_path.name}")
    text = ""
    try:
        with fitz.open(pdf_path) as doc:
            for page in doc:
                text += page.get_text()
    except Exception as e:
        print(f"    > ERRO ao ler o PDF {pdf_path.name}: {e}")
        return []
    
    if not text.strip():
        print(f"    > AVISO: Nenhum texto extraído de {pdf_path.name}")
        return []
    
    return extrair_itens_pdf_texto(text)

def processar_xlsx_itens(xlsx_path: Path):
    """
    Processa um arquivo .xlsx para extrair uma lista de itens.
    Tenta mapear colunas com nomes variáveis para um padrão definido.
    """
    print(f"    > Processando planilha de itens: {xlsx_path.name}")
    try:
        df = pd.read_excel(xlsx_path, sheet_name=None) # Lê todas as abas
    except Exception as e:
        print(f"      - ❌ Falha ao ler o arquivo Excel '{xlsx_path.name}': {e}")
        return []

    # Mapeamento de possíveis nomes de coluna para o nosso padrão
    COLUNA_MAP = {
        'Nº': ['item', 'nº', 'numero', 'número'],
        'DESCRICAO': ['desc', 'descrição', 'descricao', 'especificação', 'especificacao', 'objeto', 'produto', 'histórico', 'historico'],
        'QTDE': ['qtd', 'qtde', 'quantidade'],
        'VALOR_UNIT': ['valor unitario', 'valor unitário', 'vr. unit', 'vr unit', 'preço unitário', 'preco unitario'],
        'VALOR_TOTAL': ['valor total', 'vr. total', 'vr total', 'preço total', 'preco total'],
        'UNID_FORN': ['unidade', 'unid', 'un', 'unid. forn.'],
    }

    itens_encontrados = []

    for sheet_name, sheet_df in df.items():
        if sheet_df.empty:
            continue

        colunas_renomeadas = {}
        colunas_df = [str(c).lower().strip() for c in sheet_df.columns]

        for col_padrao, nomes_possiveis in COLUNA_MAP.items():
            for nome_possivel in nomes_possiveis:
                if nome_possivel in colunas_df:
                    idx = colunas_df.index(nome_possivel)
                    colunas_renomeadas[sheet_df.columns[idx]] = col_padrao
                    break # Pega a primeira correspondência
        
        # Se encontrou pelo menos 'Nº' e 'DESCRICAO', processa
        if 'Nº' in colunas_renomeadas.values() and 'DESCRICAO' in colunas_renomeadas.values():
            sheet_df = sheet_df.rename(columns=colunas_renomeadas)
            itens_encontrados.extend(sheet_df.to_dict('records'))
            print(f"      - ✅ {len(sheet_df)} itens encontrados na aba '{sheet_name}'.")

    return itens_encontrados

# REMOVIDA: A função main() original será substituída pela nova lógica de orquestração
# def main():
#     """
#     Função principal que coordena o processamento multimodal dos editais.
#     """
#     print("Iniciando processamento multimodal dos editais...")
    
#     # Processa cada pasta na pasta de editais
#     for pasta_edital in PASTA_EDITAIS.iterdir():
#         if not pasta_edital.is_dir():
#             continue
            
#         try:
#             # Processa a pasta do edital
#             itens = processar_pasta_edital(pasta_edital)
            
#             if not itens:
#                 print(f"Nenhum item relevante encontrado em: {pasta_edital.name}")
#                 continue
            
#             # Cria DataFrame com os itens encontrados
#             df = pd.DataFrame(itens)
            
#             # Salva os resultados em um arquivo Excel
#             output_file = pasta_edital / f"itens_extraidos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
#             df.to_excel(output_file, index=False)
#             print(f"Resultados salvos em: {output_file}")
            
#         except Exception as e:
#             print(f"Erro ao processar pasta {pasta_edital.name}: {e}")

# if __name__ == "__main__":
#     main()

def tratar_dataframe(df):
    """Aplica tratamento e padronização em um DataFrame de itens."""
    if df.empty:
        return df

    # Garante que a coluna exista antes de tentar converter
    if 'QTDE' in df.columns:
        # Converter QTDE para numérico, mantendo NaN para valores inválidos/vazios
        df['QTDE'] = pd.to_numeric(df['QTDE'], errors='coerce')

    # Limpar e converter colunas de valor para numérico
    for col in ['VALOR_UNIT', 'VALOR_TOTAL']:
        if col in df.columns:
            # Assegurar que a coluna é string antes de usar métodos .str
            series = df[col].astype(str)
            
            # Cria uma máscara para valores que contêm vírgula (formato brasileiro, ex: "1.234,56")
            mask_br_format = series.str.contains(',', na=False)
            
            # Cria uma série para armazenar os resultados. Inicializa com os valores originais.
            cleaned_series = series.copy()
            
            # Aplica a limpeza APENAS nos valores com vírgula
            # 1. Remove o ponto (milhar)
            # 2. Substitui a vírgula (decimal) por ponto
            if mask_br_format.any():
                cleaned_br = series[mask_br_format].str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                cleaned_series.loc[mask_br_format] = cleaned_br

            # Converte a série limpa para numérico.
            # Valores que já estavam no formato "1234.56" ou que foram corrigidos passarão.
            # Valores inválidos se tornarão NaN.
            df[col] = pd.to_numeric(cleaned_series, errors='coerce')

    # Tenta calcular VALOR_UNIT se estiver faltando, mas outras informações estiverem presentes
    # Usamos isnull() para checar células vazias (NaN)
    if 'VALOR_UNIT' in df.columns and 'VALOR_TOTAL' in df.columns and 'QTDE' in df.columns:
        mask_unit = (df['VALOR_UNIT'].isnull()) & (df['VALOR_TOTAL'].notna()) & (df['QTDE'].notna() & df['QTDE'] > 0)
        if mask_unit.any():
            print(f"    > Preenchendo {mask_unit.sum()} VALOR_UNIT ausente(s) a partir do VALOR_TOTAL e QTDE.")
            df.loc[mask_unit, 'VALOR_UNIT'] = df.loc[mask_unit, 'VALOR_TOTAL'] / df.loc[mask_unit, 'QTDE']

    # Recalcula VALOR_TOTAL para garantir consistência onde for possível
    if 'QTDE' in df.columns and 'VALOR_UNIT' in df.columns:
        mask_total = df['QTDE'].notna() & df['VALOR_UNIT'].notna()
        # Se VALOR_TOTAL não existe, cria a coluna
        if 'VALOR_TOTAL' not in df.columns:
            df['VALOR_TOTAL'] = pd.NA
        # Adicionamos uma verificação para não recalcular se o valor total já existe e é consistente
        # Isso evita sobrescrever um valor total extraído corretamente que tenha um pequeno erro de arredondamento
        # em comparação com o cálculo. Vamos recalcular apenas se VALOR_TOTAL estiver vazio.
        mask_recalc_total = mask_total & df['VALOR_TOTAL'].isnull()
        if mask_recalc_total.any():
            print(f"    > Calculando {mask_recalc_total.sum()} VALOR_TOTAL ausente(s) a partir de QTDE e VALOR_UNIT.")
            df.loc[mask_recalc_total, 'VALOR_TOTAL'] = df.loc[mask_recalc_total, 'QTDE'] * df.loc[mask_recalc_total, 'VALOR_UNIT']
    
    # As colunas de valor agora são numéricas (float), com NaN para vazios.
    # A conversão de volta para string foi removida para permitir cálculos em outros scripts.
    return df

def gerar_conteudo_com_fallback(prompt: str, modelos: list[str], image_base64: str | None = None) -> str | None:
    """
    Tenta gerar conteúdo usando a API Google Generative AI com uma lista de modelos de fallback.
    Pode ser usada para texto puro ou com uma única imagem.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("   - ❌ GOOGLE_API_KEY não encontrada no arquivo .env")
        return None

    # Decodifica a imagem base64 para PIL Image se fornecida
    image = None
    if image_base64:
        try:
            image_data = base64.b64decode(image_base64)
            image = Image.open(BytesIO(image_data))
        except Exception as e:
            print(f"   - ❌ Erro ao decodificar imagem base64: {e}")
            return None

    for nome_modelo in modelos:
        for attempt in range(MAX_RETRIES):
            try:
                print(f"   - Tentando (tentativa {attempt+1}/{MAX_RETRIES}) modelo '{nome_modelo}'...")
                model = genai.GenerativeModel(nome_modelo)

                # Prepara o conteúdo para a geração
                content_parts = [prompt]
                if image:
                    content_parts.append(image)

                response = model.generate_content(content_parts, request_options={"timeout": TIMEOUT})

                # Verifica se a resposta contém partes válidas
                if not response.parts:
                    finish_reason = response.candidates[0].finish_reason.name if response.candidates else 'N/A'
                    print(f"   - ❌ Resposta vazia do modelo '{nome_modelo}'. Motivo: {finish_reason}.")
                    if attempt == MAX_RETRIES - 1:  # Se for a última tentativa, falha
                        break  # Sai do loop de tentativas para este modelo
                    else:  # Se não for a última, tenta novamente
                        time.sleep(DELAY_BETWEEN_RETRIES)
                        continue

                print(f"   - Sucesso com o modelo '{nome_modelo}'.")
                return response.text

            except google_exceptions.ResourceExhausted as e:
                print(f"   - Cota excedida para o modelo '{nome_modelo}'. Tentando o próximo da lista.")
                time.sleep(5)
                break  # Sai do loop de tentativas e passa para o próximo modelo
            except Exception as e:
                print(f"   - ❌ Erro inesperado com o modelo '{nome_modelo}': {e}")
                if attempt == MAX_RETRIES - 1:
                    break
                else:
                    time.sleep(DELAY_BETWEEN_RETRIES)
                    continue

    print("   - ❌ FALHA TOTAL: Todos os modelos e tentativas falharam.")
    return None

def construir_prompt_enriquecimento_multimodal(df_itens):
    """
    Constrói o prompt para o modelo multimodal enriquecer itens com referências da imagem.
    """
    itens_lista = df_itens[['Nº', 'DESCRICAO']].to_dict('records')
    itens_texto = "\n".join([f"{item['Nº']}: {item['DESCRICAO']}" for item in itens_lista])

    return f"""
    Você é um assistente especializado em analisar editais de licitação.

    Analise a imagem fornecida de uma página do edital e extraia as descrições detalhadas de referência para os itens listados abaixo.

    Itens a enriquecer:
    {itens_texto}

    Para cada item, encontre a descrição detalhada correspondente na imagem da página do edital.

    Retorne no formato '<--|-->' como separador. NÃO use aspas.
    A saída deve ter apenas 2 colunas: 'Nº' e 'REFERENCIA'.

    O formato de saída DEVE ser:
    Nº<--|-->REFERENCIA
    1<--|-->Descrição detalhada do item 1.
    2<--|-->Descrição detalhada do item 2.

    IMPORTANTE: Use '<--|-->' como separador. Não inclua nenhuma explicação ou formatação extra. Se não encontrar referência para um item, deixe vazio.
    """

def construir_prompt_extracao_multimodal(contexto: str = "") -> str:
    """
    Constrói o prompt para o modelo multimodal extrair informações de uma imagem de edital.
    """
    return f"""Faça a extração dos dados de itens de um edital de licitação a partir da imagem fornecida.

    {contexto}

    Retorne as informações no seguinte formato EXATO, usando '<--|-->' como separador:
    Nº<--|-->DESCRICAO<--|-->QTDE<--|-->VALOR_UNIT<--|-->UNID_FORN<--|-->LOCAL_ENTREGA

    Exemplo:
    1<--|-->Violão Clássico Acústico<--|-->10<--|-->1500,00<--|-->Unidade<--|-->Campus São Paulo
    
    IMPORTANTE:
    - Retorne APENAS os dados no formato especificado
    - Se alguma informação não estiver disponível, preencha com a palavra: nan
    - Não inclua cabeçalhos, explicações ou informações adicionais
    - Inclua TODOS os itens encontrados na imagem
    """

# NOVA FUNÇÃO: construir_prompt_extracao_itens (para fallback de texto)
def construir_prompt_extracao_itens(texto_pdf: str) -> str:
    """
    Constrói o prompt para o modelo de linguagem extrair itens de um texto bruto de PDF.
    """
    return f"""Você é um assistente especializado em extrair informações de editais de licitação.
    
    Analise o texto do edital fornecido e extraia as seguintes informações para cada item:
    1. Número do item
    2. Descrição detalhada do item
    3. Quantidade
    4. Valor unitário
    5. Unidade de fornecimento
    6. Local de entrega (se disponível)

    Texto do Edital:
    {texto_pdf}

    Retorne as informações no seguinte formato EXATO, usando '<--|-->' como separador:
    Nº<--|-->DESCRICAO<--|-->QTDE<--|-->VALOR_UNIT<--|-->UNID_FORN<--|-->LOCAL_ENTREGA

    Exemplo:
    1<--|-->Violão Clássico Acústico<--|-->10<--|-->1500,00<--|-->Unidade<--|-->Campus São Paulo
    2<--|-->Microfone Condensador Profissional<--|-->5<--|-->800,00<--|-->Peça<--|-->Auditório Central
    
    IMPORTANTE:
    - Retorne APENAS os dados no formato especificado
    - Se alguma informação não estiver disponível, preencha com a palavra: nan
    - Não inclua cabeçalhos, explicações ou informações adicionais
    - Inclua TODOS os itens encontrados no texto
    """

# NOVA FUNÇÃO: extrair_texto_de_pdf (para o razao.txt, se ainda for necessário)
def extrair_texto_de_pdf(pdf_path: Path) -> str:
    """
    Extrai todo o texto de um arquivo PDF.
    """
    text = ""
    try:
        with fitz.open(pdf_path) as doc:
            for page in doc:
                text += page.get_text("text", sort=True) # sort=True para melhor ordenação do texto
        print(f"      - ✅ Texto extraído de '{pdf_path.name}'.")
        return text
    except Exception as e:
        print(f"      - ❌ ERRO ao extrair texto do PDF '{pdf_path.name}': {e}")
        return ""


def descompactar_e_organizar_recursivamente(pasta_path: Path):
    """
    Procura por arquivos .zip e .rar em `pasta_path` e em todas as suas subpastas,
    extrai seu conteúdo para a `pasta_path` principal e remove o arquivo compactado original.
    Repete o processo até que não haja mais arquivos compactados.
    """
    while True:
        # Busca arquivos .zip e .rar em todos os níveis a partir da pasta_path
        # O processamento de .rar foi desativado temporariamente para evitar erros.
        arquivos_compactados = list(pasta_path.rglob('*.zip')) # + list(pasta_path.rglob('*.rar'))

        if not arquivos_compactados:
            print("    > Nenhum arquivo compactado encontrado. Finalizando descompactação.")
            break

        print(f"    > Encontrado(s) {len(arquivos_compactados)} arquivo(s) compactado(s) para processar nesta rodada.")

        for file_path in arquivos_compactados:
            print(f"      - Processando: {file_path.relative_to(pasta_path)}")
            temp_extract_dir = pasta_path / f"temp_extract_{file_path.stem}"
            temp_extract_dir.mkdir(exist_ok=True)

            try:
                if file_path.suffix.lower() == '.zip':
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        zip_ref.extractall(temp_extract_dir)
                # elif file_path.suffix.lower() == '.rar':
                #     with rarfile.RarFile(file_path, 'r') as rar_ref:
                #         rar_ref.extractall(temp_extract_dir)

                # Move todos os arquivos extraídos para a pasta principal
                for item in temp_extract_dir.rglob('*'):
                    if item.is_file():
                        destino = pasta_path / item.name
                        # Evita sobrescrever arquivos com o mesmo nome, adicionando um sufixo
                        counter = 1
                        while destino.exists():
                            destino = pasta_path / f"{item.stem}_{counter}{item.suffix}"
                            counter += 1
                        shutil.move(str(item), str(destino))

                print(f"      - ✅ '{file_path.name}' descompactado e arquivos movidos para a raiz do edital.")
                # Remove o arquivo compactado original e a pasta temporária
                file_path.unlink()
                shutil.rmtree(temp_extract_dir)

            except Exception as e:
                print(f"      - ❌ Falha ao descompactar '{file_path.name}': {e}")
                # Limpa a pasta temporária mesmo em caso de erro
                if temp_extract_dir.exists():
                    shutil.rmtree(temp_extract_dir)

def descompactar_arquivos_compactados_legado(pasta_path: Path):
    """
    (LEGADO) Procura por arquivos .zip e .rar na pasta e os descompacta em um subdiretório 'unzipped'.
    Retorna o caminho para a pasta com os arquivos descompactados, ou a pasta original se não houver zips.
    """
    arquivos_compactados = list(pasta_path.glob('*.zip')) + list(pasta_path.glob('*.rar'))
    if not arquivos_compactados:
        return pasta_path # Nenhuma ação necessária

    pasta_unzipped = pasta_path / "unzipped"
    pasta_unzipped.mkdir(exist_ok=True)
    
    print(f"    > Encontrado(s) {len(arquivos_compactados)} arquivo(s) compactado(s). Descompactando...")
    for file_path in arquivos_compactados:
        if file_path.suffix.lower() == '.zip':
            try:
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(pasta_unzipped)
                print(f"      - ✅ '{file_path.name}' (ZIP) descompactado em '{pasta_unzipped.name}/'")
            except Exception as e:
                print(f"      - ❌ Falha ao descompactar '{file_path.name}': {e}")
        elif file_path.suffix.lower() == '.rar':
            try:
                with rarfile.RarFile(file_path, 'r') as rar_ref:
                    rar_ref.extractall(pasta_unzipped)
                print(f"      - ✅ '{file_path.name}' (RAR) descompactado em '{pasta_unzipped.name}/'")
            except rarfile.NeedFirstVolume:
                 print(f"      - ⚠️ AVISO: '{file_path.name}' é parte de um arquivo multi-volume. Apenas o primeiro volume é processado.")
            except Exception as e:
                print(f"      - ❌ Falha ao descompactar '{file_path.name}': {e}. Verifique se o 'unrar' está instalado e no PATH.")
    
    return pasta_unzipped

def extrair_contexto_relevante_de_pdf(pdf_path: Path, df_itens: pd.DataFrame, margem_paginas: int = 1) -> str:

    """
    Extrai texto de um PDF apenas das páginas que contêm referências aos itens de um DataFrame,
    incluindo uma margem de páginas antes e depois.
    """
    if df_itens.empty or 'Nº' not in df_itens.columns:
        return ""

    paginas_relevantes = set()
    termos_busca = [f"item {n}" for n in df_itens['Nº'].unique()]
    
    try:
        with fitz.open(pdf_path) as doc:
            for i, page in enumerate(doc):
                texto_pagina = page.get_text("text").lower()
                if any(termo in texto_pagina for termo in termos_busca):
                    # Adiciona a página encontrada e as páginas na margem
                    inicio = max(0, i - margem_paginas)
                    fim = min(len(doc) - 1, i + margem_paginas)
                    for num_pagina in range(inicio, fim + 1):
                        paginas_relevantes.add(num_pagina)
            
            # Extrai o texto das páginas relevantes e ordenadas
            contexto_final = "".join(doc[i].get_text("text", sort=True) for i in sorted(list(paginas_relevantes)))
            return contexto_final
    except Exception as e:
        print(f"      - ⚠️ Erro ao extrair contexto relevante de '{pdf_path.name}': {e}")
        return ""

def achatar_estrutura_de_diretorios(base_path: Path):
    """
    Move todos os arquivos de quaisquer subdiretórios para a pasta principal (`base_path`)
    e, em seguida, remove as subpastas agora vazias. Garante uma estrutura de arquivos plana.
    """
    print(f"    > Verificando e achatando estrutura de diretórios em '{base_path.name}'...")
    # Lista todas as subpastas diretas. Usamos .rglob() depois para pegar arquivos aninhados.
    subdirs = [d for d in base_path.iterdir() if d.is_dir()]

    if not subdirs:
        print("      - Nenhuma subpasta encontrada. Estrutura já está plana.")
        return

    moved_files_count = 0
    for subdir in subdirs:
        # Itera recursivamente em todos os arquivos dentro da subpasta
        for file_path in subdir.rglob('*'):
            if file_path.is_file():
                destination_path = base_path / file_path.name
                # Lida com colisões de nome para não sobrescrever arquivos
                counter = 1
                while destination_path.exists():
                    destination_path = base_path / f"{file_path.stem}_{counter}{file_path.suffix}"
                    counter += 1
                
                try:
                    shutil.move(str(file_path), str(destination_path))
                    moved_files_count += 1
                except Exception as e:
                    print(f"      - ❌ Falha ao mover '{file_path.name}': {e}")
        # Após mover todos os arquivos, remove a árvore de diretórios da subpasta
        shutil.rmtree(subdir)
    print(f"      - ✅ Estrutura achatada. {moved_files_count} arquivo(s) movido(s) para a pasta principal e subpastas removidas.")
# =====================================================================================
# 3. ORQUESTRADOR PRINCIPAL
# =====================================================================================

def processar_pasta_edital(pasta_path):
    """
    Orquestra o pipeline completo para uma única pasta de edital, combinando eficiência e robustez.
    - Pula pastas se o resultado final já existir.
    - Prioriza a extração de 'RelacaoItens.pdf'.
    - Usa o PDF principal para enriquecer os dados com IA.
    - Possui um fallback para extrair itens com IA se 'RelacaoItens.pdf' falhar.
    """
    nome_pasta = pasta_path.name
    print(f"\n--- Processando Edital: {nome_pasta} ---")
    
    # --- CAMINHOS DE SAÍDA ---
    # O razao.txt não será mais o principal, mas pode ser usado para fallback de texto
    caminho_razao_txt = pasta_path / "razao.txt" 
    caminho_xlsx_itens = pasta_path / f"{nome_pasta}_itens.xlsx"
    caminho_final_xlsx = pasta_path / f"{nome_pasta}_master.xlsx"

    # --- ETAPA 0: VERIFICAR SE JÁ FOI PROCESSADO ---
    if caminho_final_xlsx.exists():
        print(f"  >✅ RESULTADO FINAL JÁ EXISTE ({caminho_final_xlsx.name}). Pulando processamento.")
        try:
            df_itens = pd.read_excel(caminho_xlsx_itens) if caminho_xlsx_itens.exists() else pd.DataFrame()
            df_enriquecido = pd.read_excel(caminho_final_xlsx)
            return df_itens, df_enriquecido
        except Exception as e:
            print(f"  > AVISO: Falha ao ler arquivos existentes. {e}. O processamento será refeito.")

    # --- ETAPA 1: ACHATAR ESTRUTURA DE PASTAS ---
    print(f"  [ETAPA 1/6] Garantindo que todos os arquivos estejam na pasta principal...")
    achatar_estrutura_de_diretorios(pasta_path)

    # --- ETAPA 1: DESCOMPACTAR ARQUIVOS RECURSIVAMENTE ---
    print(f"  [ETAPA 1/4] Verificando e descompactando arquivos recursivamente...")
    descompactar_e_organizar_recursivamente(pasta_path)

    # --- ETAPA 2: EXTRAIR ITENS DE ARQUIVOS ESTRUTURADOS (PDF/XLSX) ---
    print(f"  [ETAPA 2/4] Extraindo itens de 'RelacaoItens.pdf' ou planilhas .xlsx...")
    df_itens = pd.DataFrame()
    if caminho_xlsx_itens.exists():
        print(f"    > Arquivo de itens ({caminho_xlsx_itens.name}) já existe. Carregando...")
        df_itens = pd.read_excel(caminho_xlsx_itens)
    else:
        itens_encontrados = []
        # 1. Tenta extrair de planilhas .xlsx/.xls
        planilhas = list(pasta_path.glob("*.xlsx")) + list(pasta_path.glob("*.xls"))
        if planilhas:
            for planilha in planilhas:
                itens_encontrados.extend(processar_xlsx_itens(planilha))

        # 2. Se não encontrou em planilhas, tenta extrair de RelacaoItens.pdf
        pdfs_relacao = list(pasta_path.glob("RelacaoItens*.pdf"))
        if not itens_encontrados and pdfs_relacao:
            for pdf in pdfs_relacao:
                itens_encontrados.extend(processar_pdf_relacao_itens(pdf))
        
        if itens_encontrados:
            df_itens = pd.DataFrame(itens_encontrados)
            df_itens["ARQUIVO"] = nome_pasta
            df_itens = tratar_dataframe(df_itens)
            df_itens.to_excel(caminho_xlsx_itens, index=False)
            print(f"    > {len(df_itens)} itens extraídos e salvos em: {caminho_xlsx_itens.name}")
        elif pdfs_relacao:
            print("    > AVISO: 'RelacaoItens.pdf' encontrado, mas nenhum item pôde ser extraído.")
        elif planilhas:
            print("    > AVISO: Planilhas encontradas, mas nenhum item com estrutura reconhecível foi extraído.")
        else:
            print("    > AVISO: Nenhum arquivo estruturado (RelacaoItens.pdf ou .xlsx) para extração de itens foi encontrado.")

    # --- ETAPA 3: PROCESSAMENTO COM IA MULTIMODAL (EXTRAÇÃO DE ITENS DE PDF PRINCIPAL) ---
    print(f"  [ETAPA 3/4] Processando PDFs principais com IA Multimodal para extração de itens...")
    
    # Se df_itens ainda estiver vazio, tentamos a extração multimodal dos PDFs principais
    if df_itens.empty:
        pdfs_principais = [p for p in pasta_path.glob("*.pdf") if not p.name.lower().startswith("relacaoitens")]
        if pdfs_principais:
            all_multimodal_items = []
            for pdf_principal in pdfs_principais:
                print(f"    > Processando PDF principal com IA Multimodal: {pdf_principal.name}")
                imagens_base64 = pdf_to_base64_images(pdf_principal)
                if not imagens_base64:
                    print(f"      - Falha ao converter PDF {pdf_principal.name} para imagens.")
                    continue

                for num_pagina, imagem_base64 in enumerate(imagens_base64, 1):
                    print(f"      - Processando página {num_pagina}/{len(imagens_base64)} de {pdf_principal.name}...")
                    imagem_base64_resized = resize_image_if_needed(imagem_base64)
                    prompt_multimodal = construir_prompt_extracao_multimodal()
                    
                    conteudo_ia = gerar_conteudo_com_fallback(prompt_multimodal, LLM_MODELS_FALLBACK, imagem_base64_resized)
                    
                    if not conteudo_ia:
                        print(f"        - Falha ao obter conteúdo da IA para página {num_pagina}.")
                        continue
                    
                    for linha in conteudo_ia.strip().split('\n'):
                        if not linha or '<--|-->' not in linha:
                            continue

                        campos = linha.split('<--|-->')
                        if len(campos) < 6:
                            print(f"        - AVISO: Linha da IA com menos de 6 campos: {linha}")
                            continue

                        num, desc, qtd, val_unit, unid, local = campos[:6]
                        
                        # Verifica se o item é relevante usando os filtros existentes
                        if REGEX_FILTRO.search(desc) and not REGEX_EXCLUIR.search(desc):
                            item = {
                                "Nº": num,
                                "DESCRICAO": desc,
                                "QTDE": qtd,
                                "VALOR_UNIT": val_unit,
                                "UNID_FORN": unid,
                                "LOCAL_ENTREGA": local,
                                "ARQUIVO": nome_pasta # Adiciona o nome da pasta
                            }
                            all_multimodal_items.append(item)
            
            if all_multimodal_items:
                df_itens = pd.DataFrame(all_multimodal_items)
                df_itens = tratar_dataframe(df_itens)
                df_itens.to_excel(caminho_xlsx_itens, index=False)
                print(f"    > {len(df_itens)} itens extraídos via IA Multimodal e salvos em: {caminho_xlsx_itens.name}")
            else:
                print("    > Nenhum item relevante extraído via IA Multimodal dos PDFs principais.")
        else:
            print("    > Nenhum PDF principal encontrado para processamento multimodal.")

    # --- ETAPA 4: ENRIQUECIMENTO COM IA MULTIMODAL (PROCESSANDO PDF DIRETAMENTE) ---
    print(f"  [ETAPA 4/4] Enriquecendo itens com IA multimodal processando PDF diretamente...")

    df_final = pd.DataFrame()

    if not df_itens.empty:
        # Encontrar PDFs principais para enriquecimento
        pdfs_principais = [p for p in pasta_path.glob("*.pdf") if not p.name.lower().startswith("relacaoitens")]
        if pdfs_principais:
            pdf_para_enriquecimento = pdfs_principais[0]  # Usar o primeiro PDF
            print(f"    > Processando PDF para enriquecimento: {pdf_para_enriquecimento.name}")
            
            # Converter PDF para imagens
            imagens_base64 = pdf_to_base64_images(pdf_para_enriquecimento)
            if imagens_base64:
                referencias = {}
                for num_pagina, imagem_base64 in enumerate(imagens_base64, 1):
                    print(f"      - Processando página {num_pagina}/{len(imagens_base64)} para enriquecimento...")
                    imagem_base64 = resize_image_if_needed(imagem_base64)
                    prompt_enriquecimento = construir_prompt_enriquecimento_multimodal(df_itens)
                    resposta = gerar_conteudo_com_fallback(prompt_enriquecimento, LLM_MODELS_FALLBACK, imagem_base64)
                    
                    if resposta:
                        for linha in resposta.strip().split('\n'):
                            if '<--|-->' in linha:
                                campos = linha.split('<--|-->')
                                if len(campos) == 2:
                                    num, ref = campos
                                    num = num.strip()
                                    ref = ref.strip()
                                    if ref and num not in referencias:  # Evitar sobrescrever
                                        referencias[num] = ref
                
                if referencias:
                    df_referencia = pd.DataFrame(list(referencias.items()), columns=['Nº', 'REFERENCIA'])
                    key_col = 'Nº'
                    df_itens[key_col] = df_itens[key_col].astype(str)
                    df_referencia[key_col] = df_referencia[key_col].astype(str)
                    df_final = pd.merge(df_itens, df_referencia, on=key_col, how='left')
                    print("    > Itens enriquecidos pela IA multimodal.")
                else:
                    df_final = df_itens.copy()
                    df_final['REFERENCIA'] = "Nenhuma referência encontrada via multimodal."
            else:
                df_final = df_itens.copy()
                df_final['REFERENCIA'] = "Falha ao converter PDF para imagens para enriquecimento."
        else:
            df_final = df_itens.copy()
            df_final['REFERENCIA'] = "Nenhum PDF principal encontrado para enriquecimento multimodal."
    else:
        print("    > Nenhum item para enriquecer.")

    # --- ETAPA FINAL: SALVAR RESULTADO ---
    print(f"  [ETAPA FINAL] Finalizando e salvando...")
    if not df_final.empty:
        # Reordenar colunas para o padrão
        df_final = tratar_dataframe(df_final) # Trata os valores extraídos pela IA
        desired_order = ['Nº', 'DESCRICAO', 'REFERENCIA', 'QTDE', 'VALOR_UNIT', 'VALOR_TOTAL', 'UNID_FORN', 'LOCAL_ENTREGA', 'ARQUIVO']
        df_final = df_final.reindex(columns=desired_order, fill_value='')
        
        df_final.to_excel(caminho_final_xlsx, index=False)
        print(f"    >✅ SUCESSO! Planilha final salva como: {caminho_final_xlsx.name}")
        return df_itens, df_final
    else:
        print("    >❌ FALHA: Nenhum item foi extraído ou gerado. Criando placeholder.")
        headers = ['Nº', 'DESCRICAO', 'REFERENCIA', 'QTDE', 'VALOR_UNIT', 'VALOR_TOTAL', 'UNID_FORN', 'LOCAL_ENTREGA', 'ARQUIVO']
        df_placeholder = pd.DataFrame([{col: '' for col in headers}], columns=headers)
        df_placeholder['ARQUIVO'] = nome_pasta
        df_placeholder.to_excel(caminho_final_xlsx, index=False)
        return None, df_placeholder


def main():
    """
    Função principal que itera sobre todas as pastas de editais e as processa.
    Ao final, gera os arquivos consolidados 'summary.xlsx' e 'master.xlsx'.
    """
    print("="*80)
    print("INICIANDO O PROCESSO DE EXTRAÇÃO E ANÁLISE DE EDITAIS (V2 - MULTIMODAL)")
    print("="*80)

    if not PASTA_EDITAIS.is_dir():
        print(f"ERRO CRÍTICO: O diretório de editais '{PASTA_EDITAIS}' não foi encontrado.")
        return

    todos_os_itens_base = []
    todos_os_itens_finais = []

    pastas_de_editais = sorted([d for d in PASTA_EDITAIS.iterdir() if d.is_dir()])
    for i, pasta in enumerate(pastas_de_editais):
        df_base, df_final = processar_pasta_edital(pasta)
        if df_base is not None and not df_base.empty:
            todos_os_itens_base.append(df_base)
        if df_final is not None and not df_final.empty:
            todos_os_itens_finais.append(df_final)
        print(f"--- Edital {i+1}/{len(pastas_de_editais)} concluído. ---")

    print("\n--- Finalizando e Gerando Arquivos Consolidados ---")

    # Gerar summary.xlsx com todos os itens finais (de _master.xlsx)
    if todos_os_itens_finais:
        df_summary = pd.concat(todos_os_itens_finais, ignore_index=True)
        df_summary = tratar_dataframe(df_summary)
        df_summary.to_excel(SUMMARY_EXCEL_PATH, index=False)
        print(f"✅ Arquivo 'summary.xlsx' criado com {len(df_summary)} itens totais (dos arquivos _master).")
    else:
        print("🟡 Nenhum item final foi processado para gerar o 'summary.xlsx'.")

    # Gerar master.xlsx com itens finais filtrados por palavras-chave
    if todos_os_itens_finais:
        df_master = pd.concat(todos_os_itens_finais, ignore_index=True)
        
        # Garantir que as colunas de filtro existam e sejam string
        if 'DESCRICAO' not in df_master.columns:
            df_master['DESCRICAO'] = ''
        if 'REFERENCIA' not in df_master.columns:
            df_master['REFERENCIA'] = ''
        df_master['DESCRICAO'] = df_master['DESCRICAO'].astype(str)
        df_master['REFERENCIA'] = df_master['REFERENCIA'].astype(str)

        # Aplicar filtro de inclusão (palavras-chave)
        mask_descricao = df_master['DESCRICAO'].apply(lambda x: bool(REGEX_FILTRO.search(x)))
        mask_referencia = df_master['REFERENCIA'].apply(lambda x: bool(REGEX_FILTRO.search(x)))
        df_com_relevantes = df_master[mask_descricao | mask_referencia]

        # Aplicar filtro de exclusão, mas com exceções
        def deve_manter(row):
            texto_completo = f"{row['DESCRICAO']} {row['REFERENCIA']}"
            # Se o texto contiver uma palavra de exceção (ex: 'drone'), mantenha o item.
            if REGEX_EXCECAO.search(texto_completo):
                return True
            # Caso contrário, verifique se contém uma palavra de exclusão. Se contiver, remova.
            if REGEX_EXCLUIR.search(texto_completo):
                return False
            # Se não contiver exceção nem exclusão, mantenha (já passou pelo filtro de inclusão).
            return True
        df_filtrado = df_com_relevantes[df_com_relevantes.apply(deve_manter, axis=1)].copy()

        # Adicionar coluna de timestamp
        df_filtrado['TIMESTAMP'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        df_filtrado.to_excel(FINAL_MASTER_PATH, index=False)
        print(f"✅ Arquivo 'master.xlsx' criado com {len(df_filtrado)} itens relevantes.")

        # --- Análise de Editais Ausentes no Master ---
        print("\n--- Análise de Editais Ausentes no Master ---")
        nomes_pastas_processadas = {p.name for p in pastas_de_editais}
        editais_no_master = set(df_filtrado['ARQUIVO'].unique())
        
        editais_nao_incluidos = nomes_pastas_processadas - editais_no_master
        
        if editais_nao_incluidos:
            print(f"🟡 {len(editais_nao_incluidos)} editais foram processados, mas não tiveram itens que passaram no filtro final:")
            for edital in sorted(list(editais_nao_incluidos)):
                print(f"  - {edital}")
        else:
            print("✅ Todos os editais processados tiveram pelo menos um item incluído no arquivo master.")
    else:
        print("🔴 Nenhum item final foi processado para gerar o 'master.xlsx'.")

    print("\n--- Limpando arquivos intermediários ---")
    for pasta in pastas_de_editais:
        caminho_itens_xlsx = pasta / f"{pasta.name}_itens.xlsx"
        caminho_razao_txt = pasta / "razao.txt"
        if caminho_razao_txt.exists():
            os.remove(caminho_razao_txt)
            print(f"  > Arquivo intermediário removido: {caminho_razao_txt.name}")
        if caminho_itens_xlsx.exists():
            try:
                os.remove(caminho_itens_xlsx)
                print(f"  > Arquivo intermediário removido: {caminho_itens_xlsx.name}")
            except OSError as e:
                print(f"  > ERRO ao remover {caminho_itens_xlsx.name}: {e}")

    print("="*80)
    print("PROCESSO CONCLUÍDO!")
    print("="*80)


if __name__ == "__main__":
    main()
