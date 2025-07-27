import pandas as pd
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import os

# --- CONFIGURAÇÕES ---
# Altere os caminhos se necessário
CAMINHO_BASE_PRODUTOS = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\data_base.xlsx"
PASTA_INDICE = "indice_faiss"
ARQUIVO_INDICE = os.path.join(PASTA_INDICE, "produtos.index")
ARQUIVO_MAPEAMENTO = os.path.join(PASTA_INDICE, "mapeamento_produtos.csv")

# Nome do modelo de embedding. 'paraphrase-multilingual-MiniLM-L12-v2' é ótimo para português.
NOME_MODELO = 'all-mpnet-base-v2'

# --- FUNÇÕES AUXILIARES ---
def criar_texto_para_embedding(row):
    """Combina as colunas relevantes em um único texto para gerar o embedding."""
    marca = row['Marca'] if pd.notna(row['Marca']) else ''
    modelo = row['Modelo'] if pd.notna(row['Modelo']) else ''
    descricao = row['Descrição'] if pd.notna(row['Descrição']) else ''
    return f"Marca: {marca}. Modelo: {modelo}. Descrição: {descricao}"

# --- SCRIPT PRINCIPAL ---
if __name__ == "__main__":
    print("Iniciando o processo de indexação da base de produtos...")

    # 1. Criar pasta para o índice se não existir
    if not os.path.exists(PASTA_INDICE):
        os.makedirs(PASTA_INDICE)

    # 2. Carregar a base de produtos
    try:
        df_produtos = pd.read_excel(CAMINHO_BASE_PRODUTOS)
        print(f"Sucesso! Carregados {len(df_produtos)} produtos.")
    except FileNotFoundError:
        print(f"ERRO: O arquivo '{CAMINHO_BASE_PRODUTOS}' não foi encontrado.")
        exit()

    # 3. Preparar o texto para embedding
    df_produtos['texto_completo'] = df_produtos.apply(criar_texto_para_embedding, axis=1)

    # 4. Carregar o modelo de IA
    print(f"Carregando o modelo de embedding '{NOME_MODELO}'... (Isso pode levar um momento)")
    model = SentenceTransformer(NOME_MODELO)

    # 5. Gerar os embeddings
    print("Gerando embeddings para todos os produtos... (Isso pode ser demorado)")
    embeddings_produtos = model.encode(df_produtos['texto_completo'].tolist(), show_progress_bar=True)
    embeddings_produtos = np.array(embeddings_produtos).astype('float32')
    
    # Normalizar vetores para usar Similaridade de Cosseno (com IndexFlatIP)
    faiss.normalize_L2(embeddings_produtos)

    # 6. Criar e popular o índice Faiss
    dimensao_vetor = embeddings_produtos.shape[1]
    
    # Usamos IndexFlatIP para similaridade de cosseno após normalização L2
    index = faiss.IndexFlatIP(dimensao_vetor) 
    index = faiss.IndexIDMap(index)
    
    # Adicionamos os vetores usando o índice do DataFrame como ID
    index.add_with_ids(embeddings_produtos, df_produtos.index.values)

    # 7. Salvar o índice e o mapeamento
    print(f"Salvando o índice em '{ARQUIVO_INDICE}'...")
    faiss.write_index(index, ARQUIVO_INDICE)

    # O mapeamento salva as informações essenciais para não precisar recarregar o Excel todo
    df_produtos_map = df_produtos[['Marca', 'Modelo', 'Descrição', 'Valor']].copy()
    df_produtos_map.to_csv(ARQUIVO_MAPEAMENTO, index=True)

    print("-" * 50)
    print("Indexação concluída com sucesso!")
    print(f"Índice com {index.ntotal} produtos e mapeamento salvos na pasta '{PASTA_INDICE}'.")
    print("Execute agora o script 'processador_editais.py'.")