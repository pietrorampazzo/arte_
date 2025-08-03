import faiss

def match_editais_to_base(editais_embeddings, base_index_path):
    index = faiss.read_index(base_index_path)
    D, I = index.search(editais_embeddings, k=5)  # Top 5 matches
    similarities = -D  # Para IndexFlatIP, similaridade = -D
    return similarities, I