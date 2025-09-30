import pandas as pd
import numpy as np
import os, time, json, logging
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer, util
import google.generativeai as genai

# Configurações
BASE_DIR = r"C:\Users\pietr\OneDrive\.vscode\arte_"
CAMINHO_EDITAL = os.path.join(BASE_DIR, "DOWNLOADS", "master.xlsx")
CAMINHO_BASE_PRODUTOS = os.path.join(BASE_DIR, "DOWNLOADS", "METADADOS", "produtos_metadados.xlsx")
CAMINHO_SAIDA = os.path.join(BASE_DIR, "DOWNLOADS", "master_machine.xlsx")
SENTENCE_MODEL = "all-mpnet-base-v2"
TOP_N = 13
PRECO_FATOR = 0.6

LLM_MODELS_FALLBACK = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-1.5-flash",  
]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Função para gerar resposta da IA
def gerar_com_fallback(prompt: str):
    for modelo in LLM_MODELS_FALLBACK:
        try:
            m = genai.GenerativeModel(modelo)
            r = m.generate_content(prompt)
            if r.text: return r.text
        except Exception as e:
            logger.warning(f"Erro no modelo {modelo}: {e}")
            continue
    return None

def validar_llm(item, candidatos):
    prompt = f"""
Você é especialista em licitações. 
Item do edital:
{item.to_dict()}

Candidatos:
{candidatos.to_json(orient="records", force_ascii=False)}

Analise compatibilidade. Retorne JSON:
{{
  "best_match": {{
    "Marca": "...",
    "Modelo": "...",
    "Valor": 123.45,
    "Descricao": "...",
    "Compatibilidade_score": 85,
    "Compatibilidade_analise": "..."
  }}
}}
ou:
{{"best_match": null, "reasoning": "motivo"}}
"""
    resp = gerar_com_fallback(prompt)
    if resp:
        try:
            return json.loads(resp.strip().replace("```json","").replace("```",""))
        except: return {"best_match": None, "reasoning": "Erro no parse JSON"}
    return {"best_match": None, "reasoning": "Falha em todos modelos"}

def main():
    load_dotenv()
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

    df_edital = pd.read_excel(CAMINHO_EDITAL)
    df_prod = pd.read_excel(CAMINHO_BASE_PRODUTOS)
    df_prod['VALOR'] = pd.to_numeric(df_prod['VALOR'], errors='coerce').fillna(0)

    st_model = SentenceTransformer(SENTENCE_MODEL)
    prod_embeddings = st_model.encode(df_prod['DESCRICAO'].astype(str).tolist(), convert_to_tensor=True)

    if os.path.exists(CAMINHO_SAIDA):
        df_saida = pd.read_excel(CAMINHO_SAIDA)
    else:
        df_saida = pd.DataFrame()

    for idx, item in df_edital.iterrows():
        if not df_saida.empty and (df_saida['Nº']==item['Nº']).any():
            continue  # já processado

        item_desc = str(item['DESCRICAO'])
        item_valor = float(item.get('VALOR_REF', 0) or 0)

        # Embedding do item
        item_emb = st_model.encode(item_desc, convert_to_tensor=True)
        scores = util.cos_sim(item_emb, prod_embeddings)[0].cpu().numpy()

        # Ranking inicial por similaridade
        df_prod['score'] = scores
        candidatos = df_prod.sort_values("score", ascending=False)

        # Filtro de preço
        if item_valor > 0:
            candidatos = candidatos[candidatos['VALOR'] <= item_valor * PRECO_FATOR]

        # Pegar top N
        candidatos = candidatos.head(TOP_N)
        if candidatos.empty:
            candidatos = df_prod.sort_values("score", ascending=False).head(TOP_N)

        # Validação LLM
        resultado = validar_llm(item, candidatos)

        row = item.to_dict()
        bm = resultado.get("best_match")
        if bm:
            row.update({
                "STATUS":"Match Encontrado",
                "MARCA_SUGERIDA": bm.get("Marca"),
                "MODELO_SUGERIDO": bm.get("Modelo"),
                "CUSTO_FORNECEDOR": bm.get("Valor"),
                "DESCRICAO_FORNECEDOR": bm.get("Descricao"),
                "COMPATIBILIDADE_SCORE": bm.get("Compatibilidade_score"),
                "ANALISE_COMPATIBILIDADE": bm.get("Compatibilidade_analise")
            })
        else:
            row.update({
                "STATUS":"Nenhum Match",
                "MOTIVO_INCOMPATIBILIDADE": resultado.get("reasoning"),
                "COMPATIBILIDADE_SCORE": 0
            })

        df_saida = pd.concat([df_saida, pd.DataFrame([row])], ignore_index=True)
        df_saida.to_excel(CAMINHO_SAIDA, index=False)
        logger.info(f"Item {item['Nº']} processado e salvo.")

        time.sleep(3)

if __name__=="__main__":
    main()
