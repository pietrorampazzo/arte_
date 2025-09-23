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
from openpyxl import load_workbook
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
CAMINHO_DADOS = r"C:\Users\pietr\OneDrive\.vscode\arte_\DOWNLOADS\PRODUTOS\ultra_base.xlsx"
PASTA_SAIDA = r'C:\Users\pietr\OneDrive\.vscode\arte_\DOWNLOADS\METADADOS'
ARQUIVO_SAIDA = os.path.join(PASTA_SAIDA, "categoria_GPT.xlsx")

# --- LLM Config ---
# A chave de API agora deve ser carregada de um arquivo .env para segurança.
load_dotenv()

# O script tentará os modelos nesta ordem. Se um falhar por cota, ele passa para o próximo.
# Usando nomes padrão da API para garantir compatibilidade.
LLM_MODELS_FALLBACK = [  
    "gemini-2.0-flash-lite",    
    "gemini-2.5-flash",
    "gemini-1.5-flash",  
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
]
LLM_MODEL_PRIMARY = LLM_MODELS_FALLBACK[0]

# Parâmetros de Processamento
BATCH_SIZE = 15  # Tamanho do batch para chamadas ao LLM
MAX_RETRIES = 3  # Número de tentativas em caso de erro
TEMPO = 10  # Delay (em segundos) entre chamadas de BATCH de categorização.

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Estrutura de Categorias ---
# Centralizar as categorias facilita a manutenção e a consistência com o prompt.
CATEGORIAS_PRODUTOS = {
        "EQUIPAMENTO_SOM" : ["caixa_ativa", "caixa_passiva", "caixa_portatil", "line_array", "subwoofer_ativo", "subwoofer_passivo", "amplificador_potencia", "cabeçote_amplificado", "coluna_vertical", "monitor_de_palco"],
        "EQUIPAMENTO_AUDIO" : ["microfone_dinamico", "microfone_condensador", "microfone_lapela", "microfone_sem_fio", "microfone_instrumento", "mesa_analogica", "mesa_digital", "interface_audio", "processador_dsp", "fone_monitor", "sistema_iem", "pedal_efeitos"],
        "INSTRUMENTO_CORDA" : ["violao", "guitarra", "contra_baixo", "violino", "violoncelo", "ukulele", "cavaquinho"],
        "INSTRUMENTO_PERCUSSAO" : ["bateria_acustica", "bateria_eletronica", "repinique", "rocari", "tantan", "rebolo","surdo_mao", "cuica", "zabumba", "caixa_guerra", "bombo_fanfarra", "lira_marcha","tarol", "malacacheta", "caixa_bateria", "pandeiro", "tamborim","reco_reco", "agogô", "triangulo", "chocalho", "afuche", "cajon", "bongo", "conga", "djembé", "timbal", "atabaque", "berimbau","tam_tam", "caxixi", "carilhao", "xequerê", "prato"],
        "INSTRUMENTO_SOPRO" : ["saxofone", "trompete", "trombone", "trompa", "clarinete", "flauta", "tuba", "flugelhorn", "bombardino", "corneta", "cornetão"],
        "INSTRUMENTO_TECLADO" : ["teclado_digital", "piano_acustico", "piano_digital", "sintetizador", "controlador_midi", "glockenspiel", "metalofone"],
        "ACESSORIO_MUSICAL" : ["banco_teclado", "estante_partitura", "suporte_microfone", "suporte_instrumento", "carrinho_transporte", "case_bag", "afinador", "metronomo", "cabos_audio", "palheta", "cordas", "oleo_lubrificante", "graxa", "surdina", "bocal_trompete", "pele_percussao", "baqueta", "talabarte", "pedal_bumbo", "chimbal_hihat"],
        "EQUIPAMENTO_TECNICO" : ["ssd", "fonte_energia", "switch_rede", "projetor", "drone"]
}

def append_df_to_excel(filename, df, **to_excel_kwargs):
    """Anexa um DataFrame a um arquivo .xlsx existente sem reescrever o arquivo inteiro."""
    with pd.ExcelWriter(filename, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
        # Escreve o DataFrame sem o cabeçalho, começando da primeira linha vazia.
        df.to_excel(writer, header=False, startrow=writer.sheets['Sheet1'].max_row, **to_excel_kwargs)


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
            logger.info(f" Sucesso com o modelo '{nome_modelo}'.")
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

    prompt = f"""Você é um especialista técnico em produtos musicais e de áudio com acesso a bancos de dados técnicos.

**OBJETIVO PRINCIPAL:**
Para CADA produto na lista JSON abaixo, gere uma descrição técnica DETALHADA e ENRIQUECIDA, realizando pesquisa virtual implícita para completar informações faltantes e validar especificações.

**METODOLOGIA DE PESQUISA E VALIDAÇÃO:**
1. Para cada produto, consulte mentalmente especificações técnicas de fabricantes e marketplaces
2. Cross-reference entre pelo menos 2 fontes virtuais para validar dados
3. Complete informações parciais com dados técnicos padrão do segmento
4. Priorize informações de manuais técnicos e fichas de especificação
5. Pesquise em sites confiáveis como Thomann, Sweetwater, Amazon, fabricantes oficiais
6. Se o produto for genérico ou desconhecido, use especificações técnicas padrão do segmento
7. Se a descrição original for muito vaga, use termos técnicos padrão do segmento
8. Mantenha a precisão técnica, evitando suposições não verificadas

**ESTRUTURA DA DESCRIÇÃO ENRIQUECIDA (siga esta ordem):**
[FUNÇÃO PRINCIPAL] - [CATEGORIA TÉCNICA] com [CARACTERÍSTICAS PRINCIPAIS]. 
Especificações técnicas: [DETALHES TÉCNICOS COMPLETOS]. 
Construção: [MATERIAIS E ACABAMENTO]. 
Aplicações: [USOS RECOMENDADOS]. 
Compatibilidade: [EQUIPAMENTOS COMPATÍVEIS].

**REGRAS ESSENCIAIS:**
- INSIRA dados técnicos concretos: dimensões, pesos, materiais, conexões, especificações elétricas
- INCLUA faixas de frequência, sensibilidade, impedância, potência, quando aplicável
- DESTAQUE features únicas e diferenciais técnicos comprovados
- USE terminologia técnica precisa e padrão do mercado
- MENCIONE compatibilidades e requisitos do sistema
- EVITE linguagem de marketing - foque em fatos técnicos verificáveis

**EXEMPLO DE DESCRIÇÃO ENRIQUECIDA:**
Produto: "Microfone Condensador XYZ"
Descrição: "Microfone condensador de estúdio para captação vocal e instrumental com padrão polar cardioide. 
Especificações técnicas: resposta de frequência 20Hz-20kHz, sensibilidade de -32dB, impedância de 250 ohms, 
Relação sinal-ruído de 82dB, máxima pressão sonora de 138dB. 
Construção: corpo em metal zincado, grade de proteção em aço, membrana de 3/4". 
Aplicações: estúdio de gravação, podcasting, vocais, instrumentos acústicos. 
Compatibilidade: requer fonte phantom power 48V, interface de áudio com entrada XLR." 

**ENTRADA (Lista de {len(batch_produtos)} produtos):
{produtos_json}

**SAÍDA (Responda APENAS com uma lista de objetos JSON, um para cada produto, na mesma ordem):**
[
  {{
    "id": "<id_do_produto_original_1>",
    "descricao_enriquecida": "<descrição_técnica_detalhada_completa>",
    "especificacoes_validadas": ["spec1", "spec2", "spec3"]  # lista de specs confirmadas
  }},
  ...
]"""
    for attempt in range(MAX_RETRIES):
        response_text = gerar_conteudo_com_fallback(prompt, LLM_MODELS_FALLBACK)
        if response_text:
            parsed_response = parse_llm_response(response_text)
            if parsed_response and isinstance(parsed_response, list) and len(parsed_response) == len(batch_produtos):
                # Sucesso! Garante a ordem correta usando o ID.
                response_map = {item.get('id'): item.get('descricao_enriquecida', '') for item in parsed_response}
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
        f"Sua tarefa é classificar cada descrição de produto fornecida usando ESTRITAMENTE as categorias e subcategorias definidas abaixo.\n\n"
        "**ESTRUTURA DE CATEGORIAS (USE APENAS ESTAS):**\n"
        f"{json.dumps(CATEGORIAS_PRODUTOS, indent=2, ensure_ascii=False)}\n\n"
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
    Processa produtos em lotes e salva o progresso a cada lote bem-sucedido.
    """
    os.makedirs(PASTA_SAIDA, exist_ok=True)

    # --- Prepara o arquivo de saída ---
    # Se o arquivo não existe, cria com o cabeçalho correto.
    if not os.path.exists(ARQUIVO_SAIDA):
        logger.info(f"Criando novo arquivo de saída: {ARQUIVO_SAIDA}")
        ordem_final_colunas = ['ID_PRODUTO', 'categoria_principal', 'subcategoria', 'MARCA', 'MODELO', 'VALOR', 'DESCRICAO']
        pd.DataFrame(columns=ordem_final_colunas).to_excel(ARQUIVO_SAIDA, index=False)

    configurar_llm()

    # 1. Carregar e preparar a base de produtos de origem
    logger.info(f"Carregando dados de origem de: {CAMINHO_DADOS}")
    df_source = pd.read_excel(CAMINHO_DADOS)
    df_source.columns = [str(c).strip().upper() for c in df_source.columns]
    df_source['ID_PRODUTO'] = df_source.apply(generate_product_id, axis=1)
    df_source = df_source.dropna(subset=['DESCRICAO']).reset_index(drop=True)

    df_to_process = pd.DataFrame()

    # 2. Verificar se já existe uma base processada para fazer a comparação
    logger.info(f"Arquivo de metadados existente encontrado. Verificando atualizações...")
    try:
        df_processed = pd.read_excel(ARQUIVO_SAIDA)
    except Exception as e:
        logger.error(f"Erro ao ler o arquivo Excel existente: {e}. Tratando como se não existisse.")
        df_processed = pd.DataFrame(columns=['ID_PRODUTO']) # Cria um DF vazio para continuar

    if 'ID_PRODUTO' not in df_processed.columns or df_processed.empty:
        if not df_processed.empty:
            logger.warning("O arquivo de metadados existente é de uma versão antiga ou está vazio. Reprocessando tudo.")
            # Recria o arquivo com o cabeçalho correto
            ordem_final_colunas = ['ID_PRODUTO', 'categoria_principal', 'subcategoria', 'MARCA', 'MODELO', 'VALOR', 'DESCRICAO']
            pd.DataFrame(columns=ordem_final_colunas).to_excel(ARQUIVO_SAIDA, index=False)
            logger.info("Arquivo antigo recriado para garantir consistência.")
        df_to_process = df_source.copy()
    else:
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
            logger.info(f"Encontrados {len(deleted_ids)} produtos removidos. Eles serão excluídos da base final.")
            df_cleaned = df_processed[~df_processed['ID_PRODUTO'].isin(deleted_ids)].copy()
            df_cleaned.to_excel(ARQUIVO_SAIDA, index=False)
            logger.info(f"Arquivo atualizado com {len(df_cleaned)} produtos após remoção.")

    # 3. Processar novos produtos em lotes e salvar incrementalmente
    if not df_to_process.empty:
        logger.info(f"Iniciando processamento incremental de {len(df_to_process)} novos produtos.")
        
        produtos_para_processar = df_to_process.to_dict('records')

        for i in tqdm(range(0, len(produtos_para_processar), BATCH_SIZE), desc="Processando e salvando lotes"):
            batch_produtos_dict = produtos_para_processar[i:i + BATCH_SIZE]
            df_batch_to_process = pd.DataFrame(batch_produtos_dict)

            # --- ETAPA 3.1: CURADORIA DO BATCH ---
            logger.info(f"Lote {i//BATCH_SIZE + 1}: Iniciando curadoria de {len(df_batch_to_process)} produtos.")
            produtos_para_curar = df_batch_to_process.apply(
                lambda row: {
                    'id': row['ID_PRODUTO'],
                    'marca': row.get('MARCA', 'N/A'),
                    'modelo': row.get('MODELO', 'N/A'),
                    'descricao': clean_html(row['DESCRICAO'])
                }, axis=1
            ).tolist()
            
            curated_batch = curar_descricoes_em_batch_llm(produtos_para_curar)
            df_batch_to_process['DESCRICAO_CURADA'] = curated_batch
            
            # --- ETAPA 3.2: CATEGORIZAÇÃO DO BATCH ---
            logger.info(f"Lote {i//BATCH_SIZE + 1}: Iniciando categorização.")
            descricoes_para_categorizar = df_batch_to_process['DESCRICAO_CURADA'].tolist()
            metadados = processar_batch_llm(descricoes_para_categorizar)

            if len(metadados) != len(descricoes_para_categorizar):
                logger.error(f"Lote {i//BATCH_SIZE + 1}: Inconsistência no batch. Pulando salvamento deste lote.")
                continue

            df_metadados = pd.DataFrame(metadados)
            df_batch_to_process.reset_index(drop=True, inplace=True)
            df_metadados.reset_index(drop=True, inplace=True)

            df_batch_processed = pd.concat([df_batch_to_process, df_metadados], axis=1)
            df_batch_processed['DESCRICAO'] = df_batch_processed['DESCRICAO_CURADA']
            df_batch_processed = df_batch_processed.drop(columns=['DESCRICAO_CURADA'])

            # --- ETAPA 3.3: SALVAMENTO INCREMENTAL ---
            try:
                rename_map = {'CATEGORIA_PRINCIPAL': 'categoria_principal', 'SUBCATEGORIA': 'subcategoria'}
                df_batch_processed = df_batch_processed.rename(columns=rename_map)
                ordem_final_colunas = ['ID_PRODUTO', 'categoria_principal', 'subcategoria', 'MARCA', 'MODELO', 'VALOR', 'DESCRICAO']

                for col in ordem_final_colunas:
                    if col not in df_batch_processed.columns:
                        df_batch_processed[col] = pd.NA

                df_to_append = df_batch_processed[ordem_final_colunas]

                append_df_to_excel(ARQUIVO_SAIDA, df_to_append, index=False)
                logger.info(f"Lote {i//BATCH_SIZE + 1} processado e anexado ao arquivo de saída.")

            except Exception as e:
                logger.error(f"Erro ao salvar o lote {i//BATCH_SIZE + 1}: {e}. Progresso do lote perdido.")
            
            time.sleep(TEMPO)

    logger.info("Processamento incremental concluído.")

# =====================
# EXECUTAR O SCRIPT
# =====================
if __name__ == "__main__":
    processar_produtos()