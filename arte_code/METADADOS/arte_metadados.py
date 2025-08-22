"""
INDEXADOR OTIMIZADO DE PRODUTOS MUSICAIS
-----------------------------------------
Fluxo: base_produtos.xlsx → Limpeza → LLM (com Categorias Definidas) → Validação → Metadados Unificados → Saída Excel.
Versão: 3.0
"""

import os
import time
import logging
import pandas as pd
from tqdm import tqdm
import google.generativeai as genai
import re
import json
import hashlib

# =====================
# CONFIGURAÇÕES BÁSICAS
# =====================
# --- Path Configuration ---
# Makes the script robust by building absolute paths from the project root.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
CAMINHO_DADOS = r'C:\Users\pietr\OneDrive\.vscode\arte_\base_consolidada.xlsx'
PASTA_SAIDA = r'C:\Users\pietr\OneDrive\.vscode\arte_\sheets\RESULTADO'
ARQUIVO_SAIDA = os.path.join(PASTA_SAIDA, "produtos_categorizados_v3.xlsx")

# LLM Config
# ATENÇÃO: Substitua pela sua chave de API. Não compartilhe esta chave.
GOOGLE_API_KEY = 'AIzaSyBdrzcton2jUCv5PSaXE38UCp-l8O42Fvc'
LLM_MODEL = "gemini-2.5-flash"  # Modelo eficiente

# Parâmetros
BATCH_SIZE = 50  # Tamanho do batch para chamadas ao LLM
MAX_RETRIES = 3  # Número de tentativas em caso de erro
TEMPO = 15 

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# =====================
# FUNÇÕES DE APOIO
# =====================
def configurar_llm():
    """Configura e inicializa o modelo de IA generativo."""
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel(LLM_MODEL)
        logger.info(f"Modelo LLM '{LLM_MODEL}' configurado com sucesso.")
        return model
    except Exception as e:
        logger.error(f"Falha ao configurar o LLM. Verifique sua API Key. Erro: {e}")
        raise

def clean_html(raw_html):
    """Remove tags HTML de uma string."""
    clean_text = re.sub('<[^<]+?>', '', str(raw_html))
    return clean_text.strip()

def generate_product_id(row):
    """Gera um ID único e consistente para um produto, baseado em colunas chave."""
    # Usar uma tupla de valores de colunas específicas garante um ID estável.
    # .get() previne erros se uma coluna não existir.
    unique_str = f"{row.get('MARCA', '')}|{row.get('MODELO', '')}|{row.get('DESCRICAO', '')}"
    return hashlib.md5(unique_str.encode()).hexdigest()

def parse_llm_response(response_text):
    """Extrai o conteúdo JSON de uma resposta do LLM, mesmo com texto adicional."""
    match = re.search(r'\[.*\]', response_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            logger.error("Falha ao decodificar JSON da resposta do LLM.")
            return None
    logger.warning("Nenhum JSON válido encontrado na resposta do LLM.")
    return None

def processar_batch_llm(model, batch_descricoes):
    """Envia um batch de descrições para o LLM e processa a resposta."""
    prompt = (
        "Você é um especialista em categorização de produtos para um e-commerce de instrumentos musicais e áudio.\n"
        "Sua tarefa é classificar cada descrição de produto fornecida usando ESTRITAMENTE as categorias e subcategorias definidas abaixo.\n\n"
        "**ESTRUTURA DE CATEGORIAS (USE APENAS ESTAS):**\n"
        "- **INSTRUMENTO_SOPRO**: trompete, bombardino, trompa, trombone, tuba, sousafone, clarinete, saxofone, flauta\n"
        "- **INSTRUMENTO_PERCUSSAO**: bateria, bumbo, timbales, timpano, surdo, tarol, caixa de guerra, quadriton, tambor, afuché\n"
        "- **INSTRUMENTO_CORDA**: violino, viola, violão, guitarra, baixo, violoncelo\n"
        "- **INSTRUMENTO_TECLAS**: piano, Lira, teclado digital, Glockenspiel\n"
        "- **ACESSORIO_SOPRO**: bocal, Lubrificante, boquilha, surdina, graxa, Lever Oil, oleo lubrificante, palheta de saxofone/clarinete\n"
        "- **ACESSORIO_PERCUSSAO**: baqueta, Máquina de Hi Hat, talabarte, pele, esteira, prato, triângulo, carrilhão, sino\n"
        "- **ACESSORIO_CORDA**: corda, arco, cavalete\n"
        "- **ACESSORIO_GERAL**: estante de partitura, suporte, banco, bag\n"
        "- **EQUIPAMENTO_SOM**: caixa de som, amplificador, cubo para guitarra\n"
        "- **EQUIPAMENTO_AUDIO**: microfone, mesa áudio, mesa de som, fone de ouvido\n"
        "- **EQUIPAMENTO_CABO**: cabo HDMI, xlr M/F, P10, P2xP10, Medusa, caixa medusa, Cabo CAT5e,cabo de rede, cabo CFTV \n"
        "- **OUTROS**: use esta categoria apenas se o produto não se encaixar em nenhuma das categorias acima.\n\n"
        "**TAREFA:**\n"
        "Para CADA descrição na lista de entrada (há exatamente {len(batch_descricoes)} itens), determine a `CATEGORIA_PRINCIPAL` e a `SUBCATEGORIA`.\n"
        "Retorne EXATAMENTE {len(batch_descricoes)} objetos JSON, um por descrição, na ordem da lista.\n\n"
        "**ENTRADA (Lista numerada de descrições):**\n"
        + "\n".join([f"{idx+1}. {desc}" for idx, desc in enumerate(batch_descricoes)]) + "\n\n"  # Numerar para ajudar o LLM
        "**SAÍDA (Responda APENAS com uma lista de objetos JSON, sem texto extra):**\n"
        "[\n"
        "  {\"CATEGORIA_PRINCIPAL\": \"<categoria_definida>\", \"SUBCATEGORIA\": \"<nome_do_produto>\"},\n"
        "  ...\n"  # Exemplo com reticências para indicar repetição
        "]"

    )
    
    for attempt in range(MAX_RETRIES):
        try:
            response = model.generate_content(prompt)
            parsed_response = parse_llm_response(response.text)
            if parsed_response: return parsed_response
            else: logger.warning(f"Tentativa {attempt + 1}: Resposta do LLM não continha um JSON válido.")
        except Exception as e:
            logger.error(f"Erro na chamada da API (tentativa {attempt + 1}/{MAX_RETRIES}): {e}")
    
    logger.error(f"Falha ao processar batch após {MAX_RETRIES} tentativas.")
    return [{'CATEGORIA_PRINCIPAL': 'ERRO_PROCESSAMENTO', 'SUBCATEGORIA': 'ERRO_PROCESSAMENTO'}] * len(batch_descricoes)

# =====================
# FLUXO PRINCIPAL
# =====================
def processar_produtos():
    """
    Função principal que orquestra a leitura, processamento e gravação dos dados.
    Implementa uma lógica de atualização incremental para processar apenas produtos novos ou alterados.
    """
    os.makedirs(PASTA_SAIDA, exist_ok=True)
    model = configurar_llm()
    
    # 1. Carregar e preparar a base de produtos de origem
    logger.info(f"Carregando dados de origem de: {CAMINHO_DADOS}")
    df_source = pd.read_excel(CAMINHO_DADOS)
    # Padroniza nomes das colunas para MAIÚSCULAS para consistência
    df_source.columns = [str(c).strip().upper() for c in df_source.columns]

    # Gera IDs únicos para a base de produtos atual
    df_source['ID_PRODUTO'] = df_source.apply(generate_product_id, axis=1)
    df_source = df_source.dropna(subset=['DESCRICAO']).reset_index(drop=True)

    df_to_process = pd.DataFrame()
    df_existing_processed = pd.DataFrame()

    # 2. Verificar se já existe uma base processada para fazer a comparação
    if os.path.exists(ARQUIVO_SAIDA):
        logger.info(f"Arquivo de metadados existente encontrado. Verificando atualizações...")
        df_processed = pd.read_excel(ARQUIVO_SAIDA)
        
        # --- VERIFICAÇÃO DE COMPATIBILIDADE ---
        # Se o arquivo antigo não tiver a coluna 'ID_PRODUTO', força um reprocessamento completo.
        if 'ID_PRODUTO' not in df_processed.columns:
            logger.warning("O arquivo de metadados existente é de uma versão antiga (sem ID_PRODUTO).")
            logger.warning("Será feito um reprocessamento completo de toda a base de produtos para atualizar.")
            df_to_process = df_source.copy()
            df_existing_processed = pd.DataFrame() # Reseta os dados existentes
        else:
            # Lógica de sincronização padrão
            source_ids = set(df_source['ID_PRODUTO'])
            processed_ids = set(df_processed['ID_PRODUTO'])

            new_ids = source_ids - processed_ids
            deleted_ids = processed_ids - source_ids

            if new_ids:
                logger.info(f"Encontrados {len(new_ids)} novos produtos para processar.")
                df_to_process = df_source[df_source['ID_PRODUTO'].isin(new_ids)].copy()
            else:
                logger.info("Nenhum produto novo para processar.")

            if deleted_ids:
                logger.info(f"Encontrados {len(deleted_ids)} produtos removidos da base. Eles serão excluídos.")

            # Mantém apenas os produtos que ainda existem e já foram processados
            df_existing_processed = df_processed[~df_processed['ID_PRODUTO'].isin(deleted_ids)]
            logger.info(f"{len(df_existing_processed)} produtos existentes serão mantidos.")
    else:
        logger.info("Nenhum arquivo de metadados existente. Processando todos os produtos da base.")
        df_to_process = df_source.copy()

    # 3. Processar apenas os produtos novos com o LLM
    if not df_to_process.empty:
        logger.info(f"Iniciando processamento de {len(df_to_process)} produtos com o LLM.")
        df_to_process['DESCRICAO_LIMPA'] = df_to_process['DESCRICAO'].apply(clean_html)

        metadados_all = []
        for i in tqdm(range(0, len(df_to_process), BATCH_SIZE), desc="Processando batches de produtos"):
            batch = df_to_process.iloc[i:i + BATCH_SIZE]
            descricoes_limpas = batch['DESCRICAO_LIMPA'].tolist()
            metadados = processar_batch_llm(model, descricoes_limpas)
            time.sleep(TEMPO)
            if len(metadados) != len(batch):
                logger.warning(f"Inconsistência no batch {i}. Esperado: {len(batch)}, Recebido: {len(metadados)}. Preenchendo com erro.")
                metadados = [{'CATEGORIA_PRINCIPAL': 'ERRO_ALINHAMENTO', 'SUBCATEGORIA': 'ERRO_ALINHAMENTO'}] * len(batch)
            metadados_all.extend(metadados)

        df_metadados = pd.DataFrame(metadados_all)
        df_to_process.reset_index(drop=True, inplace=True)
        df_metadados.reset_index(drop=True, inplace=True)

        df_newly_processed = pd.concat([df_to_process, df_metadados], axis=1)
        df_newly_processed = df_newly_processed.drop(columns=['DESCRICAO_LIMPA'])

        # Combina os produtos existentes com os recém-processados
        df_final = pd.concat([df_existing_processed, df_newly_processed], ignore_index=True)
    else:
        logger.info("Nenhum produto novo para processar. A base final será a base existente (com exclusões).")
        df_final = df_existing_processed

    # 4. Formatar e salvar o arquivo de saída final
    if not df_final.empty:
        logger.info("Formatando colunas para o padrão de saída final.")

        rename_map = {'CATEGORIA_PRINCIPAL': 'categoria_principal', 'SUBCATEGORIA': 'subcategoria'}
        df_final = df_final.rename(columns=rename_map)

        ordem_final_colunas = ['ID_PRODUTO', 'categoria_principal', 'subcategoria', 'MARCA', 'MODELO', 'VALOR', 'DESCRICAO']

        # Garante que todas as colunas existam, preenchendo com NA se necessário
        for col in ordem_final_colunas:
            if col not in df_final.columns:
                df_final[col] = pd.NA

        # Reordena e remove colunas extras
        df_final = df_final[ordem_final_colunas]

        logger.info(f"Salvando arquivo final com {len(df_final)} produtos em: {ARQUIVO_SAIDA}")
        df_final.to_excel(ARQUIVO_SAIDA, index=False)
        logger.info("Operação concluída com sucesso!")
    else:
        if os.path.exists(ARQUIVO_SAIDA):
            os.remove(ARQUIVO_SAIDA)
            logger.info(f"Todos os produtos foram removidos. Arquivo '{ARQUIVO_SAIDA}' deletado.")
        else:
            logger.info("Nenhum produto para salvar. O arquivo de saída não será criado.")

# =====================
# EXECUTAR O SCRIPT
# =====================
if __name__ == "__main__":
    processar_produtos()