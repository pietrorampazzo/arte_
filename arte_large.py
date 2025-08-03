import logging
import pandas as pd
import numpy as np
import requests
import json
import time
from typing import List, Dict, Tuple
import re
import os
from datetime import datetime
import google.generativeai as genai

# ============= CONFIGURAÇÃO DE PATHS =============
PASTA_EDITAIS = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\ORCAMENTOS"
PASTA_RESULTADOS = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\PROPOSTAS"
CAMINHO_DADOS = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\data_base.xlsx"
ARQUIVO_CACHE = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\cache_llm.json"

# ============= CONFIGURAÇÃO DE APIs =============
GOOGLE_API_KEY = "AIzaSyBdrzcton2jUCv5PSaXE38UCp-l8O42Fvc"

# Configuração de LLMs
CONFIG_LLM = {
    "GEMINI": {
        "model": "gemini-1.5-flash",
        "url": "https://generativeai.googleapis.com/v1beta2/models/gemini-1.5-flash:generateContent",
        "headers": {
            "Authorization": f"Bearer {GOOGLE_API_KEY}",
            "Content-Type": "application/json"
        }
    }
}

# ============= CONFIGURAÇÃO DE MODELOS =============
NOME_MODELO = "all-MiniLM-L6-v2"  # Modelo de embedding da SentenceTransformers


# ============= CLASSES AUXILIARES =============
class RateLimiter:
    def __init__(self, rpm: int, tpm: int):
        self.rpm = rpm
        self.tpm = tpm
        self.last_call = 0
        self.token_count = 0
        self.reset_time = time.time() + 60

    def wait_if_needed(self, tokens: int):
        current_time = time.time()
        if current_time > self.reset_time:
            self.reset_time = current_time + 60
            self.token_count = 0
        
        # Verifica limite de requests por minuto
        if time.time() - self.last_call < 60/self.rpm:
            time.sleep(max(0, (60/self.rpm) - (time.time() - self.last_call)))
        
        # Verifica limite de tokens por minuto
        if self.token_count + tokens > self.tpm:
            sleep_time = self.reset_time - current_time
            if sleep_time > 0:
                time.sleep(sleep_time)
                self.token_count = 0
                self.reset_time = time.time() + 60
        
        self.last_call = time.time()
        self.token_count += tokens

class CacheLLM:
    def __init__(self, cache_file: str):
        self.cache_file = cache_file
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict:
        try:
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def get(self, key: str):
        return self.cache.get(key)

    def set(self, key: str, value: Dict):
        self.cache[key] = value
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f)

# ============= PROCESSADOR LLM =============
class ProcessadorLLM:
    def __init__(self):
        self.rate_limiter = RateLimiter(rpm=30, tpm=6000)
        self.cache = CacheLLM(ARQUIVO_CACHE)
        self.logger = logging.getLogger(__name__)
        
    def chamar_llm(self, provider: str, prompt: str, max_tokens: int = 2000) -> Dict:
        """Chama a API do LLM especificado"""
        cache_key = f"{provider}_{hash(prompt)}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
            
        self.rate_limiter.wait_if_needed(max_tokens)
        
        try:
            if provider == "GEMINI":
                payload = {
                    "model": CONFIG_LLM["GEMINI"]["model"],
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": 0.3
                }
                response = requests.post(
                    CONFIG_LLM["GEMINI"]["url"],
                    headers=CONFIG_LLM["GEMINI"]["headers"],
                    json=payload
                )
                response.raise_for_status()
                result = response.json()["choices"][0]["message"]["content"]
            
            elif provider == "GEMINI":
                genai.configure(api_key=GOOGLE_API_KEY)
                model = genai.GenerativeModel(CONFIG_LLM["GEMINI"]["model"])
                response = model.generate_content(prompt)
                result = response.text
            
            self.cache.set(cache_key, result)
            return result
            
        except Exception as e:
            self.logger.error(f"Erro ao chamar {provider} LLM: {str(e)}")
            raise

# ============= PROMPTS ESPECIALIZADOS =============
PROMPT_EXTRACAO_METADADOS = """
Você é um especialista em análise de editais e produtos para licitações públicas. Sua tarefa é extrair metadados estruturados da seguinte descrição:

DESCRIÇÃO: {descricao}

Extraia os seguintes campos em formato JSON válido (preencha com null quando não aplicável):
- categoria_principal (ex: "Instrumento Musical", "Equipamento de Áudio")
- subcategoria (ex: "Percussão", "Corda", "Amplificador")
- marca (identifique a marca se mencionada)
- modelo (identifique o modelo se mencionado)
- material (materiais principais)
- dimensoes (dimensões principais)
- especificacoes_tecnicas (lista de especificações técnicas relevantes)
- palavras_chave (lista de 5-10 palavras-chave que descrevem o item)

Retorne APENAS o JSON, sem comentários ou texto adicional.
"""

PROMPT_COMPARACAO_PRODUTOS = """
Você é um especialista em comparação de produtos para licitações. Compare o item do edital com os produtos candidatos:

ITEM DO EDITAL:
{metadados_edital}

PRODUTOS CANDIDATOS (em ordem de similaridade):
{metadados_produtos}

Analise e retorne:
1. Uma pontuação de 0-100 para cada produto baseada na compatibilidade
2. Uma justificativa breve para cada pontuação
3. Recomendação do melhor produto ou "NENHUM" se nenhum for adequado

Retorne APENAS um JSON no formato:
{
    "produtos": [
        {
            "id": 1,
            "pontuacao": 85,
            "justificativa": "O produto atende todas especificações...",
            "recomendado": true/false
        }
    ],
    "melhor_produto_id": 1 ou null
}
"""

# ============= COMPARADOR DE EDITAIAS =============
class ComparadorEditais:
    def __init__(self):
        self.llm = ProcessadorLLM()
        self.logger = logging.getLogger(__name__)
        
    def extrair_metadados(self, descricao: str, provider: str = "GEMINI") -> Dict:
        """Extrai metadados usando LLM"""
        prompt = PROMPT_EXTRACAO_METADADOS.format(descricao=descricao)
        try:
            resposta = self.llm.chamar_llm(provider, prompt)
            return json.loads(resposta.strip())
        except Exception as e:
            self.logger.error(f"Erro ao extrair metadados: {str(e)}")
            return {}

    def comparar_produtos(self, item_edital: Dict, produtos: List[Dict]) -> Dict:
        """Compara produtos usando LLM"""
        metadados_edital = self.extrair_metadados(item_edital['DESCRICAO'], "GEMINI")
        
        metadados_produtos = []
        for i, produto in enumerate(produtos[:5]):  # Limita aos 5 melhores
            metadados = self.extrair_metadados(produto['DESCRICAO'], "GEMINI")
            metadados['id'] = i+1
            metadados_produtos.append(metadados)
        
        prompt = PROMPT_COMPARACAO_PRODUTOS.format(
            metadados_edital=json.dumps(metadados_edital, indent=2),
            metadados_produtos=json.dumps(metadados_produtos, indent=2)
        )
        
        try:
            resposta = self.llm.chamar_llm("geneai", prompt, max_tokens=3000)
            return json.loads(resposta.strip())
        except Exception as e:
            self.logger.error(f"Erro ao comparar produtos: {str(e)}")
            return {"produtos": [], "melhor_produto_id": None}

    def processar_edital(self, caminho_edital: str, caminho_base: str):
        """Processa um edital completo"""
        # Carrega dados
        df_edital = pd.read_excel(caminho_edital)
        df_produtos = pd.read_excel(caminho_base)
        
        resultados = []
        
        # Processa cada item do edital
        for _, item in df_edital.iterrows():
            # Encontra produtos candidatos (simplificado - poderia usar embeddings aqui também)
            descricao = item['DESCRICAO'].lower()
            produtos_candidatos = []
            
            for _, produto in df_produtos.iterrows():
                similaridade = self._calcular_similaridade_texto(descricao, produto['DESCRICAO'].lower())
                if similaridade > 0.3:  # Limiar baixo inicial
                    produtos_candidatos.append({
                        **produto.to_dict(),
                        'similaridade': similaridade
                    })
            
            # Ordena por similaridade
            produtos_candidatos = sorted(produtos_candidatos, key=lambda x: x['similaridade'], reverse=True)
            
            # Compara com LLM
            comparacao = self.comparar_produtos(item, produtos_candidatos)
            
            # Prepara resultado
            resultado = {
                'item_edital': item.to_dict(),
                'comparacao': comparacao,
                'produtos_analisados': len(produtos_candidatos)
            }
            resultados.append(resultado)
            
            # Log progresso
            self.logger.info(f"Item {item['Nº']} processado - {len(produtos_candidatos)} produtos analisados")
        
        # Exporta resultados
        self._exportar_resultados(resultados, caminho_edital)

    def _calcular_similaridade_texto(self, texto1: str, texto2: str) -> float:
        """Calcula similaridade básica entre textos"""
        palavras1 = set(re.findall(r'\w+', texto1))
        palavras2 = set(re.findall(r'\w+', texto2))
        return len(palavras1 & palavras2) / len(palavras1 | palavras2) if (palavras1 | palavras2) else 0

    def _exportar_resultados(self, resultados: List[Dict], caminho_edital: str):
        """Exporta resultados para Excel"""
        dados_export = []
        
        for resultado in resultados:
            item = resultado['item_edital']
            comparacao = resultado['comparacao']
            
            melhor_produto = next(
                (p for p in comparacao['produtos'] if p.get('recomendado', False)),
                None
            )
            
            dados_export.append({
                'Nº Item': item.get('Nº', ''),
                'Descrição Edital': item.get('DESCRICAO', ''),
                'Produtos Analisados': resultado['produtos_analisados'],
                'Melhor Produto ID': comparacao.get('melhor_produto_id', 'NENHUM'),
                'Pontuação': melhor_produto.get('pontuacao', 0) if melhor_produto else 0,
                'Justificativa': melhor_produto.get('justificativa', '') if melhor_produto else 'Nenhum produto adequado',
                'Marca': melhor_produto.get('marca', '') if melhor_produto else '',
                'Modelo': melhor_produto.get('modelo', '') if melhor_produto else ''
            })
        
        df_export = pd.DataFrame(dados_export)
        
        # Gera nome do arquivo de saída
        nome_edital = os.path.splitext(os.path.basename(caminho_edital))[0]
        data_hora = datetime.now().strftime("%Y%m%d_%H%M%S")
        caminho_saida = os.path.join(PASTA_RESULTADOS, f"Comparacao_{nome_edital}_{data_hora}.xlsx")
        
        df_export.to_excel(caminho_saida, index=False)
        self.logger.info(f"Resultados exportados para: {caminho_saida}")

# ============= EXECUÇÃO PRINCIPAL =============
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    comparador = ComparadorEditais()
    
    try:
        # Exemplo de uso
        caminho_edital = os.path.join(PASTA_EDITAIS, "102123_900502025_IDEAL.xlsx")
        comparador.processar_edital(caminho_edital, CAMINHO_DADOS)
        
    except Exception as e:
        logging.error(f"Erro durante a execução: {str(e)}")