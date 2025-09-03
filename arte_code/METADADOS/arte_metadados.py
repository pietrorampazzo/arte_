
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
import google.api_core.exceptions as google_exceptions
import re
import json
import hashlib
from dotenv import load_dotenv

# =====================
# CONFIGURAÇÕES BÁSICAS
# =====================
# --- Path Configuration ---
# Makes the script robust by building absolute paths from the project root.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
CAMINHO_DADOS = r"C:\Users\pietr\OneDrive\.vscode\arte_\DOWNLOADS\PRODUTOS\produtos_summary.xlsx"
PASTA_SAIDA = r'DOWNLOADS/PRODUTOS/'
ARQUIVO_SAIDA = os.path.join(PASTA_SAIDA, "categoria_sonnet.xlsx")

# --- LLM Config ---
# A chave de API agora deve ser carregada de um arquivo .env para segurança.
load_dotenv()

# O script tentará os modelos nesta ordem. Se um falhar por cota, ele passa para o próximo.
# Usando nomes padrão da API para garantir compatibilidade.
LLM_MODELS_FALLBACK = [        
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.5-pro",
    "gemini-1.5-flash",  
]
LLM_MODEL_PRIMARY = LLM_MODELS_FALLBACK[0]

# Parâmetros de Processamento
BATCH_SIZE = 30  # Tamanho do batch para chamadas ao LLM
MAX_RETRIES = 3  # Número de tentativas em caso de erro
TEMPO = 10  # Delay (em segundos) entre chamadas de BATCH de categorização.

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# =====================
# FUNÇÕES DE APOIO
# =====================
def configurar_llm():
    """Configura a API do Google Generative AI com a chave do .env."""
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    if not GOOGLE_API_KEY:
        logger.error("Chave de API do Google (GOOGLE_API_KEY) não encontrada no arquivo .env.")
        raise ValueError("GOOGLE_API_KEY não configurada.")
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        logger.info(f"API do Google configurada. Modelo principal: '{LLM_MODEL_PRIMARY}'.")
    except Exception as e:
        logger.error(f"Falha ao configurar a API do Google. Verifique sua API Key. Erro: {e}")
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

def gerar_conteudo_com_fallback(prompt: str, modelos: list[str]) -> str | None:
    """
    Tenta gerar conteúdo usando uma lista de modelos em ordem de preferência.
    Se um modelo falhar por cota (ResourceExhausted), tenta o próximo.

    Args:
        prompt: O prompt a ser enviado para a API.
        modelos: A lista de nomes de modelos para tentar em sequência.

    Returns:
        O texto da resposta da API em caso de sucesso, ou None se todos falharem.
    """
    for nome_modelo in modelos:
        try:
            logger.info(f"Tentando chamada à API com o modelo: {nome_modelo}...")
            model = genai.GenerativeModel(nome_modelo)
            response = model.generate_content(prompt)
            logger.info(f"✅ Sucesso com o modelo '{nome_modelo}'.")
            return response.text
        except google_exceptions.ResourceExhausted as e:
            logger.warning(f"⚠️ Cota excedida para o modelo '{nome_modelo}'. Tentando o próximo da lista.")
            time.sleep(5)  # Pausa para não sobrecarregar o próximo modelo imediatamente
            continue
        except Exception as e:
            # Para outros erros (ex: prompt inválido, erro de servidor), é melhor parar e registrar.
            logger.error(f"❌ Erro inesperado com o modelo '{nome_modelo}': {e}")
            # Não continua para o próximo modelo, pois o erro pode não ser de cota.
            return None

    logger.error("❌ FALHA TOTAL: Todos os modelos na lista de fallback falharam. Prompt não processado.")
    return None

def curar_descricoes_em_batch_llm(batch_produtos: list[dict]) -> list[str]:
    """Usa o LLM com fallback para curar uma lista de descrições de produtos em batch."""
    produtos_json = json.dumps(batch_produtos, ensure_ascii=False, indent=2)

    prompt = f"""Você é um especialista em catalogação de produtos musicais e de áudio.
Sua tarefa é criar uma descrição técnica concisa para CADA produto na lista JSON abaixo.

**Regras Essenciais para CADA produto:**
1. **Foco em Dados:** Liste apenas especificações técnicas concretas e verificáveis (ex: material, dimensões, tipo de conexão). Use o Google para confirmar as informações.
2. **Sem "Encheção":** NÃO inclua opiniões, marketing, ou frases vagas.
3. **Omissão é Chave:** Se não encontrar uma informação com certeza, não a mencione.
4. **Formato Limpo:** Apresente as especificações como uma lista de características separadas por vírgulas.
5. **Instrução:** Complete a descrição com: tipo do produto e suas principais características técnicas.

**Exemplo de Descrição Curada:**
- Produto: "Fone de Ouvido XYZ"
- Descrição Curada: "Fone de ouvido over-ear, driver de 40mm, resposta de frequência 20Hz-20kHz, impedância 32 ohms, cabo destacável de 1.2m." 

**ENTRADA (Lista de {len(batch_produtos)} produtos):**
{produtos_json}

**SAÍDA (Responda APENAS com uma lista de objetos JSON, um para cada produto, na mesma ordem da entrada. Mantenha o 'id' original):**
[
  {{
    "id": "<id_do_produto_original_1>",
    "descricao_curada": "<descrição_técnica_concisa_para_o_produto_1>"
  }},
  ...
]
"""
    for attempt in range(MAX_RETRIES):
        response_text = gerar_conteudo_com_fallback(prompt, LLM_MODELS_FALLBACK)
        if response_text:
            parsed_response = parse_llm_response(response_text)
            if parsed_response and isinstance(parsed_response, list) and len(parsed_response) == len(batch_produtos):
                # Sucesso! Garante a ordem correta usando o ID.
                response_map = {item.get('id'): item.get('descricao_curada', '') for item in parsed_response}
                # Retorna as descrições na ordem original do batch de entrada
                ordered_descriptions = [response_map.get(prod['id'], prod['descricao']) for prod in batch_produtos]
                return ordered_descriptions
            else:
                logger.warning(f"Tentativa {attempt + 1}: Resposta da curadoria em batch inválida ou com contagem incorreta de itens.")
        else:
            logger.error(f"Falha na chamada da API de curadoria em batch (tentativa {attempt + 1}/{MAX_RETRIES}).")

        if attempt < MAX_RETRIES - 1:
            time.sleep(TEMPO)

    logger.error(f"Falha ao curar batch após {MAX_RETRIES} tentativas. Usando descrições originais para este batch.")
    # Retorna as descrições originais do batch em caso de falha total
    return [prod['descricao'] for prod in batch_produtos]

def processar_batch_llm(batch_descricoes: list[str]) -> list[dict]:
    """Envia um batch de descrições para o LLM e processa a resposta."""
    prompt = (
        "Você é um especialista em categorização de produtos para um e-commerce de instrumentos musicais e áudio.\n"
        "Sua tarefa é classificar cada descrição de produto fornecida usando ESTRITAMENTE as categorias e subcategorias definidas abaixo.\n\n"
        "**ESTRUTURA DE CATEGORIAS (USE APENAS ESTAS):**\n"

        "EQUIPAMENTO_SOM : amplificador,caixa de som,cubo para guitarra\n"
        "INSTRUMENTO_CORDA: violino, viola, violão, guitarra, baixo, violoncelo\n"
        "INSTRUMENTO_PERCUSSAO: afuché, bateria, bombo, bumbo, caixa de guerra, ganza, pandeiro, quadriton, reco reco, surdo, tambor, tarol, timbales\n"
        "INSTRUMENTO_SOPRO: trompete, bombardino, trompa, trombone, tuba,sousafone, clarinete, saxofone, flauta, tuba bombardão,flugelhorn,euphonium\n"
        "INSTRUMENTO_TECLAS: piano, teclado digital, glockenspiel, metalofone\n"
        "ACESSORIO_CORDA :arco, cavalete, corda, corda, kit nut, kit rastilho, \n"
        "ACESSORIO_GERAL :bag,banco,carrinho prancha,estante de partitura, suporte\n"
        "ACESSORIO_PERCURSSAO :baqueta,carrilhão,esteira,Máquina de Hi Hat,Pad para Bumbo,parafuso,pedal de bumbo,pele,prato,sino,talabarte,triângulo\n"
        "ACESSORIO_SOPRO : graxa,oleo lubrificante,palheta de saxofone/clarinete\n"
        "EQUIPAMENTO_AUDIO : fone de ouvido,globo microfone,Interface de guitarra,pedal,mesa de som,microfone\n"
        "EQUIPAMENTO_CABO : cabo CFTV, cabo de rede, Medusa, switch, cabo_musical\n"
        
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
        response_text = gerar_conteudo_com_fallback(prompt, LLM_MODELS_FALLBACK)

        if response_text:
            parsed_response = parse_llm_response(response_text)
            if parsed_response:
                return parsed_response
            else:
                logger.warning(f"Tentativa {attempt + 1}: Resposta do LLM não continha um JSON válido.")
        else:
            logger.error(f"Falha na chamada da API de categorização (tentativa {attempt + 1}/{MAX_RETRIES}).")

        if attempt < MAX_RETRIES - 1:
            time.sleep(TEMPO)

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
    configurar_llm()  # Apenas configura a API, não retorna mais o modelo
    
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
        logger.info(f"Iniciando processamento de {len(df_to_process)} novos produtos.")

        # --- ETAPA 3.1: CURADORIA DA DESCRIÇÃO (NOVO) ---
        logger.info(f"Iniciando etapa de CURADORIA EM BATCH para {len(df_to_process)} produtos.")
        curated_descriptions_all = []
        # Prepara os dados para o batch, incluindo o ID para remapeamento
        produtos_para_curar = df_to_process.apply(
            lambda row: {
                'id': row['ID_PRODUTO'],
                'marca': row.get('MARCA', 'N/A'),
                'modelo': row.get('MODELO', 'N/A'),
                'descricao': clean_html(row['DESCRICAO'])
            }, axis=1
        ).tolist()

        for i in tqdm(range(0, len(produtos_para_curar), BATCH_SIZE), desc="Curando descrições em batch"):
            batch_produtos = produtos_para_curar[i:i + BATCH_SIZE]
            curated_batch = curar_descricoes_em_batch_llm(batch_produtos)
            curated_descriptions_all.extend(curated_batch)
            time.sleep(TEMPO)

        df_to_process['DESCRICAO_CURADA'] = curated_descriptions_all

        # --- ETAPA 3.2: CATEGORIZAÇÃO EM BATCH (usando descrições curadas) ---
        logger.info("Iniciando etapa de categorização em batch.")
        metadados_all = []
        descricoes_para_categorizar = df_to_process['DESCRICAO_CURADA'].tolist()

        for i in tqdm(range(0, len(descricoes_para_categorizar), BATCH_SIZE), desc="Categorizando produtos"):
            batch_descricoes = descricoes_para_categorizar[i:i + BATCH_SIZE]
            metadados = processar_batch_llm(batch_descricoes)
            time.sleep(TEMPO)
            if len(metadados) != len(batch_descricoes):
                logger.warning(f"Inconsistência no batch {i}. Esperado: {len(batch_descricoes)}, Recebido: {len(metadados)}. Preenchendo com erro.")
                metadados = [{'CATEGORIA_PRINCIPAL': 'ERRO_ALINHAMENTO', 'SUBCATEGORIA': 'ERRO_ALINHAMENTO'}] * len(batch_descricoes)
            metadados_all.extend(metadados)

        df_metadados = pd.DataFrame(metadados_all)
        df_to_process.reset_index(drop=True, inplace=True)
        df_metadados.reset_index(drop=True, inplace=True)

        df_newly_processed = pd.concat([df_to_process, df_metadados], axis=1)
        df_newly_processed['DESCRICAO'] = df_newly_processed['DESCRICAO_CURADA'] # Substitui a descrição original pela curada
        df_newly_processed = df_newly_processed.drop(columns=['DESCRICAO_CURADA'])

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