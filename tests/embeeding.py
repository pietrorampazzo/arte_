import pandas as pd

# Carregar sua base de dados
caminho_base = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\FORNECEDORES\data_base.xlsx"
df_base_produtos = pd.read_excel(caminho_base)

# Criar a coluna combinada para o embedding
df_base_produtos['texto_para_embedding'] = df_base_produtos.apply(
    lambda row: f"{row['DESCRICAO']}. Marca: {row['Marca']}. Modelo: {row['Modelo']}",
    axis=1
)

# Agora a coluna 'texto_para_embedding' está pronta para ser usada no seu script
print(df_base_produtos[['texto_para_embedding']].head())


import pandas as pd

# Supondo que você carregue o edital em um DataFrame
df_edital = pd.read_excel(r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\ORCAMENTOS\102123_900502025_IDEAL.xlsx")

# A coluna para embedding já está praticamente pronta
df_edital['texto_para_embedding'] = df_edital['DESCRICAO']

print(df_edital[['texto_para_embedding']].head())