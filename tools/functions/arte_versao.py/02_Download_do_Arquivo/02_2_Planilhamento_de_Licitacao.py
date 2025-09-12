# Estratégia: Estrutura dados extraídos em planilhas.
# Funcionamento: Converte texto bruto em dados estruturados (JSON/Excel).
# Integração: Prepara dados para prompts de IA.

import pandas as pd

def planilha_licitacao(text):
    # Placeholder: implementar parsing com regex ou NLP
    data = [{'description': line, 'quantity': 1} for line in text.split('\n') if line.strip()]
    df = pd.DataFrame(data)
    df.to_excel('data/licitacao.xlsx', index=False)
    return df