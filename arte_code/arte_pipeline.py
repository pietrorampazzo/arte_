"""
ORQUESTRADOR PRINCIPAL DO PIPELINE ARTE (v2)
============================================

Este script coordena o pipeline completo de automação de licitações,
integrando os módulos especializados:

1.  **Download de Editais**: `arte_download.py`
    - Responsável por baixar novos editais e organizá-los em pastas.

2.  **Extração e Enriquecimento**: `arte_edital.py`
    - Processa os arquivos baixados (PDF, ZIP, etc.).
    - Extrai o texto dos editais, usando OCR quando necessário.
    - Utiliza IA (Gemini) para extrair e enriquecer a descrição dos itens.
    - Filtra e consolida os itens de interesse no arquivo `master.xlsx`.

3.  **Matching de Produtos**: `arte_heavy.py`
    - Compara os itens do `master.xlsx` com a base de produtos interna.
    - Realiza o matching para encontrar os produtos correspondentes para o orçamento.

Autor: arte_comercial
Data: 2025/09/21
Versão: 2.0.0
"""

import os
import sys
import subprocess
import logging
from datetime import datetime

# --- Configuração de Logging ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if logger.hasHandlers():
    logger.handlers.clear()

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# Handler para arquivo de log
log_file_path = r'C:\Users\pietr\OneDrive\.vscode\arte_\LOGS\arte_pipeline.log'
os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
file_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Handler para console (stdout)
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except (TypeError, AttributeError):
    pass # Ignora se a reconfiguração não for suportada
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

# --- Configurações de Caminhos ---
BASE_DIR = r"C:\Users\pietr\OneDrive\.vscode\arte_"
SCRIPTS_DIR = os.path.join(BASE_DIR, "arte_code")

# Mapeamento dos scripts para cada etapa
SCRIPTS = {
    "download": os.path.join(SCRIPTS_DIR, "arte_download.py"),
    "enrich": os.path.join(SCRIPTS_DIR, "arte_edital.py"),
    "matching": os.path.join(SCRIPTS_DIR, "arte_heavy.py"), # Novo script de matching
}

class ArtePipeline:
    """
    Orquestra a execução sequencial dos scripts do pipeline de análise de editais.
    """
    def __init__(self):
        self.start_time = datetime.now()

    def log_step(self, step_name, message):
        """Registra uma mensagem de log formatada."""
        logger.info(f"[{step_name.upper()}] {message}")

    def check_prerequisites(self):
        """Verifica se todos os scripts necessários existem."""
        self.log_step("VERIFICAÇÃO", "Verificando pré-requisitos...")
        all_found = True
        for name, path in SCRIPTS.items():
            if not os.path.exists(path):
                logger.error(f"❌ Script para a etapa '{name}' não encontrado: {path}")
                all_found = False
            else:
                logger.info(f"✅ Script '{name}' encontrado: {path}")

        env_file = os.path.join(BASE_DIR, ".env")
        if not os.path.exists(env_file):
            logger.warning(f"⚠️ Arquivo .env não encontrado em: {env_file}. A API do Gemini pode falhar.")
        else:
            logger.info("✅ Arquivo .env encontrado.")

        return all_found

    def run_script(self, script_name):
        """Executa um script Python e transmite sua saída em tempo real."""
        script_path = SCRIPTS.get(script_name)
        if not script_path:
            self.log_step(script_name, f"❌ Etapa '{script_name}' não reconhecida.")
            return False

        self.log_step(script_name, f"Iniciando execução de {os.path.basename(script_path)}...")
        
        # Garante que o script seja executado a partir do seu próprio diretório
        script_dir = os.path.dirname(script_path)
        original_dir = os.getcwd()
        os.chdir(script_dir)

        try:
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1" # Força o Python a usar UTF-8 para I/O

            process = subprocess.Popen(
                [sys.executable, "-u", os.path.basename(script_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                env=env
            )

            # Transmite a saída do processo em tempo real
            if process.stdout:
                for line in iter(process.stdout.readline, ''):
                    logger.info(f"[{script_name.upper()}] > {line.strip()}")

            process.wait() # Espera o processo terminar

            if process.returncode == 0:
                self.log_step(script_name, "✅ Executado com sucesso.")
                return True
            else:
                logger.error(f"[{script_name.upper()}] ❌ Erro na execução (código {process.returncode}). Verifique os logs acima.")
                return False

        except Exception as e:
            logger.error(f"[{script_name.upper()}] ❌ Erro inesperado ao executar o script: {e}")
            return False
        finally:
            os.chdir(original_dir) # Retorna ao diretório original

    def run_full_pipeline(self):
        """Executa o pipeline completo na ordem correta."""
        logger.info("="*60)
        logger.info("🚀 INICIANDO PIPELINE COMPLETO DE ANÁLISE DE EDITAIS 🚀")
        logger.info("="*60)

        if not self.check_prerequisites():
            logger.error("❌ Falha na verificação de pré-requisitos. Abortando pipeline.")
            return

        # Etapa 1: Download
        logger.info("\n--- ETAPA 1: DOWNLOAD ---")
        if not self.run_script("download"):
            logger.error("❌ A etapa de DOWNLOAD falhou. O pipeline não pode continuar.")
            return

        # Etapa 2: Extração e Enriquecimento com IA
        logger.info("\n--- ETAPA 2: ENRIQUECIMENTO (arte_edital.py) ---")
        if not self.run_script("enrich"):
            logger.error("❌ A etapa de ENRIQUECIMENTO falhou. O pipeline não pode continuar.")
            return

        # Etapa 3: Matching de Produtos
        logger.info("\n--- ETAPA 3: MATCHING (arte_heavy.py) ---")
        if not self.run_script("matching"):
            logger.error("❌ A etapa de MATCHING falhou.")
            return

        logger.info("\n" + "="*60)
        logger.info("🎉 PIPELINE COMPLETO FINALIZADO COM SUCESSO! 🎉")
        logger.info("="*60)

def main():
    pipeline = ArtePipeline()
    pipeline.run_full_pipeline()

if __name__ == "__main__":
    main()