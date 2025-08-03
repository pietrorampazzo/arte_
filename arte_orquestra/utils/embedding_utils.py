from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')  # Modelo de exemplo

def generate_embeddings(texts):
    return model.encode(texts)