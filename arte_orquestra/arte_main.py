import os
import pandas as pd
from processadores.processador_base import process_base
from processadores.processador_edital import process_editais
from processadores.matcher import match_editais_to_base
from utils.embedding_utils import generate_embeddings
from processadores.processador_edital import process_editais
from processadores.matcher import match_editais_to_base
from utils.embedding_utils import generate_embeddings

# Caminhos de entrada e saída
BASE_PATH = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\FORNECEDORES\data_base.xlsx"
EDITAIS_DIR = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\ORCAMENTOS"
PROPOSTAS_DIR = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\PROPOSTAS"

# Criar pasta de saída se não existir
os.makedirs(PROPOSTAS_DIR, exist_ok=True)

# Processar base de produtos
process_base(BASE_PATH, output_parquet="data/produtos_indexados.parquet", output_embeddings="data/embeddings_base.faiss")

# Processar editais
editais_embeddings, editais_info = process_editais(EDITAIS_DIR)

# Realizar matching
similarities, indices = match_editais_to_base(editais_embeddings, "data/embeddings_base.faiss")

# Carregar base de produtos para obter detalhes
base_df = pd.read_parquet("data/produtos_indexados.parquet")

# Gerar propostas
matches_list = []
for i, (edital_file, edital_idx, edital_desc) in enumerate(editais_info):
    for j in range(5):  # Top 5 matches
        prod_idx = indices[i, j]
        sim = similarities[i, j]
        prod_desc = base_df.iloc[prod_idx]['DESCRICAO']
        prod_id = base_df.iloc[prod_idx].get('ID', 'N/A')  # Assumindo que há uma coluna 'ID'
        matches_list.append({
            'Edital File': edital_file,
            'Edital Index': edital_idx,
            'Edital Description': edital_desc,
            'Product ID': prod_id,
            'Product Description': prod_desc,
            'Similarity': sim
        })

# Converter para DataFrame e salvar propostas
matches_df = pd.DataFrame(matches_list)
for edital_file in set(matches_df['Edital File']):
    subset = matches_df[matches_df['Edital File'] == edital_file]
    proposal_path = os.path.join(PROPOSTAS_DIR, f"proposta_{edital_file}.xlsx")
    subset.to_excel(proposal_path, index=False)

print("Processo concluído. Propostas salvas em:", PROPOSTAS_DIR)