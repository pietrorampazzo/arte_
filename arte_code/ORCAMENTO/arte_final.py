# arte_final.py
# This script will contain the final, robust solution for matching bid items to products.
# It will implement the logic defined in the plan.

import pandas as pd
import google.generativeai as genai
import os
from dotenv import load_dotenv
import json
import time
# Local imports
import config

def categorize_item(description: str) -> str:
    """
    Categorizes an item based on keywords in its description.

    Args:

        description: The description of the item.

    Returns:
        The category of the item, or "OUTROS" if no category is found.
    """
    description_lower = description.lower()
    for category, keywords in config.CATEGORIZATION_KEYWORDS.items():
        if any(keyword in description_lower for keyword in keywords):
            return category
    return "OUTROS"



def get_best_match_from_ai(model, item_edital, df_candidates):
    """
    Uses the AI model to find the best match from a list of candidate products.
    """
    print("   - Asking AI for the best match...")
    
    # Prepare data for the prompt 

    candidates_json = df_candidates[['DESCRICAO', 'categoria_principal', 'subcategoria', 'MARCA', 'MODELO', 'VALOR']].to_json(orient="records", force_ascii=False, indent=2)
    
    prompt = f"""<identidade>Você é um consultor sênior em licitações públicas governamentais, com mais de 20 anos de experiência em processos licitatórios para instrumentos musicais, equipamentos de som, áudio profissional e eletrônicos técnicos. Domina a Lei 14.133/21, princípios como isonomia, impessoalidade, economicidade e competitividade. Sua expertise combina análise de aparatos musicais, vendas de equipamentos e avaliação jurídica para impugnações. Sempre, sem ultrapassar valores de referência do edital, priorize o menor preço entre opções compatíveis.</identidade>
<item_edital>{json.dumps(item_edital.to_dict(), ensure_ascii=False, indent=2)}</item_edital>
<base_fornecedores_filtrada>{candidates_json}</base_fornecedores_filtrada>

<objetivo>
1.  Analise tecnicamente a 'DESCRICAO' do <item_edital>.
2.  Compare-a com cada produto na <base_fornecedores_filtrada>.
3.  Selecione o produto da base que seja ao menos **95% compativel** com TODAS as especificações técnicas do edital. Upgrades (especificações superiores) são permitidos e desejáveis.
4.  Dentro os produtos 100% compatíveis, escolha o de **menor 'Valor'**.
5.  Responda **apenas** com um objeto JSON contendo os dados do produto escolhido.
</objetivo>

<formato_saida>
Responda APENAS com um único objeto JSON. Não inclua ```json, explicações ou qualquer outro texto. O JSON deve ter a seguinte estrutura:
{{
  "best_match": {{
    "Marca": "Marca do Produto",
    "Modelo": "Modelo do Produto",
    "Valor": 1234.56,
    "Descricao_fornecedor": "Descrição completa do produto na base",
    "Compatibilidade_analise": "Explique brevemente por que este produto é 100% compatível, destacando as especificações que dão match."
  }}
}}
Se nenhum produto for 100% compatível, retorne:
{{
  "best_match": null
}}
</formato_saida>
"""

    try:
        response = model.generate_content(prompt)
        # Clean the response to ensure it's valid JSON
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(cleaned_response)
    except Exception as e:
        print(f"   - ERROR during AI call: {e}")
        print(f"   - AI Response Text: {response.text if 'response' in locals() else 'No response'}")
        return {"best_match": None}


def main():
    """
    Main function to orchestrate the product matching process.
    """
    print("Starting the product matching process...")

    # Load environment variables (like API key)
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: GOOGLE_API_KEY not found in .env file.")
        return
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(config.GEMINI_MODEL)

    # Load data
    try:
        df_edital = pd.read_excel(config.CAMINHO_EDITAL)
        df_base = pd.read_excel(config.CAMINHO_BASE)
        print(f"👾 Edital loaded: {len(df_edital)} items")
        print(f"📯 Product base loaded: {len(df_base)} products")
    except FileNotFoundError as e:
        print(f"ERROR: Could not load data files. Details: {e}")
        return

    results = []
    total_items = len(df_edital)

    # Loop through each item in the bid
    for idx, item_edital in df_edital.iterrows():
        descricao = str(item_edital['DESCRICAO'])
        print(f"\nProcessando item {idx + 1}/{total_items}: {descricao[:60]}...")
        status = ""
        best_match_data = None

        # --- 1. Profitability Filter ---
        valor_unit_edital = item_edital['VALOR_UNIT']
        max_cost = valor_unit_edital * config.INITIAL_PRICE_FILTER_PERCENTAGE
        df_candidates = df_base[df_base['VALOR'] <= max_cost].copy()

        if df_candidates.empty:
            print(f"- ⚠️ No products found below the max cost of R${max_cost:.2f}.")
            status = "Nenhum Produto com Margem"
        else:
            # --- 2. Category Filter ---
            item_category = categorize_item(item_edital['DESCRICAO'])
            print(f"   - Item do edital com a categoria: {item_category}")
            df_final_candidates = df_candidates[df_candidates['categoria_principal'] == item_category]

            if df_final_candidates.empty:
                print(f"- ⚠️ - Nenhum produto encontrado na categoria base: '{item_category}' (dentro do filtro de preço!).")
                status = "Nenhum Produto na Categoria da Base"
            else:
                print(f"   - Temos {len(df_final_candidates)} candidatos depois da filtragem.")
                # --- 3. AI-Powered Matching ---
                ai_result = get_best_match_from_ai(model, item_edital, df_final_candidates)
                time.sleep(10) # Basic rate limiting

                if ai_result and ai_result.get("best_match"):
                    best_match_data = ai_result["best_match"]
                    print(f" ✅  - AI recomenda: {best_match_data['Marca']} {best_match_data['Modelo']}")
                    status = "Match Encontrado"
                else:
                    print("  ❌ - AI não encontrou um produto compativel.")
                    status = "Nenhum Produto Compatível"
        
        # --- 4. Assemble Result ---
        # This block is now ALWAYS executed for every item
        result_row = {
            'ARQUIVO': item_edital['ARQUIVO'],
            'Nº': item_edital['Nº'],
            'DESCRICAO_EDITAL': item_edital['DESCRICAO'],
            'VALOR_UNIT_EDITAL': item_edital['VALOR_UNIT'],
            'STATUS': status
        }

        if best_match_data:
            cost_price = best_match_data.get('Valor', 0)
            final_price = cost_price * (1 + config.PROFIT_MARGIN)
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

    # --- 5. Generate Output File ---
    if results:
        df_results = pd.DataFrame(results)
        
        # Define column order for clarity
        output_columns = [
            'ARQUIVO', 'Nº', 'STATUS', 'DESCRICAO_EDITAL', 'VALOR_UNIT_EDITAL',
            'MARCA_SUGERIDA', 'MODELO_SUGERIDO', 'CUSTO_FORNECEDOR', 
            'PRECO_FINAL_VENDA', 'MARGEM_LUCRO_VALOR', 'DESCRICAO_FORNECEDOR',
            'ANALISE_COMPATIBILIDADE'
        ]
        
        # Ensure all columns exist, fill missing with empty string
        for col in output_columns:
            if col not in df_results.columns:
                df_results[col] = ''
        
        df_results = df_results[output_columns]

        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(config.CAMINHO_SAIDA)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        df_results.to_excel(config.CAMINHO_SAIDA, index=False)
        print(f"✅ Success! Output file generated at: {config.CAMINHO_SAIDA}")
    else:
        print("⚠️ No results were generated to create an output file.")


if __name__ == "__main__":
    main()
