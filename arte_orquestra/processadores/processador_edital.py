import pandas as pd
import os
import numpy as np
from utils.embedding_utils import generate_embeddings

def process_editais(directory):
    all_embeddings = []
    all_info = []
    for filename in os.listdir(directory):
        if filename.endswith('.xlsx'):
            filepath = os.path.join(directory, filename)
            df = pd.read_excel(filepath)
            for idx, row in df.iterrows():
                description = row['DESCRICAO']
                embedding = generate_embeddings([description])[0]
                all_embeddings.append(embedding)
                all_info.append((filename, idx, description))
    return np.array(all_embeddings), all_info