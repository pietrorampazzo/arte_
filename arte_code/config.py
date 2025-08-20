# config.py
# This file contains the configuration constants for the project.

import pandas as pd
# --- File Paths ---
# Using relative paths for better portability
CAMINHO_EDITAL = "master.xlsx"
CAMINHO_BASE = "base_produtos.xlsx"
CAMINHO_SAIDA = "RESULTADO/propostas_geradas.xlsx"

# --- Financial Parameters ---
PROFIT_MARGIN = 0.53  # 53%
INITIAL_PRICE_FILTER_PERCENTAGE = 0.60  # 60%

# --- AI Model Configuration ---
GEMINI_MODEL = "gemini-2.5-flash"

# --- Categorization Keywords ---
# This dictionary will be used for keyword-based categorization.
# The keys are the categories, and the values are lists of keywords.
CATEGORIZATION_KEYWORDS = {
    "MESA_DE_SOM": ["mesa de som", "mesa digital", "mesa analogica", "mixer"],
    "MICROFONE": ["microfone", "mic", "lapela", "headset"],
    "CAIXA_DE_SOM": ["caixa de som", "caixa acustica", "monitor de palco", "subwoofer"],
    "INSTRUMENTO_SOPRO": ["trompete", "bombardino", "trompa", "trombone", "tuba", "sousafone", "clarinete", "saxofone", "flauta"],
    "INSTRUMENTO_PERCUSSAO": ["bateria", "bumbo", "timbales", "timpano", "surdo", "tarol", "caixa de guerra", "quadriton", "tambor", "afuché", "prato", "triângulo", "carrilhão", "sino"],
    "INSTRUMENTO_CORDA": ["violino", "viola", "violão", "guitarra", "baixo", "violoncelo"],
    "INSTRUMENTO_TECLAS": ["piano", "lira", "teclado digital", "glockenspiel"],
    "ACESSORIO": ["bocal", "lubrificante", "boquilha", "surdina", "graxa", "lever oil", "oleo", "palheta", "baqueta", "maquina de hi hat", "talabarte", "pele", "esteira", "corda", "arco", "cavalete", "estante", "suporte", "banco", "bag", "case"],
    "CABO": ["cabo", "hdmi", "xlr", "p10", "p2", "medusa", "cat5", "cftv"],
    "EQUIPAMENTO_AUDIO": ["amplificador", "cubo", "fone de ouvido", "powerplay"],
}

# --- Load Categorized Products ---
def load_categorized_products(file_path):
    """
    Loads categorized products from an Excel file into a dictionary.
    """
    try:
        df = pd.read_excel(file_path)
        # Assuming the Excel file has columns 'ID_PRODUTO', 'categoria_principal', and 'subcategoria'
        return df.set_index('ID_PRODUTO')[['categoria_principal', 'subcategoria']].to_dict('index')
    except FileNotFoundError:
        print(f"ERROR: Could not load categorized products file: {file_path}")
        return {}
