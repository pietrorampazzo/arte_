"""
ORQUESTRADOR PRINCIPAL - SISTEMA DE AUTOMAÇÃO ARTE
==================================================

Este script coordena todos os processos de automação:
1. Download de editais (arte_orquestra.py)
2. Processamento de metadados (arte_metadados.py) 
3. Matching de produtos (arte_heavy.py)

Autor: arte_comercial
Data: 2025
Versão: 1.0.0
"""

import os
import sys
import time
import subprocess
from datetime import datetime
import logging

# Configuração de logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# Evita a duplicação de logs se o script for importado em outro lugar
if logger.hasHandlers():
    logger.handlers.clear()

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# File handler com UTF-8
file_handler = logging.FileHandler(r'C:\Users\pietr\OneDrive\.vscode\arte_\LOGS\arte_orchestrator.log', mode='a', encoding='utf-8')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Stream handler (console) com UTF-8
# Força o stdout a usar UTF-8. Essencial para o Windows.
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except (TypeError, AttributeError):
    # Passa se a reconfiguração não for suportada (ex: em alguns IDEs ou versões do Python)
    pass
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

# Configurações de caminhos
BASE_DIR = r"C:\Users\pietr\OneDrive\.vscode\arte_"
DOWNLOADS_DIR = os.path.join(BASE_DIR, "DOWNLOADS")
SCRIPTS_DIR = os.path.join(BASE_DIR, "arte_code")

# Caminhos dos scripts - CORREÇÃO DOS CAMINHOS
DOWNLOAD_SCRIPT = r"C:\Users\pietr\OneDrive\.vscode\arte_\arte_code\arte_orquestra.py"
METADADOS_SCRIPT = os.path.join(SCRIPTS_DIR, "arte_metadados.py")
HEAVY_SCRIPT = os.path.join(SCRIPTS_DIR, "arte_heavy.py")  # ajustado para o caminho correto

class ArteOrchestrator:
    def __init__(self):
        self.start_time = datetime.now()
        self.log_file = f"arte_orchestrator_{self.start_time.strftime('%Y%m%d_%H%M%S')}.log"
        
    def log_step(self, step_name, message):
        """Registra um passo do processo"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        logger.info(f"[{timestamp}] {step_name}: {message}")
        
    def check_prerequisites(self):
        """Verifica se todos os pré-requisitos estão atendidos"""
        self.log_step("VERIFICAÇÃO", "Verificando pré-requisitos...")
        
        # Verificar se os diretórios existem
        required_dirs = [BASE_DIR, DOWNLOADS_DIR, SCRIPTS_DIR]
        for dir_path in required_dirs:
            if not os.path.exists(dir_path):
                logger.error(f"❌ Diretório não encontrado: {dir_path}")
                return False
                
        # Verificar se os scripts existem
        required_scripts = [DOWNLOAD_SCRIPT, METADADOS_SCRIPT, HEAVY_SCRIPT]
        for script_path in required_scripts:
            if not os.path.exists(script_path):
                logger.error(f"❌ Script não encontrado: {script_path}")
                return False
                
        # Verificar arquivo .env
        env_file = os.path.join(BASE_DIR, ".env")
        if not os.path.exists(env_file):
            logger.warning(f"⚠️ Arquivo .env não encontrado em: {env_file}")
            logger.warning("Certifique-se de que a GOOGLE_API_KEY está configurada")
        
        self.log_step("VERIFICAÇÃO", "✅ Todos os pré-requisitos atendidos")
        return True
        
    def run_script(self, script_path, script_name):
        """
        Executa um script Python e transmite toda a sua saída (stdout e stderr) em tempo real.
        """
        self.log_step(script_name, f"Iniciando execução...")
        original_dir = os.getcwd()
        process = None
        try:
            script_dir = os.path.dirname(script_path)
            os.chdir(script_dir)

            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"

            process = subprocess.Popen(
                [sys.executable, "-u", script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                env=env
            )

            if process.stdout:
                for line in iter(process.stdout.readline, ''):
                    logger.info(f"[{script_name}] {line.strip()}")

            process.wait(timeout=3600)

            if process.returncode == 0:
                self.log_step(script_name, "✅ Executado com sucesso")
                return True
            else:
                self.log_step(script_name, f"❌ Erro na execução (código {process.returncode})")
                return False

        except subprocess.TimeoutExpired:
            self.log_step(script_name, "❌ Timeout - script demorou mais de 1 hora")
            if process:
                process.kill()
            return False
        except Exception as e:
            self.log_step(script_name, f"❌ Erro inesperado: {str(e)}")
            return False
        finally:
            os.chdir(original_dir)
            
    def check_files_updated(self, file_paths, timeout_minutes=5):
        """Verifica se os arquivos foram atualizados recentemente"""
        self.log_step("VERIFICAÇÃO", "Verificando atualização de arquivos...")
        
        current_time = time.time()
        for file_path in file_paths:
            if os.path.exists(file_path):
                file_time = os.path.getmtime(file_path)
                time_diff = (current_time - file_time) / 60  # em minutos
                
                if time_diff <= timeout_minutes:
                    self.log_step("VERIFICAÇÃO", f"✅ {os.path.basename(file_path)} atualizado recentemente")
                else:
                    self.log_step("VERIFICAÇÃO", f"⚠️ {os.path.basename(file_path)} não foi atualizado recentemente")
            else:
                self.log_step("VERIFICAÇÃO", f"❌ {os.path.basename(file_path)} não encontrado")
                
    def run_pipeline(self, steps=None):
        """Executa o pipeline completo ou etapas específicas"""
        if steps is None:
            steps = ['download', 'matching']
            
        self.log_step("ORQUESTRADOR", f"Iniciando pipeline: {', '.join(steps)}")
        
        # Verificar pré-requisitos
        if not self.check_prerequisites():
            logger.error("❌ Falha na verificação de pré-requisitos. Abortando.")
            return False
            
        success_count = 0
        total_steps = len(steps)
        
        # Etapa: Download de editais
        if 'download' in steps:
            self.log_step("PIPELINE", "=== ETAPA: DOWNLOAD DE EDITAIS ===")
            if self.run_script(DOWNLOAD_SCRIPT, "DOWNLOAD_EDITAIS"):
                success_count += 1
                # Verificar se o master.xlsx foi atualizado
                master_file = os.path.join(DOWNLOADS_DIR, "master.xlsx")
                self.check_files_updated([master_file])
            else:
                logger.error("❌ Falha no download de editais. Continuando com próximas etapas...")
                
        
                
        # Etapa: Matching de produtos
        if 'matching' in steps:
            self.log_step("PIPELINE", "=== ETAPA: MATCHING DE PRODUTOS ===")
            if self.run_script(HEAVY_SCRIPT, "MATCHING_PRODUTOS"):
                success_count += 1
            else:
                logger.error("❌ Falha no matching de produtos.")
                
        
    def show_status(self):
        """Mostra o status atual dos arquivos"""
        self.log_step("STATUS", "Verificando status dos arquivos principais...")
        
        key_files = [
            os.path.join(DOWNLOADS_DIR, "master.xlsx"),
            os.path.join(DOWNLOADS_DIR, "summary.xlsx"),
            os.path.join(DOWNLOADS_DIR, "livro_razao.xlsx"),
            os.path.join(DOWNLOADS_DIR, "RESULTADO_metadados", "categoria_sonnet.xlsx"),
            os.path.join(DOWNLOADS_DIR, "ORCAMENTOS", "master_heavy.xlsx")
        ]
        
        for file_path in key_files:
            if os.path.exists(file_path):
                size = os.path.getsize(file_path) / 1024  # KB
                mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                self.log_step("STATUS", f"✅ {os.path.basename(file_path)}: {size:.1f}KB, modificado em {mtime.strftime('%d/%m/%Y %H:%M')}")
            else:
                self.log_step("STATUS", f"❌ {os.path.basename(file_path)}: não encontrado")

def main():
    """Função principal"""
    print("="*60)
    print("🐳 ORQUESTRADOR ARTE - SISTEMA DE AUTOMAÇÃO")
    print("="*60)
    
    orchestrator = ArteOrchestrator()
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "status":
            orchestrator.show_status()
        elif command == "download":
            orchestrator.run_pipeline(['download'])
        elif command == "matching":
            orchestrator.run_pipeline(['matching'])
        elif command == "full":
            orchestrator.run_pipeline()
        else:
            print("Comandos disponíveis:")
            print("  python arte_code\nipsey.py status    - Mostra status dos arquivos")
            print("  python arte_code\nipsey.py download  - Executa apenas download")
            print("  python arte_code\nipsey.py matching - Executa apenas matching")
            print("  python arte_code\nipsey.py full      - Executa pipeline completo")
    else:
        # Execução padrão: pipeline completo
        orchestrator.run_pipeline()

if __name__ == "__main__":
    main()
