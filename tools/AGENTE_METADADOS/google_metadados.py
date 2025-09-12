
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
from dotenv import load_dotenv

# =====================
# CONFIGURAÇÕES BÁSICAS
# =====================
# --- Path Configuration ---
# Makes the script robust by building absolute paths from the project root.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
CAMINHO_DADOS = r'C:\Users\pietr\OneDrive\.vscode\arte_\sheets\PRODUTOS\produtos_o4-mini.xlsx'
PASTA_SAIDA = r'C:\Users\pietr\OneDrive\.vscode\arte_\sheets\RESULTADO_metadados'
ARQUIVO_SAIDA = os.path.join(PASTA_SAIDA, "categoria_o4-mini_v3.xlsx")

# --- LLM Config ---
# A chave de API agora deve ser carregada de um arquivo .env para segurança.
# Crie um arquivo .env na raiz do projeto com a linha: GOOGLE_API_KEY="sua_chave_aqui"
load_dotenv()
LLM_MODEL = "gemini-2.5-flash-lite"  # Modelo eficiente

# Parâmetros
BATCH_SIZE = 50  # Tamanho do batch para chamadas ao LLM
MAX_RETRIES = 3  # Número de tentativas em caso de erro
TEMPO = 5  # Delay entre chamadas de batch de categorização
CURATION_DELAY = 15 # Delay entre chamadas de curadoria para evitar rate limit

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# =====================
# FUNÇÕES DE APOIO
# =====================
def configurar_llm():
    """Configura e inicializa o modelo de IA generativo."""
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    if not GOOGLE_API_KEY:
        logger.error("Chave de API do Google (GOOGLE_API_KEY) não encontrada no arquivo .env.")
        raise ValueError("GOOGLE_API_KEY não configurada.")
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

def curar_descricao_produto_llm(model, marca, modelo, descricao):
    """Usa o LLM para pesquisar e criar uma descrição técnica concisa para um produto."""
    prompt = f"""Você é um especialista em catalogação de produtos musicais e de áudio.
Sua tarefa é criar uma descrição técnica para o produto abaixo, listando APENAS as especificações mais relevantes e confirmadas.
Dê um google no produto usando as informações do produto para analise, priorize o site do fabricante ou de algum revendedor confiavel, para captar as informações reais do produto.
Seu trabalho é fazer uma curadoria digital sobre os produtos, e buscar extidão nas informações.

**Produto para Análise:**
- **Marca:** {marca}
- **Modelo:** {modelo}
- **Descrição Conhecida:** "{descricao}"

**Regras Essenciais:**
1.  **Foco Total em Dados:** Liste apenas especificações técnicas concretas e verificáveis (ex: material, dimensões, tipo de conexão, resposta de frequência, etc.).
2.  **Sem "Encheção":** NÃO inclua opiniões, marketing, frases vagas ou comentários.**ISSO É UMA NORMATIVA** diga apenas coisas voltadas ao produto!
3.  **Omissão é Chave:** Se você não encontrar uma informação com alta certeza, **simplesmente não a mencione**. Não escreva "não encontrado", "desconhecido" ou "N/A". A ausência da informação é preferível.
4.  **Formato Limpo:** Apresente as especificações como uma lista de características separadas por vírgulas.
5.  **Relevância:** Forneça apenas especificações que fazem sentido para o tipo de produto. 

**Exemplo (Violão):**
Tampo em Spruce, laterais e fundo em Mogno, escala em Rosewood, 20 trastes, tarraxas cromadas.

**Exemplo (Microfone):**
Tipo Condensador, Padrão Polar Cardioide, Resposta de Frequência 20Hz-20kHz, Conexão XLR.

**Descrição Técnica Concisa:**"""

    for attempt in range(MAX_RETRIES):
        try:
            response = model.generate_content(prompt)
            curated_desc = response.text.strip()
            if curated_desc:
                return curated_desc
            else:
                logger.warning(f"Tentativa de curadoria {attempt + 1} para '{marca} {modelo}' retornou resposta vazia.")
        except Exception as e:
            logger.error(f"Erro na API de curadoria (tentativa {attempt + 1}/{MAX_RETRIES}) para '{marca} {modelo}': {e}")
            time.sleep(2)
    
    logger.error(f"Falha ao curar a descrição para '{marca} {modelo}' após {MAX_RETRIES} tentativas. Usando descrição original.")
    return descricao

def processar_batch_llm(model, batch_descricoes):
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
        "ACESSORIO_CORDA :arco,cavalete,corda,corda,kit nut,kit rastilho\n"
        "ACESSORIO_GERAL :bag,banco,carrinho prancha,estante de partitura,suporte\n"
        "ACESSORIO_PERCURSSAO :baqueta,carrilhão,esteira,Máquina de Hi Hat,Pad para Bumbo,parafuso,pedal de bumbo,pele,prato,sino,talabarte,triângulo\n"
        "ACESSORIO_SOPRO : graxa,oleo lubrificante,palheta de saxofone/clarinete\n"
        "EQUIPAMENTO_AUDIO : fone de ouvido,globo microfone,Interface de guitarra,pedal,mesa de som,microfone\n"
        "EQUIPAMENTO_CABO : cabo CFTV,cabo de rede,caixa medusa,Medusa,P10,P2xP10,painel de conexão,xlr M/F\n"

        
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
        logger.info(f"Iniciando processamento de {len(df_to_process)} novos produtos.")

        # --- ETAPA 3.1: CURADORIA DA DESCRIÇÃO (NOVO) ---
        logger.info(f"Iniciando etapa de curadoria para {len(df_to_process)} produtos.")
        curated_descriptions = []
        for _, row in tqdm(df_to_process.iterrows(), total=df_to_process.shape[0], desc="Curando descrições de produtos"):
            original_desc = clean_html(row['DESCRICAO'])
            curated_desc = curar_descricao_produto_llm(
                model,
                row.get('MARCA', 'N/A'),
                row.get('MODELO', 'N/A'),
                original_desc
            )
            curated_descriptions.append(curated_desc)
            time.sleep(CURATION_DELAY)
        
        df_to_process['DESCRICAO_CURADA'] = curated_descriptions

        # --- ETAPA 3.2: CATEGORIZAÇÃO EM BATCH ---
        logger.info("Iniciando etapa de categorização em batch.")
        metadados_all = []
        descricoes_para_categorizar = df_to_process['DESCRICAO_CURADA'].tolist()

        for i in tqdm(range(0, len(descricoes_para_categorizar), BATCH_SIZE), desc="Categorizando produtos"):
            batch_descricoes = descricoes_para_categorizar[i:i + BATCH_SIZE]
            metadados = processar_batch_llm(model, batch_descricoes)
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