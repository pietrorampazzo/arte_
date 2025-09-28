
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
import sys

# Scikit-learn para ML clássico
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score

# Sentence-Transformers para busca semântica
from sentence_transformers import SentenceTransformer, util

# =====================================================================
# CONFIGURAÇÕES E CONSTANTES
# =====================================================================

# --- File Paths ---
BASE_DIR = r"C:\Users\pietr\OneDrive\.vscode\arte_"
CAMINHO_EDITAL = os.path.join(BASE_DIR, "DOWNLOADS", "master.xlsx")
CAMINHO_BASE_PRODUTOS = os.path.join(BASE_DIR, "DOWNLOADS", "METADADOS", "categoria_GPT.xlsx")
CAMINHO_SAIDA = os.path.join(BASE_DIR, "DOWNLOADS", "master_stanley_ml.xlsx")

# --- ML Models & Precomputed Data Paths ---
MODELS_DIR = os.path.join(BASE_DIR, "machine_learning", "ml_models")
CLASSIFIER_PATH = os.path.join(MODELS_DIR, "subcategory_classifier.joblib")
EMBEDDINGS_PATH = os.path.join(MODELS_DIR, "product_embeddings.npy")
EMBEDDINGS_DATA_PATH = os.path.join(MODELS_DIR, "product_embeddings_data.pkl")

# --- ML & AI Parameters ---
SEMANTIC_SEARCH_TOP_K = 10 # Nº de candidatos que a busca semântica vai levantar para o LLM
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
LOG_FILE = os.path.join(BASE_DIR, "LOGS", "arte_ml_pipeline.log")
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
# FUNÇÕES DE IA (REUTILIZADAS DO SCRIPT ANTERIOR)
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
    """Usa o modelo de IA para encontrar o melhor match e calcular um score de compatibilidade."""
    logger.info(f" - Enviando {len(df_candidates)} candidatos para validação final do LLM...")
    if df_candidates.empty:
        return {"best_match": None, "reasoning": "Nenhum candidato fornecido para o LLM."}

    candidates_json = df_candidates[['DESCRICAO','subcategoria','MARCA','MODELO','VALOR']].to_json(orient="records", force_ascii=False, indent=2)
    prompt = f"""<identidade>Você é um consultor de licitações especialista em áudio e instrumentos musicais.</identidade>
<objetivo>
1.  **Analise o Item do Edital:** Decomponha a descrição do item do edital em especificações-chave (ex: "tipo de produto", "potência", "dimensão", "funcionalidade X", "cor Y").
2.  **Compare com os Candidatos:** Para cada produto candidato, verifique quantas das especificações-chave ele atende.
3.  **Calcule o Score:** Calcule um `Compatibilidade_score` (de 0 a 100) para o melhor candidato. O score é a porcentagem de especificações atendidas. Exemplo: se o edital tem 4 especificações e o produto atende 3, o score é 75.
4.  **Selecione o Melhor:** Encontre o produto com o maior `Compatibilidade_score`. Se houver empate, escolha o de menor `VALOR`. O produto só é um "best_match" se o score for >= 60.
5.  **Responda em JSON:** Retorne APENAS um objeto JSON com o formato especificado.
</objetivo>
<formato_saida>
// Se encontrar um match com score >= 60
{{
  "best_match": {{
    "Marca": "Marca do Produto",
    "Modelo": "Modelo do Produto",
    "Valor": 1234.56,
    "Descricao_fornecedor": "Descrição completa do produto na base",
    "Compatibilidade_analise": "Análise detalhada, explicando quais especificações bateram e quais não.",
    "Compatibilidade_score": 85 // Score numérico de 0 a 100
  }}
}}
// Se nenhum for compatível (score < 60)
{{
  "best_match": null,
  "reasoning": "Explique porque os melhores candidatos não atingiram o score mínimo de 60."
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


# =====================================================================
# NOVAS FUNÇÕES DE MACHINE LEARNING
# =====================================================================

def train_classifier(df_path: str, classifier_save_path: str):
    """
    Treina um modelo de classificação (Random Forest) para prever a 'subcategoria'
    a partir da 'DESCRICAO' e salva o pipeline treinado.
    """
    logger.info("Iniciando treinamento do classificador de subcategoria...")
    df = pd.read_excel(df_path)
    df.dropna(subset=['DESCRICAO', 'subcategoria'], inplace=True)
    df['DESCRICAO'] = df['DESCRICAO'].astype(str)
    df['subcategoria'] = df['subcategoria'].astype(str)

    X = df['DESCRICAO']
    y = df['subcategoria']

    # Dividir dados para avaliar a acurácia do modelo treinado
    try:
        # Tenta fazer a divisão estratificada
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    except ValueError:
        logger.warning("Não foi possível usar a estratificação (alguma subcategoria tem apenas 1 membro). Tentando sem estratificação.")
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Criação do Pipeline de ML:
    # 1. TfidfVectorizer: Converte texto em uma matriz de features numéricas.
    # 2. RandomForestClassifier: Um classificador robusto que funciona bem para texto.
    classifier_pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(sublinear_tf=True, min_df=5, ngram_range=(1, 2))),
        ('clf', RandomForestClassifier(n_estimators=100, random_state=42))
    ])

    logger.info("Treinando o pipeline...")
    classifier_pipeline.fit(X_train, y_train)

    # Avalia e reporta a acurácia
    y_pred = classifier_pipeline.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    logger.info(f"Acurácia do classificador no set de teste: {accuracy:.2f}")

    logger.info(f"Salvando o pipeline treinado em: {classifier_save_path}")
    joblib.dump(classifier_pipeline, classifier_save_path)
    logger.info("Treinamento concluído e modelo salvo.")


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
    # Garante que a coluna 'VALOR' seja numérica
    df['VALOR'] = pd.to_numeric(df['VALOR'], errors='coerce').fillna(0)
    
    embeddings = model.encode(df['DESCRICAO'].tolist(), convert_to_tensor=True, show_progress_bar=True)

    # Salva os embeddings e os dados correspondentes
    logger.info(f"Salvando embeddings em: {embeddings_save_path}")
    np.save(embeddings_save_path, embeddings.cpu().numpy())
    
    # Salva o dataframe com os dados relevantes para busca
    df_to_save = df[['DESCRICAO', 'subcategoria', 'MARCA', 'MODELO', 'VALOR']].copy()
    df_to_save.to_pickle(data_save_path)
    
    logger.info(f"Dados dos embeddings salvos em: {data_save_path}")
    logger.info("Geração de embeddings concluída.")


# =====================================================================
# FUNÇÃO DE ESTILIZAÇÃO E SALVAMENTO
# =====================================================================

def save_styled_excel(file_path: str):
    """
    Carrega o arquivo Excel final, aplica um gradiente de cores na coluna 
    de score e salva o arquivo estilizado.
    """
    try:
        df = pd.read_excel(file_path)
        if 'COMPATIBILIDADE_SCORE' not in df.columns:
            logger.warning("A coluna 'COMPATIBILIDADE_SCORE' não foi encontrada. Pulando a estilização.")
            return

        # Garante que a coluna de score é numérica para o gradiente
        df['COMPATIBILIDADE_SCORE'] = pd.to_numeric(df['COMPATIBILIDADE_SCORE'], errors='coerce').fillna(0)

        logger.info("Aplicando formatação de cores ao arquivo de saída...")
        
        styled_df = df.style.background_gradient(
            cmap='RdYlGn', 
            subset=['COMPATIBILIDADE_SCORE'],
            low=0.4,  # Começa a cor em um tom mais claro
            high=1.0  # Termina em um tom mais escuro
        )

        # Salva o arquivo estilizado usando o motor openpyxl
        styled_df.to_excel(file_path, index=False, engine='openpyxl')
        logger.info(f"✅ Arquivo final estilizado e salvo em: {file_path}")

    except FileNotFoundError:
        logger.error(f"Arquivo não encontrado em {file_path} para estilizar. Nada a fazer.")
    except Exception as e:
        logger.error(f"Ocorreu um erro ao estilizar o arquivo Excel: {e}")


# =====================================================================
# PIPELINE PRINCIPAL
# =====================================================================

def main():
    logger.info("Iniciando o pipeline de ML para matching de produtos...")
    
    # --- Configuração de API ---
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_PAGO")
    if not api_key:
        logger.error("GOOGLE_API_PAGO não encontrada no arquivo .env. Abortando.")
        return
    genai.configure(api_key=api_key)

    # --- Preparação dos Modelos e Dados ---
    os.makedirs(MODELS_DIR, exist_ok=True)

    # Verifica a flag --retrain para forçar o retreinamento
    force_retrain = '--retrain' in sys.argv

    if force_retrain and os.path.exists(CLASSIFIER_PATH):
        logger.info("Flag --retrain detectada. Removendo modelo classificador antigo.")
        os.remove(CLASSIFIER_PATH)

    if force_retrain and os.path.exists(EMBEDDINGS_PATH):
        logger.info("Flag --retrain detectada. Removendo embeddings antigos.")
        os.remove(EMBEDDINGS_PATH)
        if os.path.exists(EMBEDDINGS_DATA_PATH):
            os.remove(EMBEDDINGS_DATA_PATH)

    if not os.path.exists(CLASSIFIER_PATH):
        logger.warning("Modelo classificador não encontrado. Iniciando treinamento...")
        train_classifier(CAMINHO_BASE_PRODUTOS, CLASSIFIER_PATH)

    if not os.path.exists(EMBEDDINGS_PATH) or not os.path.exists(EMBEDDINGS_DATA_PATH):
        logger.warning("Embeddings não encontrados. Iniciando geração...")
        generate_embeddings(CAMINHO_BASE_PRODUTOS, EMBEDDINGS_PATH, EMBEDDINGS_DATA_PATH)

    # --- Carregar Modelos e Dados Pré-computados ---
    logger.info("Carregando modelos e dados pré-computados...")
    classifier = joblib.load(CLASSIFIER_PATH)
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
        # Chave para identificar itens já processados (ARQUIVO + Nº)
        df_final['chave'] = df_final['ARQUIVO'].astype(str) + "_" + df_final['Nº'].astype(str)
        existing_keys = set(df_final['chave'])
    else:
        df_final = pd.DataFrame()
        existing_keys = set()

    # Filtra apenas os itens que ainda não foram processados
    df_edital['chave'] = df_edital['ARQUIVO'].astype(str) + "_" + df_edital['Nº'].astype(str)
    df_novos_itens = df_edital[~df_edital['chave'].isin(existing_keys)].copy()

    if df_novos_itens.empty:
        logger.info("✅ Nenhum item novo para processar. O arquivo de saída já está atualizado.")
        # Mesmo sem itens novos, aplica o estilo caso o arquivo exista
        if os.path.exists(CAMINHO_SAIDA):
            save_styled_excel(CAMINHO_SAIDA)
        return

    logger.info(f"Encontrados {len(df_novos_itens)} novos itens para processar.")
    processamento_ocorreu = False

    # --- Loop de Processamento ---
    for idx, item_edital in df_novos_itens.iterrows():
        processamento_ocorreu = True
        item_idx_num = df_novos_itens.index.get_loc(idx) + 1
        logger.info(f"\n--- Processando item {item_idx_num}/{len(df_novos_itens)}: {item_edital['DESCRICAO'][:70]}...")
        
        # ETAPA 1: CLASSIFICAÇÃO RÁPIDA COM MODELO ML
        item_desc = str(item_edital['DESCRICAO'])
        predicted_subcategory = classifier.predict([item_desc])[0]
        logger.info(f"   [ML] Subcategoria prevista: '{predicted_subcategory}'")

        # ETAPA 2: BUSCA SEMÂNTICA COM EMBEDDINGS
        df_filtered_products = df_products[df_products['subcategoria'] == predicted_subcategory]
        
        result_row = item_edital.to_dict()

        if df_filtered_products.empty:
            logger.warning("   Nenhum produto encontrado na subcategoria prevista.")
            result_row['STATUS'] = 'Nenhum produto na subcategoria'
            result_row['COMPATIBILIDADE_SCORE'] = 0
        else:
            filtered_indices = df_filtered_products.index.tolist()
            filtered_embeddings = product_embeddings[filtered_indices]

            item_embedding = st_model.encode(item_desc, convert_to_tensor=True)
            cos_scores = util.cos_sim(item_embedding, filtered_embeddings)[0]
            
            top_k_candidates = min(SEMANTIC_SEARCH_TOP_K, len(df_filtered_products))
            top_results = np.argpartition(-cos_scores.cpu().numpy(), range(top_k_candidates))[:top_k_candidates]
            
            candidate_indices = [filtered_indices[i] for i in top_results]
            df_candidates = df_products.iloc[candidate_indices]
            
            logger.info(f"   [ML] {len(df_candidates)} candidatos encontrados via busca semântica.")

            # ETAPA 3: VALIDAÇÃO FINAL COM LLM
            ai_result = get_best_match_from_ai(item_edital, df_candidates)
            
            best_match = ai_result.get("best_match")
            if best_match:
                score = best_match.get('Compatibilidade_score', 0)
                logger.info(f"   [IA] ✅ Match encontrado: {best_match.get('Marca')} {best_match.get('Modelo')} (Score: {score})")
                result_row['STATUS'] = 'Match Encontrado'
                result_row['MARCA_SUGERIDA'] = best_match.get('Marca')
                result_row['MODELO_SUGERIDO'] = best_match.get('Modelo')
                result_row['CUSTO_FORNECEDOR'] = best_match.get('Valor')
                result_row['DESCRICAO_FORNECEDOR'] = best_match.get('Descricao_fornecedor')
                result_row['ANALISE_COMPATIBILIDADE'] = best_match.get('Compatibilidade_analise')
                result_row['COMPATIBILIDADE_SCORE'] = score
            else:
                logger.warning(f"   [IA] ❌ Nenhum match compatível encontrado. Motivo: {ai_result.get('reasoning')}")
                result_row['STATUS'] = 'Nenhum Match Compatível'
                result_row['MOTIVO_INCOMPATIBILIDADE'] = ai_result.get('reasoning')
                result_row['COMPATIBILIDADE_SCORE'] = 0
        
        # --- Salvamento Incremental ---
        df_final = pd.concat([df_final, pd.DataFrame([result_row])], ignore_index=True)
        try:
            # Salva a versão não estilizada incrementalmente
            df_final.drop(columns=['chave'], inplace=True, errors='ignore')
            df_final.to_excel(CAMINHO_SAIDA, index=False)
            logger.info(f"   💾 Progresso salvo. {len(df_final)} itens no arquivo de saída.")
        except Exception as e:
            logger.error(f"   ❌ Falha ao salvar o arquivo Excel incrementalmente: {e}")

        time.sleep(5)

    # --- Estilização Final ---
    # Apenas executa a estilização se houver um arquivo de saída para processar
    if processamento_ocorreu or (not df_novos_itens.empty):
        logger.info("✅ Processamento de todos os itens concluído.")
        save_styled_excel(CAMINHO_SAIDA)
    elif not os.path.exists(CAMINHO_SAIDA):
        logger.info("Nenhum item foi processado e nenhum arquivo de saída existe. Encerrando.")


if __name__ == "__main__":
    main()
