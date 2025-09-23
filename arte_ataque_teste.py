
import os
import re
from pathlib import Path
from io import StringIO

import pandas as pd
import fitz  # PyMuPDF
from pdf2image import convert_from_path
import pytesseract
import google.api_core.exceptions as google_exceptions
import time
import google.generativeai as genai
from dotenv import load_dotenv
import zipfile
from spacy.tokens import DocBin

# =====================================================================================
# 1. CONFIGURAÇÕES E CONSTANTES
# =====================================================================================

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# --- Configurações de Caminhos ---
PROJECT_ROOT = Path(r"c:\\Users\\pietr\\OneDrive\\.vscode\\arte_")
BASE_DIR = PROJECT_ROOT / "DOWNLOADS"
PASTA_EDITAIS = BASE_DIR / "EDITAIS"
SUMMARY_EXCEL_PATH = BASE_DIR / "summary_ml.xlsx"
FINAL_MASTER_PATH = BASE_DIR / "master_ataque.xlsx"

# --- Configurações de Ferramentas Externas ---
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
POPLER_PATH = SCRIPTS_DIR / "Release-25.07.0-0" / "poppler-25.07.0" / "Library" / "bin"
TESSERACT_CMD = SCRIPTS_DIR / "Tesseract-OCR" / "tesseract.exe"
pytesseract.pytesseract.tesseract_cmd = str(TESSERACT_CMD)

# --- Configuração do Modelo NER ---
MODEL_DIR = PROJECT_ROOT / "ml_models" / "ner_model"

# =====================================================================================
# 1.5. CLASSE DO EXTRATOR NER (INTEGRADA)
# =====================================================================================

class ItemExtractor:
    """
    Classe para carregar um modelo NER (Named Entity Recognition) treinado com spaCy
    e extrair informações estruturadas de textos de editais.
    """
    def __init__(self, model_path=MODEL_DIR):
        self.nlp = None
        if model_path.exists():
            try:
                print(f"Carregando modelo NER de: {model_path}")
                import spacy # Importa spacy apenas se o modelo existir
                self.nlp = spacy.load(model_path)
                print("✅ Modelo NER carregado com sucesso.")
            except Exception as e:
                print(f"⚠️ ERRO ao carregar modelo NER: {e}. O fallback para regex/LLM será usado.")
        else:
            print(f"⚠️ Modelo NER não encontrado em {model_path}. O fallback para regex/LLM será usado.")

    def is_ready(self):
        """Verifica se o modelo NLP foi carregado."""
        return self.nlp is not None

    def extract_items_from_text(self, text):
        """Usa o modelo NER para extrair uma lista de dicionários de itens."""
        if not self.is_ready():
            return []

        print("    > Extraindo itens com modelo NER...")
        doc = self.nlp(text)
        # A lógica de extração a partir de doc.ents dependeria do modelo treinado.
        # Esta é uma implementação placeholder.
        items = []
        # ... (lógica de extração de entidades) ...
        if items:
            print(f"    > ✅ Modelo NER extraiu {len(items)} itens.")
        else:
            print("    > ⚠️ Modelo NER não encontrou itens estruturados.")
        return items

# --- Configuração da API Generativa ---
LLM_MODELS_FALLBACK = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.5-pro",
    "gemini-1.5-flash",
]

API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    print("ERRO: A variável de ambiente GOOGLE_API_KEY não foi definida.")
else:
    genai.configure(api_key=API_KEY)

# --- Configuração do Extrator ML ---
EXTRACTOR_ML = ItemExtractor()

# --- Configurações de Filtro ---
PALAVRAS_CHAVE = [

    # ------------------ Categorias principais ------------------
    r'Instrumento Musical',r'Instrumento Musical - Sopro',r'Instrumento Musical - Corda',r'Instrumento Musical - Percussão',
    r'Peças e acessórios instrumento musical',    r'Peças E Acessórios Instrumento Musical',

    # ------------------ Sopros ------------------
    r'saxofone',r'trompete',r'tuba',r'clarinete',r'trompa', 
    r'óleo lubrificante', r'óleos para válvulas', r'corneta'

    # ------------------ Cordas ------------------
    r'violão',r'Guitarra',r'Violino',
    r'Viola',r'Cavaquinho',r'Bandolim',
    r'Ukulele',

    # ------------------ Percussão ------------------
    r'tarol', r'Bombo', r'CAIXA TENOR', r'Caixa tenor', r'Caixa de guerra',
    r'Bateria', r'Bateria completa', r'Bateria eletrônica',
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
    r'Microfone',
    r'Microfone direcional',
    r'Microfone Dinâmico',
    r'Microfone de Lapela',
    r'Suporte microfone',
    r'Base microfone',
    r'Medusa para microfone',
    r'Pré-amplificador microfone',
    r'Fone Ouvido', r'Gooseneck',

    # ------------------ Áudio (caixas, amplificação, interfaces) ------------------
    r'Caixa Acústica', r'Caixa de Som'
    r'Caixa som', r'Caixa Som'
    r'Subwoofer',
    r'Amplificador de áudio',
    r'Amplificador som',
    r'Amplificador fone ouvido',
    r'Interface de Áudio',
    r'Mesa áudio',

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
    r'notebook', r'Dosímetro Digital', r'Radiação',r'Raios X', r'Aparelho eletroestimulador',
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
# 2. FUNÇÕES DE EXTRAÇÃO E PROCESSAMENTO
# =====================================================================================

def descompactar_e_coletar_texto_pdfs(pasta_path: Path) -> str:
    """
    Descompacta todos os arquivos .zip na pasta e suas subpastas,
    depois extrai texto de todos os PDFs encontrados (exceto RelacaoItens).
    """
    textos_combinados = ""
    
    # 1. Descompactar arquivos .zip recursivamente em um loop para lidar com zips aninhados
    while True:
        zip_files = list(pasta_path.rglob("*.zip"))
        if not zip_files:
            break  # Sai do loop se não houver mais arquivos .zip

        print(f"    > Encontrados {len(zip_files)} arquivos .zip para descompactar nesta iteração.")
        for zip_path in zip_files:
            try:
                # Cria um diretório com o nome do zip para extrair o conteúdo
                extract_path = zip_path.parent / zip_path.stem
                extract_path.mkdir(exist_ok=True)
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_path)
                print(f"      - Descompactado: {zip_path.name} -> {extract_path.name}")
                os.remove(zip_path) # Remove o zip após a extração para não entrar em loop infinito
            except Exception as e:
                print(f"      - ERRO ao descompactar {zip_path.name}: {e}")

    # 2. Após toda a descompactação, coletar texto de todos os PDFs
    pdf_files = [p for p in pasta_path.rglob("*.pdf") if not p.name.lower().startswith("relacaoitens")]
    if pdf_files:
        print(f"    > Encontrados {len(pdf_files)} PDFs para extração de texto (OCR).")
        for pdf_path in pdf_files:
            # Substituído para usar a função inteligente que tenta extração direta primeiro
            textos_combinados += extrair_texto_de_pdf(pdf_path) + "\n\n"
            
    return textos_combinados.strip()

def extrair_texto_de_pdf(pdf_path: Path) -> str:
    """
    Tenta extrair texto diretamente do PDF. Se o resultado for insatisfatório
    (indicando um PDF baseado em imagem), usa OCR (Tesseract) como fallback.
    """
    texto_completo = ""
    print(f"    > Processando PDF: {pdf_path.name}")

    # --- TENTATIVA 1: Extração de texto direto (rápido) ---
    try:
        with fitz.open(pdf_path) as doc:
            for page in doc:
                texto_completo += page.get_text("text", sort=True) + "\n\n"
        
        # Verifica se o texto extraído é significativo (mais de 100 caracteres)
        if len(texto_completo.strip()) > 100:
            print("      - ✅ Texto extraído diretamente com sucesso.")
            return texto_completo.strip()
        else:
            print("      - ⚠️ Texto direto insuficiente. Tentando OCR como fallback...")
    except Exception as e:
        print(f"      - ⚠️ Falha na extração direta: {e}. Tentando OCR.")

    # --- TENTATIVA 2: Fallback para OCR (lento) ---
    try:
        texto_ocr = ""
        images = convert_from_path(pdf_path, dpi=300, poppler_path=POPLER_PATH)
        for i, img in enumerate(images):
            print(f"      - Lendo página {i+1}/{len(images)} (OCR)...")
            texto_ocr += pytesseract.image_to_string(img, lang='por') + "\n\n"
        print("      - ✅ Texto extraído via OCR com sucesso.")
        return texto_ocr.strip()
    except Exception as e:
        print(f"      - ❌ ERRO FATAL: Falha na extração direta e no OCR para o arquivo {pdf_path.name}: {e}")
        return "" # Retorna string vazia se ambos falharem

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

        descricao_match = re.search(r'Descrição Detalhada:\s*(.*?)(?=Tratamento Diferenciado:)|Aplicabilidade Decreto|$\s*', item_text, re.DOTALL | re.IGNORECASE)
        descricao = descricao_match.group(1).strip() if descricao_match else ""
        item_completo = f"{item_nome} {re.sub(r'\s+', ' ', re.sub(r'[^\w\s:,.()/-]', '', descricao))}"

        quantidade_match = re.search(r'Quantidade Total:\s*(\d+)', item_text, re.IGNORECASE)
        quantidade = quantidade_match.group(1) if quantidade_match else ""

        valor_unitario_match = re.search(r'Valor\s+Unitário[^:]*:\s*R?\$?\s*([\d.,]+)', item_text, re.IGNORECASE)
        valor_unitario = valor_unitario_match.group(1) if valor_unitario_match else ""

        valor_total_match = re.search(r'Valor\s+Total[^:]*:\s*R?\$?\s*([\d.,]+)', item_text, re.IGNORECASE)
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

def extrair_itens_tabela_generica(texto: str) -> list[dict]:
    """
    Extrai itens de tabelas mais genéricas ou mal formatadas, onde os valores
    podem estar em linhas diferentes. Foca em encontrar blocos de item.
    """
    print("    > Tentando extração com Regex para tabelas genéricas...")
    items = []
    # Padrão para encontrar um bloco que começa com um número de item
    # e vai até o próximo número de item ou o fim do texto.
    blocos = re.split(r'\n\s*(?=\d+\s+)', texto)

    for bloco in blocos:
        if not bloco.strip():
            continue

        # Tenta extrair os campos de cada bloco
        num_match = re.match(r'^\s*(\d+)', bloco)
        item_num = num_match.group(1) if num_match else ''

        # Regex mais flexíveis para encontrar os valores no bloco
        desc_match = re.search(r'(\d+)\s+(.*?)(?=CAT\s+MAT|VALOR|R\$)', bloco, re.DOTALL | re.IGNORECASE)
        descricao = desc_match.group(2).strip().replace('\n', ' ') if desc_match else ''

        qtde_match = re.search(r'QUANT\s*IDADE\s+(\d+)', bloco, re.IGNORECASE)
        quantidade = qtde_match.group(1) if qtde_match else ''

        # Procura por valor unitário e total, pegando o primeiro valor monetário que encontrar
        valor_match = re.search(r'R\$\s*([\d.,]+)', bloco)
        valor_unitario = valor_match.group(1).replace('.', '').replace(',', '.') if valor_match else ''

        if item_num and descricao:
            items.append({"Nº": item_num, "DESCRICAO": descricao, "QTDE": quantidade, "VALOR_UNIT": valor_unitario})
            print(f"      - Regex genérico encontrou Item: {item_num}")

    return items

def tratar_dataframe(df):
    """Aplica tratamento e padronização em um DataFrame de itens."""
    if df.empty:
        return df

    # Converter QTDE para numérico, mantendo NaN para valores inválidos/vazios
    df['QTDE'] = pd.to_numeric(df['QTDE'], errors='coerce')

    # Limpar e converter colunas de valor para numérico
    for col in ['VALOR_UNIT', 'VALOR_TOTAL']:
        # Assegurar que a coluna é string antes de usar métodos .str
        series = df[col].astype(str)
        # Limpeza: remove pontos (milhar) e substitui vírgula (decimal) por ponto
        cleaned_series = series.str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
        # Converte para numérico, valores inválidos viram NaN (Not a Number), que representa células vazias
        df[col] = pd.to_numeric(cleaned_series, errors='coerce')

    # Tenta calcular VALOR_UNIT se estiver faltando, mas outras informações estiverem presentes
    # Usamos isnull() para checar células vazias (NaN)
    mask_unit = (df['VALOR_UNIT'].isnull()) & (df['VALOR_TOTAL'].notna()) & (df['QTDE'].notna() & df['QTDE'] > 0)
    df.loc[mask_unit, 'VALOR_UNIT'] = df.loc[mask_unit, 'VALOR_TOTAL'] / df.loc[mask_unit, 'QTDE']

    # Recalcula VALOR_TOTAL para garantir consistência onde for possível
    mask_total = df['QTDE'].notna() & df['VALOR_UNIT'].notna()
    df.loc[mask_total, 'VALOR_TOTAL'] = df.loc[mask_total, 'QTDE'] * df.loc[mask_total, 'VALOR_UNIT']
    
    # As colunas de valor agora são numéricas (float), com NaN para vazios.
    # A conversão de volta para string foi removida para permitir cálculos em outros scripts.
    return df

def gerar_conteudo_com_fallback(prompt: str, modelos: list[str]) -> str | None:
    """
    Tenta gerar conteúdo usando uma lista de modelos em ordem de preferência.
    Se um modelo falhar por cota (ResourceExhausted), tenta o próximo.
    """
    if "API_KEY" not in globals() or not API_KEY:
        print("    > ERRO: API Key do Google não configurada. Pulando chamada da LLM.")
        return None

    for nome_modelo in modelos:
        try:
            print(f"    > Comunicando com a IA (modelo: {nome_modelo})...")
            model = genai.GenerativeModel(nome_modelo)
            response = model.generate_content(prompt)

            if not response.parts:
                finish_reason = response.candidates[0].finish_reason.name if response.candidates else 'N/A'
                print(f"    > ❌ A GERAÇÃO RETORNOU VAZIA. Motivo: {finish_reason}. Tentando próximo modelo.")
                continue
            print(f"    > ✅ IA respondeu com sucesso usando o modelo '{nome_modelo}'.")
            return response.text
        except google_exceptions.ResourceExhausted as e:
            print(f"    > ⚠️ Cota excedida para o modelo '{nome_modelo}'. Tentando o próximo da lista.")
            time.sleep(5)
            continue
        except Exception as e:
            print(f"    > ❌ Erro inesperado com o modelo '{nome_modelo}': {e}")
            return None
    print("    > ❌ FALHA TOTAL: Todos os modelos na lista de fallback falharam.")
    return None

def construir_prompt_referencia(df, texto_pdf):
    """Constrói o prompt para o modelo de linguagem ENRIQUECER itens."""
    return f"""
    Sua tarefa é extrair a descrição de referência para cada item de uma tabela, usando um texto de PDF como fonte.

    A tabela de itens original é:
    {df.to_csv(index=False)}

    O texto de referência do PDF é:
    {texto_pdf}

    Para cada item, encontre sua descrição detalhada no PDF.
    
    Retorne o resultado usando a sequência '<--|-->' como separador. NÃO use aspas.
    A saída deve ter apenas 2 colunas: 'Nº' e 'REFERENCIA'.

    O formato de saída DEVE ser:
    Nº<--|-->REFERENCIA
    1<--|-->Descrição detalhada do item 1.
    2<--|-->Descrição detalhada do item 2, que pode ter vírgulas, e não causa problema.

    IMPORTANTE: Use '<--|-->' como separador. Não inclua nenhuma explicação ou formatação extra.
    """

def construir_prompt_extracao_itens(texto_pdf):
    """Constrói o prompt para o modelo de linguagem EXTRAIR itens do zero."""
    return f"""
    Sua tarefa é analisar o texto de um edital de licitação e extrair TODOS os itens que estão sendo licitados.
    O texto do edital é:
    {texto_pdf}

    Para cada item encontrado, extraia seu número e a descrição completa.

    Retorne o resultado usando a sequência '<--|-->' como separador. NÃO use aspas.
    A saída deve ter apenas 2 colunas: 'Nº' e 'REFERENCIA'.

    O formato de saída DEVE ser:
    Nº<--|-->REFERENCIA
    1<--|-->Descrição detalhada do item 1.
    2<--|-->Descrição detalhada do item 2, que pode ter vírgulas, e não causa problema.

    IMPORTANTE: Use '<--|-->' como separador. Não inclua nenhuma explicação ou formatação extra. Liste todos os itens que encontrar.
    """

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
    
    # --- VERIFICAÇÃO DE TESTE ---
    # Para testar um edital específico, descomente as linhas abaixo
    # e substitua pelo nome da pasta do edital.
    # editais_para_testar = [
    #     "U_987971_E_900432025_25-09-2025_08h00m",
    #     "U_158125_E_905582025_02-10-2025_09h00m",
    #     "U_453902_E_900402025_03-10-2025_13h00m",
    #     "U_180322_E_900752025_01-10-2025_08h00m",
    #     "U_990138_E_900082025_26-09-2025_09h00m"
    # ]
    # if nome_pasta not in editais_para_testar:
    #     print(f"  > Pulando edital '{nome_pasta}' (não está na lista de teste).")
    #     return None, None

    # --- CAMINHOS DE SAÍDA ---
    caminho_txt = pasta_path / "PDF.txt"
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

    # --- ETAPA 1: EXTRAIR TEXTO DO PDF PRINCIPAL (OCR) ---
    print(f"  [ETAPA 1/4] Extraindo texto do PDF principal...")
    if not caminho_txt.exists():
        # Nova lógica: descompacta e extrai texto de TODOS os PDFs
        texto_extraido = descompactar_e_coletar_texto_pdfs(pasta_path)
        if texto_extraido:
            caminho_txt.write_text(texto_extraido, encoding="utf-8")
            print(f"    > Texto combinado de todos os PDFs salvo em: {caminho_txt.name}")
        else:
            print(f"    > AVISO: Não foi possível extrair texto de nenhum PDF na pasta.")
    else:
        print(f"    > Arquivo PDF.txt já existe. Pulando OCR.")

    # --- ETAPA 2: EXTRAÇÃO DE ITENS (ESTRATÉGIA MÚLTIPLA) ---
    print(f"  [ETAPA 2/4] Extraindo itens...")
    df_itens = pd.DataFrame()
    texto_pdf_bruto = caminho_txt.read_text(encoding="utf-8") if caminho_txt.exists() else ""

    if caminho_xlsx_itens.exists():
        print(f"    > Arquivo de itens ({caminho_xlsx_itens.name}) já existe. Carregando...")
        df_itens = pd.read_excel(caminho_xlsx_itens)
    else:
        # ESTRATÉGIA 1 (PRIORITÁRIA): Se 'RelacaoItens.pdf' existe, usar Regex (mais rápido e preciso para este arquivo)
        pdfs_relacao = list(pasta_path.glob("RelacaoItens*.pdf"))
        if pdfs_relacao:
            print("    > Estratégia prioritária: Encontrado 'RelacaoItens.pdf'. Usando extração por Regex.")
            itens_encontrados = []
            for pdf in pdfs_relacao:
                itens_encontrados.extend(processar_pdf_relacao_itens(pdf))
            if itens_encontrados:
                df_itens = pd.DataFrame(itens_encontrados)
        else:
            # ESTRATÉGIA 2 (FALLBACK 1): Tentar Regex genérica no texto completo
            if texto_pdf_bruto:
                itens_genericos = extrair_itens_tabela_generica(texto_pdf_bruto)
                if itens_genericos:
                    df_itens = pd.DataFrame(itens_genericos)

            # ESTRATÉGIA 3 (FALLBACK 2): Se Regex genérica falhar, usar ML (NER)
            if df_itens.empty:
                print("    > Regex falhou. Usando fallback para ML (NER).")
            if EXTRACTOR_ML.is_ready() and texto_pdf_bruto:
                itens_ml = EXTRACTOR_ML.extract_items_from_text(texto_pdf_bruto)
                if itens_ml:
                    df_itens = pd.DataFrame(itens_ml)


        # Se alguma estratégia funcionou, salvar o resultado intermediário
        if not df_itens.empty:
            df_itens["ARQUIVO"] = nome_pasta
            df_itens = tratar_dataframe(df_itens)
            df_itens.to_excel(caminho_xlsx_itens, index=False)
            print(f"    > {len(df_itens)} itens extraídos e salvos em: {caminho_xlsx_itens.name}")
        else:
            print("    > AVISO: Nenhuma estratégia de extração inicial (ML ou Regex) funcionou.")

    # --- ETAPA 3 & 4: PROCESSAMENTO COM IA (FALLBACK E ENRIQUECIMENTO) ---
    if not texto_pdf_bruto:
        print("  > AVISO: Sem texto do PDF principal, não é possível usar a IA. Finalizando esta pasta.")
        if not df_itens.empty:
             df_itens.to_excel(caminho_final_xlsx, index=False) # Salva o que tem
        return df_itens, None

    df_final = pd.DataFrame()

    # CASO 1: Itens foram extraídos -> Apenas enriquecer com IA
    if not df_itens.empty:
        print(f"  [ETAPA 3/4] Itens encontrados. Enriquecendo com IA...")
        prompt = construir_prompt_referencia(df_itens, texto_pdf_bruto)
        resposta_llm = gerar_conteudo_com_fallback(prompt, LLM_MODELS_FALLBACK)
        if resposta_llm:
            try:
                df_referencia = pd.read_csv(StringIO(resposta_llm.replace("`", "")), sep="<--|-->", engine="python")
                df_referencia.rename(columns=lambda x: x.strip(), inplace=True)
                
                key_col = 'Nº'
                df_itens[key_col] = df_itens[key_col].astype(str)
                if key_col in df_referencia.columns:
                    df_referencia[key_col] = df_referencia[key_col].astype(str)
                    df_final = pd.merge(df_itens, df_referencia, on=key_col, how='left')
                else:
                    df_final = df_itens.copy()
                    df_final['REFERENCIA'] = "IA FALHOU EM RETORNAR Nº"
                print("    > Itens enriquecidos pela IA.")
            except Exception as e:
                print(f"    > FALHA ao processar resposta da IA para enriquecimento: {e}")
                df_final = df_itens.copy()
                df_final['REFERENCIA'] = f"ERRO IA: {e}"
        else:
            df_final = df_itens.copy()
            df_final['REFERENCIA'] = "IA NÃO RESPONDEU"

    # CASO 2: Nenhum item foi extraído -> Usar IA como FALLBACK para extrair do zero
    else:
        print(f"  [ETAPA 3/4] Nenhum item encontrado. Usando IA como fallback para EXTRAIR do zero...")
        prompt = construir_prompt_extracao_itens(texto_pdf_bruto)
        resposta_llm = gerar_conteudo_com_fallback(prompt, LLM_MODELS_FALLBACK)
        if resposta_llm:
            try:
                df_final = pd.read_csv(StringIO(resposta_llm.replace("`", "")), sep="<--|-->", engine="python")
                df_final.rename(columns=lambda x: x.strip(), inplace=True)
                df_final["ARQUIVO"] = nome_pasta
                # Preencher colunas ausentes
                for col in ['DESCRICAO', 'QTDE', 'VALOR_UNIT', 'VALOR_TOTAL', 'UNID_FORN', 'LOCAL_ENTREGA']:
                    if col not in df_final.columns:
                        df_final[col] = ''
                print("    > Itens extraídos do zero pela IA.")
            except Exception as e:
                print(f"    > FALHA ao processar resposta da IA para extração: {e}")
        else:
            print("    > FALHA: IA não respondeu para extração.")

    # --- ETAPA FINAL: SALVAR RESULTADO ---
    print(f"  [ETAPA 4/4] Finalizando e salvando...")
    if not df_final.empty:
        # Reordenar colunas para o padrão
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
    print("INICIANDO O PROCESSO DE EXTRAÇÃO E ANÁLISE DE EDITAIS (V4)")
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

        df_filtrado.to_excel(FINAL_MASTER_PATH, index=False)
        print(f"✅ Arquivo 'master.xlsx' criado com {len(df_filtrado)} itens relevantes.")

        # --- LOG DE PASTAS SEM ITENS NO MASTER FINAL ---
        nomes_pastas_processadas = {p.name for p in pastas_de_editais}
        if 'ARQUIVO' in df_filtrado.columns:
            nomes_pastas_no_master = set(df_filtrado['ARQUIVO'].unique())
            pastas_sem_itens = nomes_pastas_processadas - nomes_pastas_no_master
            
            if pastas_sem_itens:
                print("\n--- ⚠️ LOG: Pastas Processadas Sem Itens no Master Final ---")
                for pasta_sem_item in sorted(list(pastas_sem_itens)):
                    print(f"  > {pasta_sem_item}")
                print("----------------------------------------------------------")
        else:
            print("\n--- ⚠️ LOG: Não foi possível verificar as pastas sem itens (coluna 'ARQUIVO' ausente). ---")
    else:
        print("🔴 Nenhum item final foi processado para gerar o 'master.xlsx'.")

    print("\n--- Limpando arquivos intermediários ---")
    for pasta in pastas_de_editais:
        caminho_itens_xlsx = pasta / f"{pasta.name}_itens.xlsx"
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
