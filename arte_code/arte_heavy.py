import pandas as pd
import google.generativeai as genai
import google.api_core.exceptions as google_exceptions
import os
from dotenv import load_dotenv
import json
import time
import logging
from openpyxl.styles import PatternFill
import re
from datetime import datetime
import colorsys
# ======================================================================
# CONFIGURAÇÕES E CONSTANTES
# ======================================================================

# --- File Paths ---
BASE_DIR = r"C:\Users\pietr\OneDrive\.vscode\arte_"
CAMINHO_EDITAL = os.path.join(BASE_DIR, "DOWNLOADS", "master.xlsx")
CAMINHO_BASE = os.path.join(BASE_DIR, "DOWNLOADS", "RESULTADO_metadados", "categoria_GPT.xlsx")
CAMINHO_SAIDA = os.path.join(BASE_DIR, "DOWNLOADS", "master_heavy.xlsx")
CAMINHO_HEAVY_EXISTENTE = CAMINHO_SAIDA
# --- Financial Parameters ---
PROFIT_MARGIN = 0.53  # MARGEM DE LUCRO 
INITIAL_PRICE_FILTER_PERCENTAGE = 0.60  # FILTRO DE PREÇO DOS PRODUTOS NA BASE

# --- AI Model Configuration ---
LLM_MODELS_FALLBACK = [

    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.5-pro",
    "gemini-1.5-flash",  
]

# --- Categorization Keywords ------------------------------------
CATEGORIZATION_KEYWORDS = {
        "EQUIPAMENTO_SOM" : ["caixa_ativa", "caixa_passiva", "caixa_portatil", "line_array", "subwoofer_ativo", "subwoofer_passivo", "amplificador_potencia", "cabeçote_amplificado", "coluna_vertical", "monitor_de_palco"],

        "EQUIPAMENTO_AUDIO" : ["microfone_dinamico", "microfone_condensador", "microfone_lapela", "microfone_sem_fio", "microfone_instrumento", "mesa_analogica", "mesa_digital", "interface_audio", "processador_dsp", "fone_monitor", "sistema_iem", "pedal_efeitos"],

        "INSTRUMENTO_CORDA" : ["violao", "guitarra", "contra_baixo", "violino", "violoncelo", "ukulele", "cavaquinho"],

        "INSTRUMENTO_PERCUSSAO" : ["bateria_acustica", "repinique", "rocari", "tantan", "rebolo","surdo_mao", "cuica", "zabumba", "caixa_guerra", "bombo_fanfarra", "lira_marcha","tarol", "malacacheta", "caixa_bateria", "pandeiro", "tamborim","reco_reco", "agogô", "triangulo", "chocalho", "afuche", "cajon", "bongo", "conga", "djembé", "timbal", "atabaque", "berimbau","tam_tam", "caxixi", "carilhao", "xequerê", "prato"],

        "INSTRUMENTO_SOPRO" : ["saxofone", "trompete", "trombone", "trompa", "clarinete", "flauta", "tuba", "flugelhorn", "bombardino", "corneta", "cornetão"],

        "INSTRUMENTO_TECLADO" : ["teclado_digital", "piano_acustico", "piano_digital", "sintetizador", "controlador_midi", "glockenspiel", "metalofone"],

        "ACESSORIO_MUSICAL" : ["banco_teclado", "estante_partitura", "suporte_microfone", "suporte_instrumento", "carrinho_transporte", "case_bag", "afinador", "metronomo", "cabos_audio", "palheta", "cordas", "oleo_lubrificante", "graxa", "surdina", "bocal_trompete", "pele_percussao", "baqueta", "talabarte", "pedal_bumbo", "chimbal_hihat"],

        "EQUIPAMENTO_TECNICO" : ["ssd", "fonte_energia", "switch_rede", "projetor", "drone"]
}

# --- Logging Configuration ---
LOG_FILE = os.path.join(BASE_DIR, "LOGS", "arte_heavy.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def load_categorized_products(file_path):
    """Carrega produtos categorizados de uma planilha Excel."""
    try:
        df = pd.read_excel(file_path)
        return df.set_index('ID_PRODUTO')[['categoria_principal', 'subcategoria']].to_dict('index')
    except FileNotFoundError:
        print(f"ERROR: Could not load categorized products file: {file_path}")
        return {}

# ============================================================ 
# FUNÇÕES DE SUPORTE
# ============================================================ 

def gerar_conteudo_com_fallback(prompt: str, modelos: list[str]) -> str | None:
    """
    Tenta gerar conteúdo usando uma lista de modelos em ordem de preferência.
    Se um modelo falhar por cota (ResourceExhausted), tenta o próximo.
    """
    for nome_modelo in modelos:
        try:
            print(f"   - Tentando chamada à API com o modelo: {nome_modelo}...")
            model = genai.GenerativeModel(nome_modelo)
            response = model.generate_content(prompt)

            if not response.parts:
                finish_reason = response.candidates[0].finish_reason.name if response.candidates else 'N/A'
                print(f"   - ❌ A GERAÇÃO RETORNOU VAZIA. Motivo: {finish_reason}. Isso pode ser causado por filtros de segurança.")
                return None
            print(f"   - Sucesso com o modelo '{nome_modelo}'.")
            return response.text
        except google_exceptions.ResourceExhausted as e:
            print(f"- Cota excedida para o modelo '{nome_modelo}'. Tentando o próximo da lista.")
            time.sleep(5)
            continue
        except Exception as e:
            print(f"   - ❌ Erro inesperado com o modelo '{nome_modelo}': {e}")
            return None
    print("   - ❌ FALHA TOTAL: Todos os modelos na lista de fallback falharam.")
    return None

def get_item_classification(description: str, reference: str, categories_with_subcategories: dict) -> dict | None:
    """Usa o modelo de IA para classificar o item, retornando categoria e subcategoria."""
    print("- Asking AI for item classification (category and subcategory)...")

    prompt = f"""<identidade>Você é um especialista de almoxarifado e perito em catalogação de produtos, com base nessas informações.</identidade>

<objetivo>
Sua tarefa é classificar o item a seguir, identificando sua `categoria_principal` e `subcategoria` com base na estrutura fornecida.
- A `categoria_principal` DEVE ser uma das chaves da estrutura abaixo.
- A `subcategoria` DEVE ser um dos valores da lista associada à categoria principal escolhida.
Responda APENAS com um objeto JSON.
</objetivo>

<item_a_ser_classificado>
Descrição: {description}
Referência: {reference}
</item_a_ser_classificado>

<estrutura_de_categorias_e_subcategorias_permitidas>
{json.dumps(categories_with_subcategories, indent=2, ensure_ascii=False)}
</estrutura_de_categorias_e_subcategorias_permitidas>

<formato_saida>
{{
  "categoria_principal": "NOME_DA_CATEGORIA_PRINCIPAL",
  "subcategoria": "NOME_DA_SUBCATEGORIA_ESPECIFICA"
}}
</formato_saida>

JSON:
"""

    response_text = gerar_conteudo_com_fallback(prompt, LLM_MODELS_FALLBACK)
    if response_text:
        try:
            cleaned_response = response_text.strip().replace("```json", "").replace("```", "")
            classification = json.loads(cleaned_response)
            
            if 'categoria_principal' in classification and 'subcategoria' in classification:
                if classification['categoria_principal'] in categories_with_subcategories:
                    return classification
                else:
                    print(f"   - WARNING: AI returned an invalid main category: '{classification['categoria_principal']}'.")
                    return None
            else:
                print("   - WARNING: AI response is missing required keys ('categoria_principal', 'subcategoria').")
                return None

        except json.JSONDecodeError as e:
            print(f"   - ERROR decoding JSON from AI for classification: {e}")
            return None
    else:
        print("   - ERROR: AI call for classification failed for all models.")
        return None


def get_best_match_from_ai(item_edital, df_candidates):
    """Usa o modelo de IA para encontrar o melhor match dentro dos candidatos."""
    print(" - Asking AI for the best match...")

    candidates_json = df_candidates[['DESCRICAO','categoria_principal','subcategoria','MARCA','MODELO','VALOR']] \
                        .to_json(orient="records", force_ascii=False, indent=2)

    prompt = f"""<identidade>Você é um consultor de licitações com 20+ anos de experiência em áudio/instrumentos, focado na Lei 14.133/21, economicidade e menor preço.</identidade>
<objetivo>
1. Analise tecnicamente o item do edital: Descrição: "{item_edital['DESCRICAO']}" Referência: "{item_edital.get('REFERENCIA', 'N/A')}"
2. Compare-o com cada produto na <base_fornecedores_filtrada>.
3. **Seleção Primária**: Encontre o produto da base que seja >=95% compatível. Dentre os compatíveis, escolha o de **menor 'Valor'**.
4. **Seleção Secundária**: Se nenhum produto for >=95% compatível, identifique o produto tecnicamente mais próximo e detalhe as especificações que não foram atendidas.
5. Use o Google para pesquisar e confirmar as especificações técnicas dos produtos candidatos para garantir uma análise precisa.
6. Responda **apenas** com um objeto JSON seguindo o <formato_saida>.
</objetivo>

<formato_saida>
Responda APENAS com um único objeto JSON. Não inclua ```json, explicações ou qualquer outro texto.
**CASO 1: Encontrou um produto >=95% compatível.**
{{
  "best_match": {{
    "Marca": "Marca do Produto",
    "Modelo": "Modelo do Produto",
    "Valor": 1234.56,
    "Descricao_fornecedor": "Descrição completa do produto na base",
    "Compatibilidade_analise": "Análise quantitativa da compatibilidade. Ex: 'Compatível. Atende a 5 de 6 especificações chave.'"
  }}
}}

**CASO 2: NENHUM produto é >=95% compatível.**
Retorne "best_match" como `null`. Adicionalmente, inclua "closest_match" com os dados do produto mais próximo e "reasoning" explicando o motivo da incompatibilidade.
{{
  "best_match": null,
  "reasoning": "Explique o principal motivo da incompatibilidade. Ex: 'Nenhum produto atende à especificação de material X ou potência Y.'",
  "closest_match": {{
    "Marca": "Marca do Produto Mais Próximo",
    "Modelo": "Modelo do Mais Próximo",
    "Valor": 4321.98,
    "Descricao_fornecedor": "Descrição do produto mais próximo.",
    "Compatibilidade_analise": "Análise da compatibilidade parcial com detalhes. Ex: 'Atende [especificação A, B], mas falha em [especificação C (material), D (potência)].'"
  }}
}}
</formato_saida><base_fornecedores_filtrada>{candidates_json}</base_fornecedores_filtrada>"""

    response_text = gerar_conteudo_com_fallback(prompt, LLM_MODELS_FALLBACK)
    if response_text:
        MAX_RETRIES = 3
        for attempt in range(MAX_RETRIES):
            try:
                cleaned_response = response_text.strip().replace("```json", "").replace("```", "")
                return json.loads(cleaned_response)
            except json.JSONDecodeError as e:
                print(f"   - ERROR decoding JSON from AI (Attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES - 1:
                    print("   - Retrying in 10 seconds...")
                    time.sleep(10)
                else:
                    print("   - Max retries reached. Returning error.")
                    return { "best_match": None, "closest_match": None, "reasoning": f"Erro na decodificação do JSON da API após {MAX_RETRIES} tentativas: {e}"}
    else:
        return { "best_match": None, "closest_match": None, "reasoning": "Falha na chamada da API para todos os modelos de fallback."}

def calculate_compatibility_score(analise: str, edital_subcategory: str | None, product_subcategory: str | None) -> float:
    """
    Calcula a pontuação de compatibilidade com base na SUBCATEGORIA e na análise de especificações.
    - 50% da pontuação vem da correspondência de subcategoria.
    - 50% da pontuação vem da análise de especificações da IA.
    """
    # 1. Calcula a pontuação base pela subcategoria (50%)
    base_score = 0.0
    if edital_subcategory and product_subcategory and edital_subcategory.lower() == product_subcategory.lower():
        base_score = 50.0

    # 2. Calcula o percentual de compatibilidade das especificações (0-100%)
    spec_percentage = 0.0
    if analise and pd.notna(analise):
        # Padrão 1: 'atende a X de Y'
        match_num = re.search(r'atende a (\d+) de (\d+)', analise, re.IGNORECASE)
        if match_num:
            attended, total = map(int, match_num.groups())
            if total > 0:
                spec_percentage = (attended / total) * 100
        else:
            # Padrão 2: 'Atende [...] mas falha em [...]'
            atende_match = re.search(r'atende (?:às seguintes especificações:|à|as seguintes:) (.*?) (?:No entanto|mas falha em|não foram atendidas:)', analise, re.IGNORECASE | re.DOTALL)
            falha_match = re.search(r'(?:falha em|não foram atendidas:|falha nas seguintes:) (.*)', analise, re.IGNORECASE | re.DOTALL)
            
            attended_count = 0
            failed_count = 0
            
            if atende_match:
                atende_text = atende_match.group(1)
                attended_count = len(re.findall(r'[^,;.]+', atende_text.strip()))
            
            if falha_match:
                falha_text = falha_match.group(1)
                failed_count = len(re.findall(r'[^,;.]+', falha_text.strip()))
            
            total = attended_count + failed_count
            if total > 0:
                spec_percentage = (attended_count / total) * 100

    # 3. Combina as pontuações: 50% da base + 50% das especificações
    spec_score_contribution = (spec_percentage / 100.0) * 50.0
    final_score = base_score + spec_score_contribution
    
    return final_score

def get_rainbow_color(score: float) -> PatternFill:
    """
    Gera cor com base no score de compatibilidade:
    - 100%: Verde forte (matching perfeito)
    - 80-99%: Verde claro (matching semi-perfeito)
    - 40-79%: Amarelo (mesma categoria, mas com divergências)
    - 0-39%: Vermelho claro (produtos muito diferentes ou sem correspondência)
    """
    if pd.isna(score):
        score = 0.0

    # Cores base (R, G, B)
    strong_green = (0, 176, 80)   # 00B050
    light_green = (198, 239, 206) # C6EFCE
    yellow = (255, 235, 156)      # FFEB9C
    red = (255, 199, 206)         # FFC7CE

    if score == 100:
        r, g, b = strong_green
    elif score >= 80:
        r, g, b = light_green
    elif score >= 40:
        r, g, b = yellow
    else: # score < 40
        r, g, b = red

    hex_color = f'{r:02X}{g:02X}{b:02X}'
    return PatternFill(start_color=hex_color, end_color=hex_color, fill_type='solid')

# ============================================================ 
# MAIN
# ============================================================ 

def main():
    logger.info("Starting the product matching process...")
    print("Starting the product matching process...")

    load_dotenv()
    api_key = os.getenv("GOOGLE_API_PAGO")
    if not api_key:
        logger.error("GOOGLE_API_KEY not found in .env file.")
        print("ERROR: GOOGLE_API_KEY not found in .env file.")
        return

    genai.configure(api_key=api_key)

    try:
        df_edital = pd.read_excel(CAMINHO_EDITAL)
        df_base = pd.read_excel(CAMINHO_BASE)
        
        # Convert 'VALOR' to numeric, coercing errors
        df_base['VALOR'] = pd.to_numeric(df_base['VALOR'], errors='coerce').fillna(0)

        logger.info(f"Loaded {len(df_edital)} items from {os.path.basename(CAMINHO_EDITAL)} and {len(df_base)} products from {os.path.basename(CAMINHO_BASE)}")
        print(f"👾 Edital loaded: {len(df_edital)} items from {os.path.basename(CAMINHO_EDITAL)}")
        print(f"📯 Product base loaded: {len(df_base)} products from {os.path.basename(CAMINHO_BASE)}")
    except FileNotFoundError as e:
        logger.error(f"Could not load data files. Details: {e}")
        print(f"ERROR: Could not load data files. Details: {e}")
        return

    if os.path.exists(CAMINHO_HEAVY_EXISTENTE):
        logger.info(f"Loading existing processed data from {os.path.basename(CAMINHO_HEAVY_EXISTENTE)}")
        print(f"   - Loading existing data from: {os.path.basename(CAMINHO_HEAVY_EXISTENTE)}")
        df_existing = pd.read_excel(CAMINHO_HEAVY_EXISTENTE)
        existing_keys = set(zip(df_existing['ARQUIVO'].astype(str), df_existing['Nº'].astype(str)))
        logger.info(f"Found {len(existing_keys)} already processed items.")
    else:
        df_existing = pd.DataFrame()
        existing_keys = set()
        logger.info("No existing output file found. Processing all items as new.")

    df_edital_new = df_edital[~df_edital.apply(lambda row: (str(row['ARQUIVO']), str(row['Nº'])) in existing_keys, axis=1)].copy()

    if df_edital_new.empty:
        logger.info("No new items to process. Output file is up to date.")
        print("\n✅ No new items to process. The output file is already up to date.")
        return

    logger.info(f"Identified {len(df_edital_new)} new items to process.")
    print(f"   - Found {len(df_edital_new)} new items to process.")
    total_new_items = len(df_edital_new)

    for idx, item_edital in df_edital_new.iterrows():
        descricao = str(item_edital['DESCRICAO'])
        referencia = str(item_edital.get('REFERENCIA', 'N/A'))
        print(f"\n 📈 Processing new item {idx + 1}/{total_new_items}: {referencia[:60]}...")
        status = ""
        best_match_data = None
        closest_match_data = None
        reasoning = None
        data_to_populate = None
        classification = None

        valor_unit_edital = float(str(item_edital.get('VALOR_UNIT', '0')).replace(',', '.'))

        if valor_unit_edital > 0:
            max_cost = valor_unit_edital * INITIAL_PRICE_FILTER_PERCENTAGE
            df_candidates = df_base[df_base['VALOR'] <= max_cost].copy()
        else:
            print("- Valor de referência do edital é R$0.00 ou inválido. Analisando todos os produtos da base.")
            df_candidates = df_base.copy()

        if df_candidates.empty:
            if valor_unit_edital > 0:
                print(f"- ⚠️ Nenhum produto encontrado abaixo do custo máximo de R${max_cost:.2f}.")
            status = "Nenhum Produto com Margem"
        else:
            classification = get_item_classification(descricao, referencia, CATEGORIZATION_KEYWORDS)
        
        time.sleep(10) 

        df_final_candidates = pd.DataFrame()
        filter_level = "Nenhum"

        if classification:
            main_category = classification.get('categoria_principal')
            subcategory = classification.get('subcategoria')
            print(f"   - AI classified item as: Categoria='{main_category}', Subcategoria='{subcategory}'")

            if subcategory:
                df_filtered_sub = df_candidates[df_candidates['subcategoria'].str.contains(subcategory, case=False, na=False)]
                if not df_filtered_sub.empty:
                    print(f"  - 📦 Found {len(df_filtered_sub)} candidates matching SUBCATEGORY '{subcategory}'.")
                    df_final_candidates = df_filtered_sub
                    filter_level = "Subcategoria"

            if df_final_candidates.empty and main_category:
                print(f"  - ⚠️ No candidates found for subcategory '{subcategory}'. Trying main category...")
                df_filtered_main = df_candidates[df_candidates['categoria_principal'] == main_category]
                if not df_filtered_main.empty:
                    print(f"  - 📦 Found {len(df_filtered_main)} candidates matching MAIN CATEGORY '{main_category}'.")
                    df_final_candidates = df_filtered_main
                    filter_level = "Categoria Principal"

            if df_final_candidates.empty:
                print(f"  - ⚠️ No candidates found for main category '{main_category}'. Using all price-filtered products...")
                df_final_candidates = df_candidates
                filter_level = "Apenas Preço"
        
        else:
            print("   - ⚠️ AI classification failed. Using all price-filtered products as fallback.")
            df_final_candidates = df_candidates
            filter_level = "Apenas Preço (Falha na IA)"

        if df_final_candidates.empty:
            print(f"- ⚠️ Nenhum produto encontrado após todas as tentativas de filtro.")
            status = "Nenhum Produto na Categoria"
        else:
            print(f" - Temos {len(df_final_candidates)} candidatos para a IA (filtrado por: {filter_level}).")
            ai_result = get_best_match_from_ai(item_edital, df_final_candidates)
            time.sleep(30)

            best_match_data = ai_result.get("best_match")
            closest_match_data = ai_result.get("closest_match")
            reasoning = ai_result.get("reasoning")

            if best_match_data:
                print(f" ✅ - AI recomenda: {best_match_data.get('Marca', 'N/A')} {best_match_data.get('Modelo', 'N/A')}")
                status = "Match Encontrado"
                data_to_populate = best_match_data
            elif closest_match_data:
                print(f"- 🧿 AI sugere como mais próximo: {closest_match_data.get('Marca', 'N/A')} {closest_match_data.get('Modelo', 'N/A')}")
                if reasoning:
                    print(f"    Motivo: {reasoning}")
                status = "Match Parcial (Sugestão)"
                data_to_populate = closest_match_data
            else:
                print(" ❌ - AI não encontrou produto compatível ou próximo.")
                if reasoning:
                    print(f"    Motivo: {reasoning}")
                status = "Nenhum Produto Compatível"

        result_row = {
            'ARQUIVO': item_edital['ARQUIVO'],
            'Nº': item_edital['Nº'],
            'DESCRICAO': item_edital['DESCRICAO'],
            'REFERENCIA': item_edital.get('REFERENCIA'),
            'UNID_FORN': item_edital.get('UNID_FORN'),
            'QTDE': item_edital.get('QTDE'),
            'VALOR_TOTAL': item_edital.get('VALOR_TOTAL'),
            'LOCAL_ENTREGA': item_edital.get('LOCAL_ENTREGA'),
            'INTERVALO_LANCES': item_edital.get('INTERVALO_LANCES'),
            'VALOR_UNIT_EDITAL': item_edital['VALOR_UNIT'],
            'STATUS': status,
            'MOTIVO_INCOMPATIBILIDADE': reasoning if status != "Match Encontrado" else None,
            'LAST_UPDATE': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        if data_to_populate:
            cost_price = float(data_to_populate.get('Valor') or 0)
            final_price = cost_price * (1 + PROFIT_MARGIN)
            margem_lucro_valor = final_price - cost_price
            qtde_val = item_edital.get('QTDE')
            qtde = 0
            if pd.notna(qtde_val):
                try:
                    qtde = int(float(qtde_val))
                except (ValueError, TypeError):
                    qtde = 0
            lucro_total = margem_lucro_valor * qtde
            # --- Nova lógica de compatibilidade ---
            analise_compat = data_to_populate.get('Compatibilidade_analise')
            
            # Obter subcategoria do item do edital
            edital_subcategory = classification.get('subcategoria') if classification else None

            # Obter subcategoria do produto sugerido
            product_subcategory = None
            desc_fornecedor = data_to_populate.get('Descricao_fornecedor')
            if desc_fornecedor:
                # Usar df_final_candidates que foi a base para a IA
                matched_rows = df_final_candidates[df_final_candidates['DESCRICAO'] == desc_fornecedor]
                if not matched_rows.empty:
                    product_subcategory = matched_rows.iloc[0]['subcategoria']

            compat_score = calculate_compatibility_score(
                analise_compat,
                edital_subcategory,
                product_subcategory
            )
            # --- Fim da nova lógica ---

            result_row.update({
                'MARCA_SUGERIDA': data_to_populate.get('Marca'),
                'MODELO_SUGERIDO': data_to_populate.get('Modelo'),
                'CUSTO_FORNECEDOR': cost_price,
                'PRECO_FINAL_VENDA': final_price,
                'MARGEM_LUCRO_VALOR': margem_lucro_valor,
                'LUCRO_TOTAL': lucro_total,
                'DESCRICAO_FORNECEDOR': data_to_populate.get('Descricao_fornecedor'),
                'ANALISE_COMPATIBILIDADE': analise_compat,
                'COMPATIBILITY_SCORE': compat_score
            })

        # Append the result to existing data
        df_existing = pd.concat([df_existing, pd.DataFrame([result_row])], ignore_index=True)

        # Save incrementally
        df_final = df_existing

        output_columns = [
            'ARQUIVO','Nº','DESCRICAO','REFERENCIA','STATUS',
            'UNID_FORN', 'QTDE', 'VALOR_UNIT_EDITAL', 'VALOR_TOTAL',
            'LOCAL_ENTREGA', 'INTERVALO_LANCES',
            'MARCA_SUGERIDA', 'MODELO_SUGERIDO', 'CUSTO_FORNECEDOR',
            'PRECO_FINAL_VENDA','MARGEM_LUCRO_VALOR', 'LUCRO_TOTAL', 'MOTIVO_INCOMPATIBILIDADE',
            'DESCRICAO_FORNECEDOR','ANALISE_COMPATIBILIDADE','COMPATIBILITY_SCORE','LAST_UPDATE'
        ]
        for col in output_columns:
            if col not in df_final.columns:
                df_final[col] = ''
        df_final = df_final[output_columns]

        output_dir = os.path.dirname(CAMINHO_SAIDA)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        writer = pd.ExcelWriter(CAMINHO_SAIDA, engine='openpyxl')
        df_final.to_excel(writer, index=False, sheet_name='Proposta')

        workbook = writer.book
        worksheet = writer.sheets['Proposta']

        compat_col_idx = output_columns.index('COMPATIBILITY_SCORE') + 1  # 1-based

        for row_idx in range(2, len(df_final) + 2):
            score = df_final.at[row_idx - 2, 'COMPATIBILITY_SCORE']
            if pd.isna(score):
                score = 0.0
            color_fill = get_rainbow_color(score)
            for col_idx in range(1, len(output_columns) + 1):
                worksheet.cell(row=row_idx, column=col_idx).fill = color_fill

        writer.close()
        logger.info(f"✅ Incremental save after processing item {idx + 1}/{total_new_items} at {CAMINHO_SAIDA}")
        print(f"✅ - Incremental save completed for item {idx + 1}/{total_new_items}.")

    logger.info("All new items processed and saved incrementally.")
    print("✅ All new items processed and saved incrementally.")

if __name__ == "__main__":
    main()