
import pandas as pd
import numpy as np
import os
import time
import json
import logging
from dotenv import load_dotenv
import joblib
import google.generativeai as genai
import google.api_core.exceptions as google_exceptions

# Sentence-Transformers para busca semântica
from sentence_transformers import SentenceTransformer, util

# =====================================================================
# CONFIGURAÇÕES E CONSTANTES
# =====================================================================

# --- File Paths ---
BASE_DIR = r"C:\Users\pietr\OneDrive\.vscode\arte_"
CAMINHO_EDITAL = os.path.join(BASE_DIR, "DOWNLOADS", "master.xlsx")
CAMINHO_BASE_PRODUTOS = os.path.join(BASE_DIR, "DOWNLOADS", "METADADOS", "categoria_GPT.xlsx")
# Novo arquivo de saída para este pipeline simplificado
CAMINHO_SAIDA = os.path.join(BASE_DIR, "DOWNLOADS", "master_stanley_semantic.xlsx") 

# --- ML Models & Precomputed Data Paths ---
MODELS_DIR = os.path.join(BASE_DIR, "machine_learning", "ml_models")
# O classificador não é mais necessário, mas os embeddings sim.
EMBEDDINGS_PATH = os.path.join(MODELS_DIR, "product_embeddings.npy")
EMBEDDINGS_DATA_PATH = os.path.join(MODELS_DIR, "product_embeddings_data.pkl")

# --- ML & AI Parameters ---
SEMANTIC_SEARCH_TOP_K = 15 # Nº de candidatos que a busca semântica vai levantar para o LLM
SENTENCE_TRANSFORMER_MODEL = 'paraphrase-multilingual-MiniLM-L12-v2'

# --- AI Model Configuration ---
LLM_MODELS_FALLBACK = [    
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-1.5-flash",  
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    ]

# --- Logging Configuration ---
LOG_FILE = os.path.join(BASE_DIR, "LOGS", "arte_semantic_pipeline.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# =====================================================================
# FUNÇÕES DE IA E EMBEDDINGS (Reutilizadas)
# =====================================================================

def gerar_conteudo_com_fallback(prompt: str, modelos: list[str]) -> str | None:
    """Tenta gerar conteúdo usando uma lista de modelos em ordem de preferência."""
    for nome_modelo in modelos:
        try:
            logger.info(f"   - Tentando chamada à API com o modelo: {nome_modelo}...")
            model = genai.GenerativeModel(nome_modelo)
            response = model.generate_content(prompt)
            if not response.parts:
                finish_reason = response.candidates[0].finish_reason.name if response.candidates else 'N/A'
                logger.warning(f"   - ❌ A GERAÇÃO RETORNOU VAZIA. Motivo: {finish_reason}.")
                return None
            logger.info(f"   - Sucesso com o modelo '{nome_modelo}'.")
            return response.text
        except google_exceptions.ResourceExhausted as e:
            logger.warning(f"- Cota excedida para o modelo '{nome_modelo}'. Tentando o próximo da lista.")
            time.sleep(5)
            continue
        except Exception as e:
            logger.error(f"   - ❌ Erro inesperado com o modelo '{nome_modelo}': {e}")
            return None
    logger.error("   - ❌ FALHA TOTAL: Todos os modelos na lista de fallback falharam.")
    return None

def get_best_match_from_ai(item_edital, df_candidates):
    """Usa o modelo de IA para encontrar o melhor match dentro dos candidatos."""
    logger.info(f" - Enviando {len(df_candidates)} candidatos para validação final do LLM...")
    if df_candidates.empty:
        return {"best_match": None, "reasoning": "Nenhum candidato fornecido para o LLM."}

    # A subcategoria não é mais o foco, mas pode ser útil para o LLM
    candidates_json = df_candidates[['DESCRICAO','subcategoria','MARCA','MODELO','VALOR']].to_json(orient="records", force_ascii=False, indent=2)
    prompt = f"""<identidade>Você é um consultor de licitações especialista em áudio e instrumentos musicais.</identidade>
<objetivo>
1. Analise o item do edital: Descrição: "{item_edital['DESCRICAO']}" e Referência: "{item_edital.get('REFERENCIA', 'N/A')}".
2. Compare-o com a lista de produtos candidatos.
3. Encontre o produto da lista que seja o melhor correspondente técnico (>=95% compatível) e de menor preço entre os compatíveis.
4. Responda APENAS com um objeto JSON com o formato de saída especificado.
</objetivo>
<formato_saida>
{{
  "best_match": {{
    "Marca": "Marca do Produto",
    "Modelo": "Modelo do Produto",
    "Valor": 1234.56,
    "Descricao_fornecedor": "Descrição completa do produto na base",
    "Compatibilidade_analise": "Análise detalhada da compatibilidade."
  }}
}}
// Se nenhum for compatível, retorne best_match como null.
{{
  "best_match": null,
  "reasoning": "Explique o principal motivo da incompatibilidade."
}}
</formato_saida>
<item_edital>{item_edital.to_json(force_ascii=False)}</item_edital>
<lista_produtos_candidatos>{candidates_json}</lista_produtos_candidatos>
JSON:
"""
    response_text = gerar_conteudo_com_fallback(prompt, LLM_MODELS_FALLBACK)
    if response_text:
        try:
            cleaned_response = response_text.strip().replace("```json", "").replace("```", "")
            return json.loads(cleaned_response)
        except json.JSONDecodeError as e:
            logger.error(f"   - ERRO decodificando JSON da IA: {e}")
            return {"best_match": None, "reasoning": f"Erro na decodificação do JSON da API: {e}"}
    return {"best_match": None, "reasoning": "Falha na chamada da API para todos os modelos."}

def generate_embeddings(df_path: str, embeddings_save_path: str, data_save_path: str):
    """
    Gera e salva os embeddings de texto para todas as descrições de produtos
    usando um modelo SentenceTransformer.
    """
    logger.info("Iniciando geração de embeddings semânticos para os produtos...")
    df = pd.read_excel(df_path)
    df.dropna(subset=['DESCRICAO'], inplace=True)
    df['DESCRICAO'] = df['DESCRICAO'].astype(str)

    logger.info(f"Carregando o modelo '{SENTENCE_TRANSFORMER_MODEL}'...")
    model = SentenceTransformer(SENTENCE_TRANSFORMER_MODEL)

    logger.info(f"Gerando embeddings para {len(df)} descrições de produtos...")
    df['VALOR'] = pd.to_numeric(df['VALOR'], errors='coerce').fillna(0)
    
    # Combina DESCRICAO, MARCA e MODELO para um embedding mais rico
    df['TEXTO_PARA_EMBEDDING'] = df['DESCRICAO'] + " " + df['MARCA'].fillna('') + " " + df['MODELO'].fillna('')
    
    embeddings = model.encode(df['TEXTO_PARA_EMBEDEDING'].tolist(), convert_to_tensor=True, show_progress_bar=True)

    logger.info(f"Salvando embeddings em: {embeddings_save_path}")
    np.save(embeddings_save_path, embeddings.cpu().numpy())
    
    # Salva o dataframe com os dados relevantes para busca
    df_to_save = df.drop(columns=['TEXTO_PARA_EMBEDDING']).copy()
    df_to_save.to_pickle(data_save_path)
    
    logger.info(f"Dados dos embeddings salvos em: {data_save_path}")
    logger.info("Geração de embeddings concluída.")

# =====================================================================
# PIPELINE PRINCIPAL (SEMÂNTICO DIRETO)
# =====================================================================

def main():
    logger.info("Iniciando o pipeline de BUSCA SEMÂNTICA DIRETA...")
    
    # --- Configuração de API ---
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_PAGO")
    if not api_key:
        logger.error("GOOGLE_API_PAGO não encontrada no arquivo .env. Abortando.")
        return
    genai.configure(api_key=api_key)

    # --- Preparação dos Embeddings ---
    os.makedirs(MODELS_DIR, exist_ok=True)
    if not os.path.exists(EMBEDDINGS_PATH) or not os.path.exists(EMBEDDINGS_DATA_PATH):
        logger.warning("Embeddings não encontrados. Iniciando geração...")
        generate_embeddings(CAMINHO_BASE_PRODUTOS, EMBEDDINGS_PATH, EMBEDDINGS_DATA_PATH)

    # --- Carregar Dados Pré-computados ---
    logger.info("Carregando embeddings e dados dos produtos...")
    product_embeddings = np.load(EMBEDDINGS_PATH)
    df_products = pd.read_pickle(EMBEDDINGS_DATA_PATH)
    st_model = SentenceTransformer(SENTENCE_TRANSFORMER_MODEL)
    
    # --- Carregar Itens do Edital ---
    try:
        df_edital = pd.read_excel(CAMINHO_EDITAL)
        logger.info(f"Carregados {len(df_edital)} itens do edital.")
    except FileNotFoundError:
        logger.error(f"Arquivo do edital não encontrado em: {CAMINHO_EDITAL}")
        return

    # --- Lógica de Salvamento Incremental e Resumo ---
    if os.path.exists(CAMINHO_SAIDA):
        logger.info(f"Carregando resultados existentes de {CAMINHO_SAIDA}")
        df_final = pd.read_excel(CAMINHO_SAIDA)
        df_final['chave'] = df_final['ARQUIVO'].astype(str) + "_" + df_final['Nº'].astype(str)
        existing_keys = set(df_final['chave'])
    else:
        df_final = pd.DataFrame()
        existing_keys = set()

    df_edital['chave'] = df_edital['ARQUIVO'].astype(str) + "_" + df_edital['Nº'].astype(str)
    df_novos_itens = df_edital[~df_edital['chave'].isin(existing_keys)].copy()

    if df_novos_itens.empty:
        logger.info("✅ Nenhum item novo para processar. O arquivo de saída já está atualizado.")
        return

    logger.info(f"Encontrados {len(df_novos_itens)} novos itens para processar.")

    # --- Loop de Processamento ---
    for idx, item_edital in df_novos_itens.iterrows():
        item_idx_num = df_novos_itens.index.get_loc(idx) + 1
        logger.info(f"\n--- Processando item {item_idx_num}/{len(df_novos_itens)}: {item_edital['DESCRICAO'][:70]}...")
        
        # ETAPA 1: BUSCA SEMÂNTICA GLOBAL
        # Combina DESCRICAO e REFERENCIA para uma busca mais rica
        item_text = str(item_edital['DESCRICAO']) + " " + str(item_edital.get('REFERENCIA', ''))
        
        # Gera embedding para o item do edital
        item_embedding = st_model.encode(item_text, convert_to_tensor=True)
        
        # Calcula similaridade contra TODOS os produtos
        cos_scores = util.cos_sim(item_embedding, product_embeddings)[0]
        
        # Obter os top K candidatos de toda a base
        top_k_candidates = min(SEMANTIC_SEARCH_TOP_K, len(df_products))
        top_results = np.argpartition(-cos_scores.cpu().numpy(), range(top_k_candidates))[:top_k_candidates]
        
        df_candidates = df_products.iloc[top_results]
        logger.info(f"   [ML] {len(df_candidates)} candidatos encontrados via busca semântica global.")

        # ETAPA 2: VALIDAÇÃO FINAL COM LLM
        ai_result = get_best_match_from_ai(item_edital, df_candidates)
        
        result_row = item_edital.to_dict()
        best_match = ai_result.get("best_match")
        if best_match:
            logger.info(f"   [IA] ✅ Match encontrado: {best_match.get('Marca')} {best_match.get('Modelo')}")
            result_row['STATUS'] = 'Match Encontrado'
            result_row['MARCA_SUGERIDA'] = best_match.get('Marca')
            result_row['MODELO_SUGERIDO'] = best_match.get('Modelo')
            result_row['CUSTO_FORNECEDOR'] = best_match.get('Valor')
            result_row['DESCRICAO_FORNECEDOR'] = best_match.get('Descricao_fornecedor')
            result_row['ANALISE_COMPATIBILIDADE'] = best_match.get('Compatibilidade_analise')
        else:
            logger.warning(f"   [IA] ❌ Nenhum match compatível encontrado. Motivo: {ai_result.get('reasoning')}")
            result_row['STATUS'] = 'Nenhum Match Compatível'
            result_row['MOTIVO_INCOMPATIBILIDADE'] = ai_result.get('reasoning')
        
        # --- Salvamento Incremental ---
        df_final = pd.concat([df_final, pd.DataFrame([result_row])], ignore_index=True)
        try:
            df_final.drop(columns=['chave'], inplace=True, errors='ignore')
            df_final.to_excel(CAMINHO_SAIDA, index=False)
            logger.info(f"   💾 Progresso salvo. {len(df_final)} itens no arquivo de saída.")
        except Exception as e:
            logger.error(f"   ❌ Falha ao salvar o arquivo Excel incrementalmente: {e}")

        time.sleep(5)

    logger.info("✅ Processamento de todos os itens concluído.")

if __name__ == "__main__":
    main()
