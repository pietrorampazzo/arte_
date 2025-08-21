"""
INDEXADOR OTIMIZADO DE PRODUTOS MUSICAIS
-----------------------------------------
Sistema robusto de categorização com reprocessamento automático
Versão: 4.0 - Sistema de reprocessamento robusto
"""
###########problema
import os
import time
import logging
import pandas as pd
from tqdm import tqdm
import google.generativeai as genai
import re
import json
import hashlib
from collections import deque

# =====================
# CONFIGURAÇÕES
# =====================

# Caminhos dos arquivos
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
CAMINHO_DADOS = r'C:\Users\pietr\OneDrive\.vscode\arte_\base_consolidada.xlsx'
PASTA_SAIDA = os.path.join(PROJECT_ROOT, "RESULTADO")
ARQUIVO_SAIDA = os.path.join(PASTA_SAIDA, "base_consolidada_categorizada_v3.xlsx")

# Configurações da API
GOOGLE_API_KEY = 'AIzaSyBdrzcton2jUCv5PSaXE38UCp-l8O42Fvc'
LLM_MODEL = "gemini-2.5-flash"

# Parâmetros de processamento
BATCH_SIZE = 250
MAX_RETRIES = 3
MAX_REPROCESS_ATTEMPTS = 5
RETRY_DELAY = 10
REPROCESS_BATCH_SIZE = 50
DELAY_ENTRE_BATCHES = 10

# Configuração de logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =====================
# FUNÇÕES AUXILIARES
# =====================

def configurar_llm():
    """Configura e inicializa o modelo de IA generativo."""
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel(LLM_MODEL)
        logger.info(f"Modelo LLM '{LLM_MODEL}' configurado com sucesso.")
        return model
    except Exception as e:
        logger.error(f"Falha ao configurar o LLM: {e}")
        raise

def limpar_html(texto):
    """Remove tags HTML de uma string."""
    return re.sub('<[^<]+?>', '', str(texto)).strip()

def gerar_id_produto(row):
    """Gera um ID único para um produto baseado em suas características."""
    chave_unica = f"{row.get('MARCA', '')}|{row.get('MODELO', '')}|{row.get('DESCRICAO', '')}"
    return hashlib.md5(chave_unica.encode()).hexdigest()

def extrair_json_resposta(resposta_texto):
    """Extrai o conteúdo JSON de uma resposta do LLM."""
    match = re.search(r'\[.*\]', resposta_texto, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            logger.error("Falha ao decodificar JSON da resposta do LLM.")
            return None
    logger.warning("Nenhum JSON válido encontrado na resposta do LLM.")
    return None

def criar_prompt_categorizacao(descricoes):
    """Cria o prompt para categorização dos produtos."""
    return (
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
        "Para CADA descrição na lista de entrada (há exatamente {len(descricoes)} itens), determine a `CATEGORIA_PRINCIPAL` e a `SUBCATEGORIA`.\n"
        "Retorne EXATAMENTE {len(descricoes)} objetos JSON, um por descrição, na ordem da lista.\n\n"
        "**ENTRADA (Lista numerada de descrições):**\n"
        + "\n".join([f"{idx+1}. {desc}" for idx, desc in enumerate(descricoes)]) + "\n\n"
        "**SAÍDA (Responda APENAS com uma lista de objetos JSON, sem texto extra):**\n"
        "[\n"
        "  {\"CATEGORIA_PRINCIPAL\": \"<categoria_definida>\", \"SUBCATEGORIA\": \"<nome_do_produto>\"},\n"
        "  ...\n"
        "]"
    )

def processar_batch_llm(model, descricoes, batch_id=""):
    """Processa um batch de descrições com o LLM."""
    prompt = criar_prompt_categorizacao(descricoes)
    
    for tentativa in range(MAX_RETRIES):
        try:
            resposta = model.generate_content(prompt)
            metadados = extrair_json_resposta(resposta.text)
            
            if metadados and len(metadados) == len(descricoes):
                logger.info(f"Batch {batch_id}: Processado com sucesso ({len(metadados)} itens)")
                return metadados
            else:
                logger.warning(
                    f"Batch {batch_id}: Tentativa {tentativa + 1}: Resposta inconsistente. "
                    f"Esperado: {len(descricoes)}, Recebido: {len(metadados) if metadados else 0}"
                )
        except Exception as e:
            logger.error(f"Batch {batch_id}: Erro na API (tentativa {tentativa + 1}/{MAX_RETRIES}): {e}")
        
        if tentativa < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY)
    
    logger.error(f"Batch {batch_id}: Falha após {MAX_RETRIES} tentativas.")
    return None

# =====================
# CLASSE PROCESSADOR ROBUSTO
# =====================

class ProcessadorRobusto:
    """Gerencia o processamento robusto com reprocessamento automático."""
    
    def __init__(self, model):
        self.model = model
        self.produtos_processados = {}
        self.fila_falhas = deque()
        self.total_processados = 0
        self.total_falhas = 0
    
    def processar_produtos(self, df_produtos):
        """Processa todos os produtos com sistema de reprocessamento."""
        logger.info(f"Iniciando processamento robusto de {len(df_produtos)} produtos")
        
        # Preparar dados
        df_produtos['DESCRICAO_LIMPA'] = df_produtos['DESCRICAO'].apply(limpar_html)
        
        # Processar batches principais
        self._processar_batches_principais(df_produtos)
        
        # Reprocessar itens que falharam
        self._reprocessar_falhas()
        
        # Compilar resultados finais
        return self._compilar_resultados(df_produtos)
    
    def _processar_batches_principais(self, df_produtos):
        """Processa os batches principais."""
        for i in tqdm(range(0, len(df_produtos), BATCH_SIZE), desc="Processando batches principais"):
            batch = df_produtos.iloc[i:i + BATCH_SIZE]
            batch_id = f"{i}-{i+len(batch)}"
            
            self._processar_batch(batch, batch_id)
            time.sleep(DELAY_ENTRE_BATCHES)
    
    def _processar_batch(self, batch, batch_id):
        """Processa um batch individual."""
        descricoes = batch['DESCRICAO_LIMPA'].tolist()
        metadados = processar_batch_llm(self.model, descricoes, batch_id)
        
        if metadados and len(metadados) == len(batch):
            # Sucesso - adicionar ao processados
            for idx, (_, row) in enumerate(batch.iterrows()):
                produto_id = row['ID_PRODUTO']
                self.produtos_processados[produto_id] = {
                    'CATEGORIA_PRINCIPAL': metadados[idx]['CATEGORIA_PRINCIPAL'],
                    'SUBCATEGORIA': metadados[idx]['SUBCATEGORIA']
                }
                self.total_processados += 1
        else:
            # Falha - adicionar à fila de reprocessamento
            logger.warning(f"Batch {batch_id}: Inconsistência detectada. Adicionando {len(batch)} itens à fila de reprocessamento.")
            for _, row in batch.iterrows():
                self.fila_falhas.append({
                    'ID_PRODUTO': row['ID_PRODUTO'],
                    'DESCRICAO_LIMPA': row['DESCRICAO_LIMPA'],
                    'DADOS_ORIGINAIS': row
                })
                self.total_falhas += 1
    
    def _reprocessar_falhas(self):
        """Reprocessa itens que falharam em batches menores."""
        if not self.fila_falhas:
            logger.info("Nenhum item para reprocessar.")
            return
        
        logger.info(f"Iniciando reprocessamento de {len(self.fila_falhas)} itens que falharam")
        
        for tentativa in range(MAX_REPROCESS_ATTEMPTS):
            if not self.fila_falhas:
                break
                
            logger.info(f"Tentativa de reprocessamento {tentativa + 1}/{MAX_REPROCESS_ATTEMPTS}")
            
            # Pegar itens para reprocessar
            itens_reprocessar = []
            for _ in range(min(REPROCESS_BATCH_SIZE, len(self.fila_falhas))):
                if self.fila_falhas:
                    itens_reprocessar.append(self.fila_falhas.popleft())
            
            if not itens_reprocessar:
                break
            
            # Reprocessar
            descricoes = [item['DESCRICAO_LIMPA'] for item in itens_reprocessar]
            batch_id = f"reprocess-{tentativa + 1}"
            
            metadados = processar_batch_llm(self.model, descricoes, batch_id)
            
            if metadados and len(metadados) == len(itens_reprocessar):
                # Sucesso no reprocessamento
                for idx, item in enumerate(itens_reprocessar):
                    produto_id = item['ID_PRODUTO']
                    self.produtos_processados[produto_id] = {
                        'CATEGORIA_PRINCIPAL': metadados[idx]['CATEGORIA_PRINCIPAL'],
                        'SUBCATEGORIA': metadados[idx]['SUBCATEGORIA']
                    }
                    self.total_processados += 1
                    self.total_falhas -= 1
                
                logger.info(f"Reprocessamento {tentativa + 1}: {len(itens_reprocessar)} itens processados com sucesso")
            else:
                # Falha no reprocessamento - devolver à fila
                logger.warning(f"Reprocessamento {tentativa + 1}: Falha. Devolvendo {len(itens_reprocessar)} itens à fila")
                for item in itens_reprocessar:
                    self.fila_falhas.append(item)
                    self.total_falhas += 1
            
            time.sleep(RETRY_DELAY * 2)
        
        # Aplicar fallback para itens que ainda falharam
        if self.fila_falhas:
            self._aplicar_fallback()
    
    def _aplicar_fallback(self):
        """Aplica fallback para itens que ainda falharam."""
        for item in self.fila_falhas:
            produto_id = item['ID_PRODUTO']
            self.produtos_processados[produto_id] = {
                'CATEGORIA_PRINCIPAL': 'ERRO_PROCESSAMENTO',
                'SUBCATEGORIA': 'ERRO_PROCESSAMENTO'
            }
            self.total_processados += 1
        
        logger.info(f"Aplicado fallback para {len(self.fila_falhas)} itens")
        self.fila_falhas.clear()
        self.total_falhas = 0
    
    def _compilar_resultados(self, df_produtos):
        """Compila os resultados finais em DataFrame."""
        metadados_lista = []
        
        for _, row in df_produtos.iterrows():
            produto_id = row['ID_PRODUTO']
            if produto_id in self.produtos_processados:
                metadados_lista.append(self.produtos_processados[produto_id])
            else:
                # Fallback para itens não processados
                metadados_lista.append({
                    'CATEGORIA_PRINCIPAL': 'ERRO_PROCESSAMENTO',
                    'SUBCATEGORIA': 'ERRO_PROCESSAMENTO'
                })
        
        logger.info(f"Compilação final: {self.total_processados} processados, {self.total_falhas} falhas")
        return pd.DataFrame(metadados_lista)

# =====================
# FUNÇÃO PRINCIPAL
# =====================

def processar_produtos():
    """Função principal que orquestra todo o processo."""
    os.makedirs(PASTA_SAIDA, exist_ok=True)
    model = configurar_llm()
    
    # 1. Carregar dados de origem
    logger.info(f"Carregando dados de origem: {CAMINHO_DADOS}")
    df_origem = pd.read_excel(CAMINHO_DADOS)
    df_origem.columns = [str(c).strip().upper() for c in df_origem.columns]
    df_origem['ID_PRODUTO'] = df_origem.apply(gerar_id_produto, axis=1)
    df_origem = df_origem.dropna(subset=['DESCRICAO']).reset_index(drop=True)

    # 2. Verificar dados existentes
    df_processar = pd.DataFrame()
    df_existente = pd.DataFrame()

    if os.path.exists(ARQUIVO_SAIDA):
        logger.info("Arquivo de metadados existente encontrado. Verificando atualizações...")
        df_processado = pd.read_excel(ARQUIVO_SAIDA)
        
        if 'ID_PRODUTO' not in df_processado.columns:
            logger.warning("Arquivo antigo detectado. Reprocessamento completo necessário.")
            df_processar = df_origem.copy()
            df_existente = pd.DataFrame()
        else:
            # Sincronização incremental
            ids_origem = set(df_origem['ID_PRODUTO'])
            ids_processados = set(df_processado['ID_PRODUTO'])
            
            novos_ids = ids_origem - ids_processados
            removidos_ids = ids_processados - ids_origem
            
            if novos_ids:
                logger.info(f"Encontrados {len(novos_ids)} novos produtos para processar.")
                df_processar = df_origem[df_origem['ID_PRODUTO'].isin(novos_ids)].copy()
            
            if removidos_ids:
                logger.info(f"Encontrados {len(removidos_ids)} produtos removidos da base.")
            
            df_existente = df_processado[~df_processado['ID_PRODUTO'].isin(removidos_ids)]
            logger.info(f"{len(df_existente)} produtos existentes serão mantidos.")
    else:
        logger.info("Nenhum arquivo de metadados existente. Processando todos os produtos.")
        df_processar = df_origem.copy()

    # 3. Processar produtos novos
    if not df_processar.empty:
        logger.info(f"Iniciando processamento robusto de {len(df_processar)} produtos.")
        
        processador = ProcessadorRobusto(model)
        df_metadados = processador.processar_produtos(df_processar)
        
        # Combinar dados
        df_processar.reset_index(drop=True, inplace=True)
        df_metadados.reset_index(drop=True, inplace=True)
        
        df_novos_processados = pd.concat([df_processar, df_metadados], axis=1)
        df_novos_processados = df_novos_processados.drop(columns=['DESCRICAO_LIMPA'])
        
        df_final = pd.concat([df_existente, df_novos_processados], ignore_index=True)
    else:
        logger.info("Nenhum produto novo para processar.")
        df_final = df_existente

    # 4. Salvar resultado final
    if not df_final.empty:
        logger.info("Formatando e salvando arquivo final.")
        
        # Renomear colunas
        df_final = df_final.rename(columns={
            'CATEGORIA_PRINCIPAL': 'categoria_principal', 
            'SUBCATEGORIA': 'subcategoria'
        })
        
        # Definir ordem das colunas
        colunas_finais = ['ID_PRODUTO', 'categoria_principal', 'subcategoria', 'MARCA', 'MODELO', 'VALOR', 'DESCRICAO']
        
        # Garantir que todas as colunas existam
        for col in colunas_finais:
            if col not in df_final.columns:
                df_final[col] = pd.NA
        
        df_final = df_final[colunas_finais]
        
        logger.info(f"Salvando arquivo final com {len(df_final)} produtos: {ARQUIVO_SAIDA}")
        df_final.to_excel(ARQUIVO_SAIDA, index=False)
        logger.info("Operação concluída com sucesso!")
    else:
        if os.path.exists(ARQUIVO_SAIDA):
            os.remove(ARQUIVO_SAIDA)
            logger.info("Todos os produtos foram removidos. Arquivo deletado.")
        else:
            logger.info("Nenhum produto para salvar.")

# =====================
# EXECUÇÃO
# =====================

if __name__ == "__main__":
    processar_produtos()