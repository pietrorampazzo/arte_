
import os
import re
from pathlib import Path
import shutil
from io import StringIO
import time
import pandas as pd
import fitz  # PyMuPDF
import zipfile
import rarfile
from pdf2image import convert_from_path
import pytesseract
import google.generativeai as genai
from dotenv import load_dotenv
from datetime import datetime

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

    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    
]

# --- Configuração da API Generativa ---
API_KEY = os.getenv("GOOGLE_API_PAGO")
if not API_KEY:
    print("ERRO: A variável de ambiente GOOGLE_API_KEY não foi definida.")
else:
    genai.configure(api_key=API_KEY)
    # A inicialização do modelo será feita dentro da função de chamada
    # para permitir o fallback entre diferentes modelos.
    # MODEL = genai.GenerativeModel(model_name='gemini-1.5-pro')

# --- Configurações de Filtro ---
PALAVRAS_CHAVE = [

    # ------------------ Categorias principais ------------------
    r'Instrumento Musical',r'Instrumento Musical - Sopro',r'Instrumento Musical - Corda',r'Instrumento Musical - Percussão',
    r'Peças e acessórios instrumento musical',    r'Peças E Acessórios Instrumento Musical',

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
REGEX_EXCLUIR = re.compile('|'.join(PALAVRAS_EXCLUIR), re.IGNORECASE)

# --- Configurações de Exceção ao Filtro ---
PALAVRAS_EXCECAO = [
    r'drone', r'DRONE', r'Aeronave',
]
REGEX_EXCECAO = re.compile('|'.join(PALAVRAS_EXCECAO), re.IGNORECASE)



# =====================================================================================
# 2. FUNÇÕES DE EXTRAÇÃO E PROCESSAMENTO
# =====================================================================================

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
        return ""

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

        valor_unitario_match = re.search(r'Valor Unitário[^:]*:\s*R?\$?s*([\d.,]+)', item_text, re.IGNORECASE)
        valor_unitario = valor_unitario_match.group(1) if valor_unitario_match else ""

        valor_total_match = re.search(r'Valor Total[^:]*:\s*R?\$?s*([\d.,]+)', item_text, re.IGNORECASE)
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

def gerar_conteudo_com_fallback(prompt: str, modelos: list[str]):

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
                # Log do prompt que causou a falha para análise posterior
                if finish_reason == 'SAFETY':
                    log_path = PROJECT_ROOT / "logs"
                    log_path.mkdir(exist_ok=True)
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    (log_path / f"safety_failure_{timestamp}.txt").write_text(prompt, encoding="utf-8")
                    print(f"      - ℹ️ O prompt que causou a falha de segurança foi salvo em /logs/ para análise.")
                continue
            print(f"    > ✅ IA respondeu com sucesso usando o modelo '{nome_modelo}'.")
            return response.text
        except Exception as e:
            # Importar a exceção específica se quiser tratá-la separadamente
            print(f"    > ⚠️ Erro com o modelo '{nome_modelo}': {e}. Tentando o próximo da lista.")
            continue
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
    Sua tarefa é analisar o texto de um edital de licitação e extrair TODOS os itens que estão sendo licitados, incluindo número, descrição, quantidade e valor unitário.

    O texto do edital é:
    {texto_pdf}

    Para cada item encontrado, extraia as seguintes informações:
    - Nº: O número do item.
    - DESCRICAO: A descrição completa e detalhada do item.
    - QTDE: A quantidade total do item.
    - VALOR_UNIT: O valor unitário estimado ou de referência do item.

    Retorne o resultado usando a sequência '<--|-->' como separador. NÃO use aspas ou markdown.
    A saída deve ter exatamente 4 colunas: 'Nº', 'DESCRICAO', 'QTDE', 'VALOR_UNIT'.

    O formato de saída DEVE ser:
    Nº<--|-->DESCRICAO<--|-->QTDE<--|-->VALOR_UNIT
    1<--|-->Descrição detalhada do item 1.<--|-->10<--|-->150,50
    2<--|-->Descrição detalhada do item 2, que pode ter vírgulas.<--|-->5<--|-->2300,00

    IMPORTANTE: Use '<--|-->' como separador. Se uma informação não for encontrada, deixe o campo vazio, mas mantenha os separadores.
    Exemplo com campo vazio: 3<--|-->Descrição item 3<--|--><--|-->50,00
    Liste todos os itens que encontrar.
    """

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
    print(f"  [ETAPA 1/5] Verificando e descompactando arquivos recursivamente...")
    descompactar_e_organizar_recursivamente(pasta_path)

    # --- ETAPA 2: EXTRAIR TEXTO DE TODOS OS PDFs PARA O 'razao.txt' ---
    print(f"  [ETAPA 2/5] Extraindo texto de todos os PDFs para 'razao.txt'...")
    if not caminho_razao_txt.exists():
        # Exclui os PDFs de 'RelacaoItens' da extração de contexto para a LLM.
        pdfs_na_pasta = [p for p in pasta_path.glob("*.pdf") if not p.name.lower().startswith("relacaoitens")]
        texto_completo_extraido = ""
        if pdfs_na_pasta:
            for pdf in pdfs_na_pasta:
                texto_completo_extraido += extrair_texto_de_pdf(pdf) + "\n\n"
            caminho_razao_txt.write_text(texto_completo_extraido, encoding="utf-8")
            print(f"    > Texto de contexto salvo em: {caminho_razao_txt.name}")
    else:
        print(f"    > Arquivo de contexto '{caminho_razao_txt.name}' já existe. Pulando extração.")

    # --- ETAPA 3: EXTRAIR ITENS DE ARQUIVOS ESTRUTURADOS (PDF/XLSX) ---
    print(f"  [ETAPA 3/5] Extraindo itens de 'RelacaoItens.pdf' ou planilhas .xlsx...")
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

    # --- ETAPA 4 & 5: PROCESSAMENTO COM IA (FALLBACK E ENRIQUECIMENTO) ---
    texto_pdf_bruto = caminho_razao_txt.read_text(encoding="utf-8") if caminho_razao_txt.exists() else ""
    if not texto_pdf_bruto:
        print("  > AVISO: Sem texto do PDF principal, não é possível usar a IA. Finalizando esta pasta.")
        if not df_itens.empty:
             df_itens.to_excel(caminho_final_xlsx, index=False) # Salva o que tem
        return df_itens, None
    
    df_final = pd.DataFrame()

    # CASO 1: Itens foram extraídos do RelacaoItens.pdf -> Apenas enriquecer com IA
    if not df_itens.empty:
        print(f"  [ETAPA 4/5] Itens encontrados. Enriquecendo com IA usando contexto otimizado...")
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

    # CASO 2: Nenhum item foi extraído do RelacaoItens.pdf -> Usar IA como FALLBACK para extrair do zero a partir do razao.txt
    else:
        print(f"  [ETAPA 4/5] Nenhum item encontrado. Usando IA como fallback para EXTRAIR do zero...")
        prompt = construir_prompt_extracao_itens(texto_pdf_bruto)
        resposta_llm = gerar_conteudo_com_fallback(prompt, LLM_MODELS_FALLBACK)
        if resposta_llm:
            try:
                df_final = pd.read_csv(StringIO(resposta_llm.replace("`", "")), sep="<--|-->", engine="python", on_bad_lines='warn')
                df_final.rename(columns=lambda x: x.strip(), inplace=True)
                df_final["ARQUIVO"] = nome_pasta
                # A LLM agora deve retornar DESCRICAO, QTDE, VALOR_UNIT. REFERENCIA será preenchida com a própria descrição.
                if 'DESCRICAO' in df_final.columns:
                    df_final['REFERENCIA'] = df_final['DESCRICAO']
                # Preencher colunas ausentes
                for col in ['VALOR_TOTAL', 'UNID_FORN', 'LOCAL_ENTREGA']:
                    if col not in df_final.columns:
                        df_final[col] = ''
                print("    > Itens extraídos do zero pela IA.")
            except Exception as e:
                print(f"    > FALHA ao processar resposta da IA para extração: {e}")
        else:
            print("    > FALHA: IA não respondeu para extração.")

    # --- ETAPA FINAL: SALVAR RESULTADO ---
    print(f"  [ETAPA 5/5] Finalizando e salvando...")
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
