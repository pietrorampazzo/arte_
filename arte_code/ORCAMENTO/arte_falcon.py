import pandas as pd
import google.generativeai as genai
import os
from dotenv import load_dotenv
import json
import time

# ============================================================
# CONFIGURAÇÕES E CONSTANTES
# ============================================================

# --- File Paths ---
CAMINHO_EDITAL = r"C:\Users\pietr\Meu Drive\arte_comercial\master.xlsx"
CAMINHO_BASE = r'C:\Users\pietr\OneDrive\.vscode\arte_\sheets\RESULTADO_metadados\produtos_categorizados_v3.xlsx'
CAMINHO_SAIDA = "sheets/RESULTADO_proposta/master_agosto.xlsx"

# --- Financial Parameters ---
PROFIT_MARGIN = 0.53  # 53%
INITIAL_PRICE_FILTER_PERCENTAGE = 0.60  # 60%

# --- AI Model Configuration ---
GEMINI_MODEL = "gemini-2.5-flash"

# --- Categorization Keywords ---
CATEGORIZATION_KEYWORDS = {
    'ACESSORIO_CORDA': ['arco','cavalete','corda','kit nut','kit rastilho'],
    'ACESSORIO_GERAL': ['bag','banco','carrinho prancha','estante de partitura','suporte'],
    'ACESSORIO_PERCURSSAO': ['baqueta','carrilhão','esteira','Máquina de Hi Hat','Pad para Bumbo','parafuso','pedal de bumbo','pele','prato','sino','talabarte','triângulo'],
    'ACESSORIO_SOPRO': ['graxa','oleo lubrificante','palheta de saxofone/clarinete'],
    'EQUIPAMENTO_AUDIO': ['fone de ouvido','globo microfone','Interface de guitarra','pedal','mesa de som','microfone'],
    'EQUIPAMENTO_CABO': ['cabo CFTV','cabo de rede','caixa medusa','Medusa','P10','P2xP10','painel de conexão','xlr M/F'],
    'EQUIPAMENTO_SOM': ['amplificador','caixa de som','cubo para guitarra'],
    "INSTRUMENTO_CORDA": ["violino","viola","violão","guitarra","baixo","violoncelo"],
    "INSTRUMENTO_PERCUSSAO": ["afuché","bateria","bombo","bumbo","caixa de guerra","caixa tenor","ganza","pandeiro","quadriton","reco reco","surdo","tambor","tarol","timbales"],
    "INSTRUMENTO_SOPRO": ["trompete","bombardino","trompa","trombone","tuba","sousafone","clarinete","saxofone","flauta","tuba bombardão","flugelhorn","euphonium"],
    "INSTRUMENTO_TECLAS": ["piano","teclado digital","glockenspiel","metalofone"],
}

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

def categorize_item(description: str) -> str:
    """Retorna a categoria do item com base em palavras-chave."""
    description_lower = description.lower()
    for category, keywords in CATEGORIZATION_KEYWORDS.items():
        if any(keyword in description_lower for keyword in keywords):
            return category
    return "OUTROS"


def get_best_match_from_ai(model, item_edital, df_candidates):
    """Usa o modelo de IA para encontrar o melhor match dentro dos candidatos."""
    print("   - Asking AI for the best match...")

    candidates_json = df_candidates[['DESCRICAO','categoria_principal','subcategoria','MARCA','MODELO','VALOR']] \
                        .to_json(orient="records", force_ascii=False, indent=2)

    prompt = f"""<identidade>Você é um consultor sênior em licitações públicas governamentais...</identidade>
<item_edital>{json.dumps(item_edital.to_dict(), ensure_ascii=False, indent=2)}</item_edital>
<base_fornecedores_filtrada>{candidates_json}</base_fornecedores_filtrada>
<objetivo>
1. Analise tecnicamente a 'DESCRICAO' do <item_edital>.
2. Compare-a com cada produto na <base_fornecedores_filtrada>.
3. Selecione o produto da base que seja ao menos **95% compativel** com TODAS as especificações técnicas do edital.
4. Dentro os produtos compatíveis, escolha o de **menor 'Valor'**.
5. Responda **apenas** com um objeto JSON contendo os dados do produto escolhido.
</objetivo>
<formato_saida>
{{
  "best_match": {{
    "Marca": "...",
    "Modelo": "...",
    "Valor": 1234.56,
    "Descricao_fornecedor": "...",
    "Compatibilidade_analise": "..."
  }}
}}
</formato_saida>"""

    try:
        response = model.generate_content(prompt)
        cleaned_response = response.text.strip().replace("```json","").replace("```","")
        return json.loads(cleaned_response)
    except Exception as e:
        print(f"   - ERROR during AI call: {e}")
        return {"best_match": None}

# ============================================================
# MAIN
# ============================================================

def main():
    print("Starting the product matching process...")

    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: GOOGLE_API_KEY not found in .env file.")
        return

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(GEMINI_MODEL)

    try:
        df_edital = pd.read_excel(CAMINHO_EDITAL)
        df_base = pd.read_excel(CAMINHO_BASE)
        print(f"👾 Edital loaded: {len(df_edital)} items")
        print(f"📯 Product base loaded: {len(df_base)} products")
    except FileNotFoundError as e:
        print(f"ERROR: Could not load data files. Details: {e}")
        return

    results = []
    total_items = len(df_edital)

    for idx, item_edital in df_edital.iterrows():
        descricao = str(item_edital['DESCRICAO'])
        print(f"\nProcessando item {idx + 1}/{total_items}: {descricao[:60]}...")
        status = ""
        best_match_data = None

        valor_unit_edital = item_edital['VALOR_UNIT']
        max_cost = valor_unit_edital * INITIAL_PRICE_FILTER_PERCENTAGE
        df_candidates = df_base[df_base['VALOR'] <= max_cost].copy()

        if df_candidates.empty:
            print(f"- ⚠️ No products found below the max cost of R${max_cost:.2f}.")
            status = "Nenhum Produto com Margem"
        else:
            item_category = categorize_item(item_edital['DESCRICAO'])
            print(f"   - Item do edital com a categoria: {item_category}")
            df_final_candidates = df_candidates[df_candidates['categoria_principal'] == item_category]

            if df_final_candidates.empty:
                print(f"- ⚠️ Nenhum produto encontrado na categoria '{item_category}'.")
                status = "Nenhum Produto na Categoria"
            else:
                print(f"   - Temos {len(df_final_candidates)} candidatos depois da filtragem.")
                ai_result = get_best_match_from_ai(model, item_edital, df_final_candidates)
                time.sleep(10)

                if ai_result and ai_result.get("best_match"):
                    best_match_data = ai_result["best_match"]
                    print(f" ✅ AI recomenda: {best_match_data['Marca']} {best_match_data['Modelo']}")
                    status = "Match Encontrado"
                else:
                    print(" ❌ AI não encontrou produto compatível.")
                    status = "Nenhum Produto Compatível"

        result_row = {
            'ARQUIVO': item_edital['ARQUIVO'],
            'Nº': item_edital['Nº'],
            'DESCRICAO_EDITAL': item_edital['DESCRICAO'],
            'VALOR_UNIT_EDITAL': item_edital['VALOR_UNIT'],
            'STATUS': status
        }

        if best_match_data:
            cost_price = float(best_match_data.get('Valor') or 0)
            final_price = cost_price * (1 + PROFIT_MARGIN)
            result_row.update({
                'MARCA_SUGERIDA': best_match_data.get('Marca'),
                'MODELO_SUGERIDO': best_match_data.get('Modelo'),
                'CUSTO_FORNECEDOR': cost_price,
                'PRECO_FINAL_VENDA': final_price,
                'MARGEM_LUCRO_VALOR': final_price - cost_price,
                'DESCRICAO_FORNECEDOR': best_match_data.get('Descricao_fornecedor'),
                'ANALISE_COMPATIBILIDADE': best_match_data.get('Compatibilidade_analise')
            })

        results.append(result_row)

    print("\nProcess finished. Generating output file...")

    if results:
        df_results = pd.DataFrame(results)
        output_columns = [
            'ARQUIVO','Nº','STATUS','DESCRICAO_EDITAL','VALOR_UNIT_EDITAL',
            'MARCA_SUGERIDA','MODELO_SUGERIDO','CUSTO_FORNECEDOR',
            'PRECO_FINAL_VENDA','MARGEM_LUCRO_VALOR','DESCRICAO_FORNECEDOR',
            'ANALISE_COMPATIBILIDADE'
        ]
        for col in output_columns:
            if col not in df_results.columns:
                df_results[col] = ''
        df_results = df_results[output_columns]

        output_dir = os.path.dirname(CAMINHO_SAIDA)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        df_results.to_excel(CAMINHO_SAIDA, index=False)
        print(f"✅ Success! Output file generated at: {CAMINHO_SAIDA}")
    else:
        print("⚠️ No results were generated.")

if __name__ == "__main__":
    main()
