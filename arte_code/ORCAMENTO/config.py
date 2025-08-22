# config.py
# This file contains the configuration constants for the project.

import pandas as pd
# --- File Paths ---
# Using relative paths for better portability
CAMINHO_EDITAL = r'C:\Users\pietr\OneDrive\.vscode\arte_\U_980403_N_900142025.xlsx'
CAMINHO_BASE = r'C:\Users\pietr\OneDrive\.vscode\arte_\sheets\RESULTADO_metadados\produtos_categorizados_v2.xlsx'
CAMINHO_SAIDA = "sheets/RESULTADO_proposta/propostas_geradas.xlsx"

# --- Financial Parameters ---
PROFIT_MARGIN = 0.53  # 53%
INITIAL_PRICE_FILTER_PERCENTAGE = 0.60  # 60%

# --- AI Model Configuration ---
GEMINI_MODEL = "gemini-2.5-flash-lite"

# --- Categorization Keywords ---
# This dictionary will be used for keyword-based categorization.
# The keys are the categories, and the values are lists of keywords.
CATEGORIZATION_KEYWORDS = {
    'ACESSORIO_CORDA' :['arco','cavalete','corda','corda','kit nut','kit rastilho'],
    'ACESSORIO_GERAL' :['bag','banco','carrinho prancha','estante de partitura','suporte'],
    'ACESSORIO_PERCURSSAO' :['baqueta','carrilhão','esteira','Máquina de Hi Hat','Pad para Bumbo','parafuso','pedal de bumbo','pele','prato','sino','talabarte','triângulo'],
    'ACESSORIO_SOPRO' : ['graxa','oleo lubrificante','palheta de saxofone/clarinete'],
    'EQUIPAMENTO_AUDIO' : ['fone de ouvido','globo microfone','Interface de guitarra','pedal','mesa de som','microfone'],
    'EQUIPAMENTO_CABO' : ['cabo CFTV','cabo de rede','caixa medusa','Medusa','P10','P2xP10','painel de conexão','xlr M/F',],
    'EQUIPAMENTO_SOM' : ['amplificador','caixa de som','cubo para guitarra',],
    "INSTRUMENTO_CORDA": ["violino", "viola", "violão", "guitarra", "baixo", "violoncelo"],
    "INSTRUMENTO_PERCUSSAO": ["afuché", "bateria", "bombo", "bumbo", "caixa de guerra","caixa tenor", "ganza", "pandeiro", "quadriton", "reco reco", "surdo", "tambor", "tarol", "timbales"],
    "INSTRUMENTO_SOPRO": ["trompete", "bombardino", "trompa", "trombone", "tuba","sousafone", "clarinete", "saxofone", "flauta", "tuba bombardão","flugelhorn","euphonium"],
    "INSTRUMENTO_TECLAS": ["piano", "teclado digital", "glockenspiel", "metalofone"],

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
