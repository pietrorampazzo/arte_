import os
import re
import pandas as pd
import fitz  # PyMuPDF
import logging
import google.generativeai as genai
import google.api_core.exceptions as google_exceptions
from dotenv import load_dotenv
import time
import json
from dotenv import load_dotenv
# --- CONFIGURAÇÃO INICIAL ---
# Chama a função para carregar as variáveis do arquivo .env
load_dotenv() 

LLM_MODELS_FALLBACK = [

    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.5-pro",
    "gemini-1.5-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash",
]

def gerar_conteudo_com_fallback(prompt, models):
    """Tenta gerar conteúdo usando uma lista de modelos em fallback."""
    for model_name in models:
        try:
            logging.info(f"Tentando chamada à API com o modelo: {model_name}...")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            logging.info(f"Sucesso com o modelo '{model_name}'.")
            return response.text
        except Exception as e:
            logging.warning(f"Falha ao usar o modelo '{model_name}': {e}")
            time.sleep(2)  # Pausa antes de tentar o próximo modelo
    logging.error("Falha em todos os modelos de fallback.")
    return None

class EditalExtractor:
    def __init__(self, input_dir, output_dir, gemini_key=None):
        self.input_dir = input_dir
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
        self.log = logging.info
        self.gemini_configured = False
        if gemini_key:
            genai.configure(api_key=gemini_key)
            self.gemini_configured = True

    def process_pdf_file(self, pdf_path):
        self.log(f"Processando: {pdf_path}")
        text = ""
        try:
            with fitz.open(pdf_path) as doc:
                for page in doc:
                    text += page.get_text()
        except Exception as e:
            self.log(f"Erro ao processar PDF {pdf_path}: {e}")
            return ""
        if not text.strip():
            self.log(f"Aviso: Nenhum texto extraído de {pdf_path}")
            return ""
        return text

    def extract_items_from_text(self, text, arquivo_nome):
        items = []
        text = re.sub(r"\n+", "\n", text)
        text = re.sub(r"\s+", " ", text)

        item_pattern = re.compile(r"(\d+)\s*-\s*([^0-9]+?)(?=Descrição Detalhada:)", re.DOTALL | re.IGNORECASE)
        item_matches = list(item_pattern.finditer(text))

        for i, match in enumerate(item_matches):
            item_num = match.group(1).strip()
            item_nome = match.group(2).strip()
            start_pos = match.start()
            end_pos = item_matches[i + 1].start() if i + 1 < len(item_matches) else len(text)
            item_text = text[start_pos:end_pos]

            descricao_match = re.search(
                r"Descrição Detalhada:\s*(.*?)(?=Tratamento Diferenciado:|Aplicabilidade Decreto|$)",
                item_text,
                re.DOTALL | re.IGNORECASE,
            )
            descricao = descricao_match.group(1).strip() if descricao_match else ""

            items.append({
                "ARQUIVO": arquivo_nome,
                "Número do Item": item_num,
                "Descrição": f"{item_nome} {descricao}".strip()
            })
        return items

    def tratar_dataframe(self, df):
        if df.empty:
            return df
        df = df.rename(columns={
            "ARQUIVO": "ARQUIVO",
            "Número do Item": "Nº",
            "Descrição": "DESCRICAO"
        })
        return df

    def validate_and_match_llm(self, df, termo_text, folder_name):
        """
        Usa Gemini com fallback para validar se os descritivos encontrados no termo
        correspondem aos itens da RelacaoItens.
        """
        if not self.gemini_configured:
            self.log("Gemini não configurado. Pulando validação LLM.")
            return {i: "" for i in df["Nº"]}

        prompt = f"""
Você é um especialista em editais públicos.
Recebeu dois conjuntos de informações:

1. Relação de Itens extraída do edital (Item + Descrição)
{df.to_dict(orient='records')}

2. Texto extraído de seções como 'CONDIÇÕES GERAIS DA CONTRATAÇÃO', 'MODELO DE PLANILHA DE PROPOSTA' e outros:
{termo_text}

Tarefa:
- Validar se existem correspondências entre os itens da RelaçãoItens e as descrições do texto.
- Retornar um dicionário JSON com o formato:
  {{ "item_numero": "descricao de referencia validada" }}
- O número de itens deve bater com a RelaçãoItens.
- Caso não encontre descrição confiável, retorne string vazia.
"""

        for model_name in LLM_MODELS_FALLBACK:
            try:
                self.log(f"Tentando chamada LLM com modelo: {model_name}")
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                
                # Limpa a resposta para extrair o JSON
                cleaned_response = response.text.strip()
                if cleaned_response.startswith("```json"):
                    cleaned_response = cleaned_response[7:]
                if cleaned_response.endswith("```"):
                    cleaned_response = cleaned_response[:-3]
                
                mapping = json.loads(cleaned_response)

                if isinstance(mapping, dict) and mapping:
                    return mapping
                else:
                    self.log(f"Modelo {model_name} retornou vazio ou formato inválido. Tentando próximo...")
            except (json.JSONDecodeError, AttributeError, google_exceptions.GoogleAPICallError) as e:
                self.log(f"Erro com modelo {model_name}: {e}. Tentando próximo...")
            except Exception as e:
                self.log(f"Erro inesperado com modelo {model_name}: {e}. Tentando próximo...")


        self.log("Todos os modelos falharam. Retornando mapping vazio.")
        return {i: "" for i in df["Nº"]}

    def process_folder(self, folder_path):
        self.log(f"Processando pasta: {folder_path}")
        relacao_text = ""
        termo_text = ""

        for file in os.listdir(folder_path):
            if file.lower().endswith(".pdf"):
                path = os.path.join(folder_path, file)
                text = self.process_pdf_file(path)
                if "RelacaoItens" in file:
                    relacao_text = text
                else:
                    termo_text += text

        if not relacao_text:
            self.log("Arquivo RelacaoItens não encontrado ou vazio. Pulando pasta.")
            return pd.DataFrame()

        items = self.extract_items_from_text(relacao_text, os.path.basename(folder_path))
        if not items:
            self.log("Nenhum item extraído da RelacaoItens. Pulando pasta.")
            return pd.DataFrame()

        df = pd.DataFrame(items)
        df = self.tratar_dataframe(df)
        mapping = self.validate_and_match_llm(df, termo_text, os.path.basename(folder_path))
        df["REFERENCIA"] = df["Nº"].astype(str).map(mapping)
        df["PASTA"] = os.path.basename(folder_path)
        return df

    def run(self):
        self.log("Iniciando processamento de todas as pastas...")
        df_consolidado = pd.DataFrame()
        for folder in os.listdir(self.input_dir):
            folder_path = os.path.join(self.input_dir, folder)
            if os.path.isdir(folder_path):
                df_pasta = self.process_folder(folder_path)
                if not df_pasta.empty:
                    df_consolidado = pd.concat([df_consolidado, df_pasta], ignore_index=True)
        if df_consolidado.empty:
            self.log("Nenhum dado extraído de todas as pastas.")
            return
        output_file = os.path.join(self.output_dir, "master_modelo_consolidado.xlsx")
        df_consolidado.to_excel(output_file, index=False)
        self.log(f"Arquivo consolidado salvo em: {output_file}")
        self.log("Processamento concluído.")


def main():
    load_dotenv()
    gemini_api_key = os.getenv("GOOGLE_API_KEY")
    if not gemini_api_key:
        print("A chave da API Gemini não foi encontrada no arquivo .env. Defina a variável de ambiente GEMINI_API_KEY.")
        # Opcional: Sair se a chave for essencial
        # return

    input_dir = "DOWNLOADS/EDITAIS_TESTE"
    output_dir = "OUTPUT_COMPLETO"
    # Passa a chave da API para o extrator. Se for None, o LLM será pulado.
    extractor = EditalExtractor(input_dir, output_dir, gemini_key=gemini_api_key)
    extractor.run()

if __name__ == "__main__":
    main()