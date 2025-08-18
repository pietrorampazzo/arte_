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

# =====================
# CONFIGURAÇÕES BÁSICAS
# =====================
CAMINHO_DADOS = r"base_produtos.xlsx"  # Caminho do Excel de entrada
PASTA_SAIDA = "RESULTADO"  # Pasta para salvar o arquivo de saída
ARQUIVO_SAIDA = os.path.join(PASTA_SAIDA, "produtos_categorizados.xlsx")  # Arquivo Excel final

# LLM Config
# ATENÇÃO: Substitua pela sua chave de API. Não compartilhe esta chave.
GOOGLE_API_KEY = 'AIzaSyBdrzcton2jUCv5PSaXE38UCp-l8O42Fvc'
LLM_MODEL = "gemini-2.0-flash-lite"  # Modelo eficiente

# Parâmetros
BATCH_SIZE = 5  # Tamanho do batch para chamadas ao LLM
MAX_RETRIES = 3  # Número de tentativas em caso de erro

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
    """Função principal que orquestra a leitura, processamento e gravação dos dados."""
    os.makedirs(PASTA_SAIDA, exist_ok=True)
    model = configurar_llm()
    
    logger.info(f"Carregando dados de: {CAMINHO_DADOS}")
    df = pd.read_excel(CAMINHO_DADOS)
    df_original = df.dropna(subset=['DESCRICAO']).reset_index(drop=True)
    df_original['DESCRICAO_LIMPA'] = df_original['DESCRICAO'].apply(clean_html)
    
    metadados_all = []
    
    for i in tqdm(range(0, len(df_original), BATCH_SIZE), desc="Processando batches de produtos"):
        batch = df_original.iloc[i:i + BATCH_SIZE]
        descricoes_limpas = batch['DESCRICAO_LIMPA'].tolist()
        metadados = processar_batch_llm(model, descricoes_limpas)
        time.sleep(30)  # Pausa para evitar sobrecarga
        if len(metadados) != len(batch):
            logger.warning(f"Inconsistência no batch {i}. Esperado: {len(batch)}, Recebido: {len(metadados)}. Preenchendo com erro.")
            metadados = [{'CATEGORIA_PRINCIPAL': 'ERRO_ALINHAMENTO', 'SUBCATEGORIA': 'ERRO_ALINHAMENTO'}] * len(batch)
        metadados_all.extend(metadados)
    
    logger.info("Processamento de todos os batches concluído.")
    
    df_metadados = pd.DataFrame(metadados_all)
    df_final = pd.concat([df_original, df_metadados], axis=1)
    df_final = df_final.drop(columns=['DESCRICAO_LIMPA'])
    
    # ===================================================================================
    # AJUSTE FINO: Renomeia e reordena as colunas para o formato de saída final
    # ===================================================================================
    logger.info("Formatando colunas para o padrão de saída final.")
    
    # 1. Mapeamento para renomear as colunas
    rename_map = {
        'CATEGORIA_PRINCIPAL': 'categoria_principal',
        'SUBCATEGORIA': 'subcategoria',
        'Marca': 'MARCA',
        'Modelo': 'MODELO',
        'Valor': 'VALOR'
    }
    df_final = df_final.rename(columns=rename_map)
    
    # 2. Lista com a ordem exata das colunas desejadas
    ordem_final_colunas = [
        'categoria_principal',
        'subcategoria',
        'MARCA',
        'MODELO',
        'VALOR',
        'DESCRICAO'
    ]
    
    # 3. Reordena o DataFrame
    df_final = df_final[ordem_final_colunas]
    
    logger.info(f"Salvando arquivo final em: {ARQUIVO_SAIDA}")
    df_final.to_excel(ARQUIVO_SAIDA, index=False)
    logger.info("Operação concluída com sucesso!")

# =====================
# EXECUTAR O SCRIPT
# =====================
if __name__ == "__main__":
    processar_produtos()