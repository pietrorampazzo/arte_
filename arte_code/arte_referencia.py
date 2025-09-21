
import os
import re
from pathlib import Path
from io import StringIO

import pandas as pd
import fitz  # PyMuPDF
from pdf2image import convert_from_path
import pytesseract
import google.generativeai as genai
from dotenv import load_dotenv

# =====================================================================================
# 1. CONFIGURAÇÕES E CONSTANTES
# =====================================================================================

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# --- Configurações de Caminhos ---
BASE_DIR = Path(r"c:\Users\pietr\OneDrive\.vscode\arte_")
PASTA_EDITAIS = BASE_DIR / "EDITAIS"
SUMMARY_EXCEL_PATH = PASTA_EDITAIS / "summary.xlsx"
FINAL_MASTER_PATH = PASTA_EDITAIS / "master.xlsx"

# --- Configurações de Ferramentas Externas ---
POPLER_PATH = BASE_DIR / "scripts" / "Release-25.07.0-0" / "poppler-25.07.0" / "Library" / "bin"
TESSERACT_CMD = BASE_DIR / "scripts" / "Tesseract-OCR" / "tesseract.exe"
pytesseract.pytesseract.tesseract_cmd = str(TESSERACT_CMD)

# --- Configuração da API Generativa ---
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    print("ERRO: A variável de ambiente GOOGLE_API_KEY não foi definida.")
else:
    genai.configure(api_key=API_KEY)
    MODEL = genai.GenerativeModel(model_name='gemini-2.0-flash-lite')

# --- Configurações de Filtro ---
PALAVRAS_CHAVE = [
    'Instrumento Musical - Sopro', 'Instrumento Musical - Corda', 'Instrumento Musical - Percursão',
    'Instrumento Musical', 'Peças e acessórios instrumento musical', 'Cabo Rede Computador',
    'saxofone', 'trompete', 'tuba', 'clarinete', 'óleo lubrificante', 'trompa', 'sax', 'óleos para válvulas',
    'violão', 'Guitarra', 'Baixo', 'Violino', 'Viola', 'Cavaquinho', 'Bandolim', 'Ukulele',
    'Microfone', 'Microfone direcional', 'Suporte microfone', 'Microfone Dinâmico', 'Microfone de Lapela',
    'Base microfone', 'Pedestal microfone', 'Medusa para microfone', 'Pré-amplificador microfone',
    'Caixa Acústica', 'Caixa de Som', 'Caixa som', 'Subwoofer', 'tarol', 'Estante - partitura',
    'Amplificador de áudio', 'Amplificador som', 'Amplificador fone ouvido',
    'Piano', 'Suporte para teclado', 'Mesa áudio', 'Interface de Áudio',
    'Pedestal', 'Pedestal caixa acústica', 'Pedal Efeito', 'fone de ouvido', 'headset',
    'Bateria Eletrônica', 'Cabo extensor', 'Tela projeção', 'Projetor Multimídia',
]
REGEX_FILTRO = re.compile('|'.join(PALAVRAS_CHAVE), re.IGNORECASE)


# =====================================================================================
# 2. FUNÇÕES DE EXTRAÇÃO E PROCESSAMENTO (AGRUPADAS POR ETAPA)
# =====================================================================================

# -------------------------------------------------------------------------------------
# ETAPA 1: Extração de Texto Bruto do PDF Principal (OCR)
# -------------------------------------------------------------------------------------

def extrair_texto_pdf_ocr(pdf_path):
    """Extrai texto de um arquivo PDF usando OCR com Tesseract."""
    try:
        paginas = convert_from_path(pdf_path, dpi=300, poppler_path=POPLER_PATH)
        texto_completo = ""
        for i, pagina in enumerate(paginas):
            print(f"    > Lendo página {i+1}/{len(paginas)} (OCR)...")
            texto = pytesseract.image_to_string(pagina, lang="por")
            texto_completo += texto + "\n\n"
        return texto_completo
    except Exception as e:
        print(f"    > ERRO ao processar o PDF com OCR {pdf_path}: {e}")
        return ""

# -------------------------------------------------------------------------------------
# ETAPA 2: Extração de Itens Estruturados do PDF "Relação de Itens"
# -------------------------------------------------------------------------------------

def extrair_itens_pdf_texto(text):
    """Extrai itens estruturados do texto de um PDF 'Relação de Itens'."""
    items = []
    # Normalização básica do texto
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r'\s+', ' ', text)

    # Padrão para encontrar cada item e sua descrição
    item_pattern = re.compile(r'(\d+)\s*-\s*([^0-9]+?)(?=Descrição Detalhada:)', re.DOTALL | re.IGNORECASE)
    item_matches = list(item_pattern.finditer(text))

    for i, match in enumerate(item_matches):
        item_num = match.group(1).strip()
        item_nome = match.group(2).strip()
        start_pos = match.start()
        end_pos = item_matches[i + 1].start() if i + 1 < len(item_matches) else len(text)
        item_text = text[start_pos:end_pos]

        # Extração de campos específicos dentro do bloco do item
        descricao_match = re.search(r'Descrição Detalhada:\s*(.*?)(?=Tratamento Diferenciado:)|Aplicabilidade Decreto|$\s*', item_text, re.DOTALL | re.IGNORECASE)
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

def tratar_dataframe(df):
    """Aplica tratamento e padronização em um DataFrame de itens."""
    if df.empty:
        return df
    df['QTDE'] = pd.to_numeric(df['QTDE'], errors='coerce').fillna(0)
    for col in ['VALOR_UNIT', 'VALOR_TOTAL']:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False), errors='coerce').fillna(0)
    
    mask = (df['VALOR_UNIT'] == 0) & (df['VALOR_TOTAL'] > 0) & (df['QTDE'] > 0)
    df.loc[mask, 'VALOR_UNIT'] = df.loc[mask, 'VALOR_TOTAL'] / df.loc[mask, 'QTDE']
    df['VALOR_TOTAL'] = df['QTDE'] * df['VALOR_UNIT']
    
    for col in ['VALOR_UNIT', 'VALOR_TOTAL']:
        df[col] = df[col].apply(lambda x: f"{x:.2f}".replace(".", ","))
    return df

# -------------------------------------------------------------------------------------
# ETAPA 3: Enriquecimento com IA (Gemini)
# -------------------------------------------------------------------------------------

def chamar_llm(prompt):
    """Envia um prompt para o modelo Gemini e retorna a resposta."""
    if "API_KEY" not in globals() or not API_KEY:
        print("    > ERRO: API Key do Google não configurada. Pulando chamada da LLM.")
        return None
    try:
        print("    > Comunicando com a IA para extrair referências...")
        response = MODEL.generate_content(prompt)
        print("    > IA respondeu.")
        return response.text
    except Exception as e:
        print(f"    > ERRO na chamada da LLM: {e}")
        return None

def construir_prompt_referencia(df, texto_pdf):
    """Constrói o prompt para o modelo de linguagem."""
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
    3<--|-->Outra descrição.

    IMPORTANTE: Use '<--|-->' como separador. Não inclua nenhuma explicação ou formatação extra.
    """

# =====================================================================================
# 3. ORQUESTRADOR PRINCIPAL
# =====================================================================================

def processar_pasta_edital(pasta_path):
    """
    Orquestra o pipeline completo para uma única pasta de edital.
    Etapa 1: Extrai texto do PDF principal.
    Etapa 2: Extrai itens da Relação de Itens.
    Etapa 3: Enriquece os dados com IA.
    """
    nome_pasta = pasta_path.name
    print(f"\n--- Processando Edital: {nome_pasta} ---")

    # --- ETAPA 1: Extrair texto do PDF principal ---
    pdf_principal_encontrado = None
    for arquivo in pasta_path.glob("*.pdf"):
        if not arquivo.name.lower().startswith("relacaoitens"):
            pdf_principal_encontrado = arquivo
            break
    
    caminho_txt = pasta_path / "PDF.txt"
    if pdf_principal_encontrado:
        print(f"  [ETAPA 1/3] Extraindo texto do PDF principal: {pdf_principal_encontrado.name}")
        texto_extraido = extrair_texto_pdf_ocr(pdf_principal_encontrado)
        if texto_extraido:
            with open(caminho_txt, "w", encoding="utf-8") as f:
                f.write(texto_extraido)
            print(f"    > Texto extraído salvo em: {caminho_txt.name}")
        else:
            print(f"    > AVISO: Não foi possível extrair texto do PDF principal.")
    else:
        print(f"  [ETAPA 1/3] AVISO: Nenhum PDF principal encontrado na pasta.")

    # --- ETAPA 2: Extrair itens da Relação de Itens ---
    print(f"  [ETAPA 2/3] Extraindo itens da Relação de Itens...")
    caminho_xlsx_itens = pasta_path / f"{nome_pasta}.xlsx"
    itens_encontrados = []
    for pdf_relacao in pasta_path.glob("RelacaoItens*.pdf"):
        itens_encontrados.extend(processar_pdf_relacao_itens(pdf_relacao))
    
    if not itens_encontrados:
        print("    > AVISO: Nenhum item encontrado nos PDFs 'Relação de Itens'. Pulando para o próximo edital.")
        return None, None # Retorna None para indicar que não pode continuar

    df_itens = pd.DataFrame(itens_encontrados)
    df_itens["ARQUIVO"] = nome_pasta
    df_itens = tratar_dataframe(df_itens)
    df_itens.to_excel(caminho_xlsx_itens, index=False)
    print(f"    > Planilha de itens criada: {caminho_xlsx_itens.name} com {len(df_itens)} itens.")

    # --- ETAPA 3: Enriquecer com IA ---
    print(f"  [ETAPA 3/3] Enriquecendo dados com IA...")
    if not caminho_txt.exists():
        print("    > AVISO: Arquivo PDF.txt não encontrado. Não é possível enriquecer os dados.")
        return df_itens, None

    with open(caminho_txt, 'r', encoding='utf-8') as f:
        texto_pdf_bruto = f.read()

    prompt = construir_prompt_referencia(df_itens, texto_pdf_bruto)
    resposta_llm = chamar_llm(prompt)

    if resposta_llm:
        try:
            clean_response = resposta_llm.strip().replace('`', '').replace('csv', '')
            
            lines = clean_response.splitlines()
            
            # Skip empty lines
            lines = [line for line in lines if line.strip()]

            # Get header from the first line, handling potential empty response
            if not lines:
                raise ValueError("A resposta da LLM está vazia.")

            header = lines[0].split('<--|-->')
            
            # Process data lines
            data = []
            for line in lines[1:]:
                parts = line.split('<--|-->', 1)
                if len(parts) == 2:
                    data.append(parts)
                elif len(parts) == 1:
                    # Handle case where there is no delimiter
                    data.append([parts[0], ''])

            df_referencia = pd.DataFrame(data, columns=header)

            key_col = df_itens.columns[0] # 'Nº'
            df_itens[key_col] = df_itens[key_col].astype(str)
            df_referencia[key_col] = df_referencia[key_col].astype(str)
            
            df_merged = pd.merge(df_itens, df_referencia, on=key_col, how='left')
            
            desired_order = ['Nº', 'DESCRICAO', 'REFERENCIA', 'QTDE', 'VALOR_UNIT', 'VALOR_TOTAL', 'UNID_FORN', 'LOCAL_ENTREGA', 'ARQUIVO']
            df_result = df_merged[[col for col in desired_order if col in df_merged.columns]]
            
            output_filename = pasta_path / f"{nome_pasta}_master.xlsx"
            df_result.to_excel(output_filename, index=False)
            print(f"    >✅ SUCESSO! Planilha enriquecida salva como: {output_filename.name}")
            return df_itens, df_result
        except Exception as e:
            print(f"    >❌ FALHA ao processar a resposta da LLM: {e}")
            # Salva a resposta bruta para depuração
            with open(pasta_path / 'resposta_bruta_erro.txt', 'w', encoding='utf-8') as f:
                f.write(resposta_llm)
    else:
        print("    > FALHA: Não foi possível obter resposta da LLM.")

    return df_itens, None


def main():
    """
    Função principal que itera sobre todas as pastas de editais e as processa.
    Ao final, gera os arquivos consolidados 'summary.xlsx' e 'master.xlsx'.
    """
    print("="*80)
    print("INICIANDO O PROCESSO DE EXTRAÇÃO E ANÁLISE DE EDITAIS")
    print("="*80)

    if not PASTA_EDITAIS.is_dir():
        print(f"ERRO CRÍTICO: O diretório de editais '{PASTA_EDITAIS}' não foi encontrado.")
        return

    
    todos_os_itens = []
    todos_os_itens_enriquecidos = []

    pastas_de_editais = sorted([d for d in PASTA_EDITAIS.iterdir() if d.is_dir()])
    for i, pasta in enumerate(pastas_de_editais):
        df_itens, df_enriquecido = processar_pasta_edital(pasta)
        if df_itens is not None:
            todos_os_itens.append(df_itens)
        if df_enriquecido is not None:
            todos_os_itens_enriquecidos.append(df_enriquecido)
        print(f"--- Edital {i+1}/{len(pastas_de_editais)} concluído. ---")

    print("\n--- Finalizando e Gerando Arquivos Consolidados ---")

    # Gerar summary.xlsx com todos os itens extraídos
    if todos_os_itens:
        df_summary = pd.concat(todos_os_itens, ignore_index=True)
        df_summary = tratar_dataframe(df_summary) # Garante a formatação final
        df_summary.to_excel(SUMMARY_EXCEL_PATH, index=False)
        print(f"✅ Arquivo 'summary.xlsx' criado com {len(df_summary)} itens totais.")
    else:
        print("🟡 Nenhum item foi extraído para gerar o 'summary.xlsx'.")

    # Gerar master.xlsx com itens filtrados por palavras-chave
    if todos_os_itens_enriquecidos:
        df_master = pd.concat(todos_os_itens_enriquecidos, ignore_index=True)
        mask = df_master['DESCRICAO'].apply(lambda x: bool(REGEX_FILTRO.search(str(x))))
        df_filtrado = df_master[mask].copy()
        df_filtrado.to_excel(FINAL_MASTER_PATH, index=False)
        print(f"✅ Arquivo 'master.xlsx' criado com {len(df_filtrado)} itens relevantes.")
    elif todos_os_itens: # Fallback se o enriquecimento falhou
        print("🟡 O enriquecimento com IA falhou ou não produziu resultados. Gerando 'master.xlsx' com dados não enriquecidos.")
        df_summary = pd.concat(todos_os_itens, ignore_index=True)
        mask = df_summary['DESCRICAO'].apply(lambda x: bool(REGEX_FILTRO.search(str(x))))
        df_filtrado = df_summary[mask].copy()
        df_filtrado.to_excel(FINAL_MASTER_PATH, index=False)
        print(f"✅ Arquivo 'master.xlsx' criado com {len(df_filtrado)} itens relevantes (não enriquecidos).")
    else:
        print("🔴 Nenhum item foi extraído para gerar o 'master.xlsx'.")

    print("="*80)
    print("PROCESSO CONCLUÍDO!")
    print("="*80)


if __name__ == "__main__":
    main()
