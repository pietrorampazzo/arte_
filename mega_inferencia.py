# mega_inferência.py
import pandas as pd
import google.generativeai as genai

# CONFIG
GOOGLE_API_KEY = 'AIzaSyBdrzcton2jUCv5PSaXE38UCp-l8O42Fvc'
genai.configure(api_key=GOOGLE_API_KEY)

# Carrega produtos do edital
CAMINHO_EDITAL = r"C:\Users\pietr\Meu Drive\arte_comercial\ORÇARMENTO\ORÇANDO\U_985919_N_900662025_TESTE.xlsx"
df_edital = pd.read_excel(CAMINHO_EDITAL)

# Carrega base de fornecedores (já tratada com GEMINI via `gemini_base.py`)
CAMINHO_BASE = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\FORNECEDORES\data_base.xlsx"
df_base = pd.read_excel(CAMINHO_BASE)

# Pré-processa base para JSON limitado
df_base_filtrado = df_base[["DESCRICAO", "Marca", "Modelo", "Valor"]].head(1000)  # Limite para não estourar o token limit
base_produtos_json = df_base_filtrado.to_json(orient="records", force_ascii=False, indent=2)

# Itera sobre os produtos do edital
for idx, row in df_edital.head(10).iterrows():
    descricao_item = row["DESCRICAO"]
    unidade = row.get("UNIDADE", "unid.")
    quantidade = row.get("QTDE", 1)
    valor_unit = row.get("VALOR_UNIT", 0)
    valor_total = row.get("VALOR_TOTAL", 0)

    prompt = f"""
<identidade>

Você é um consultor sênior em instrumentos musicais, com mais de 20 anos de experiência em descrições de produtos voltados para instrumentos musicais, equipamentos de som, áudio profissional e eletrônicos técnicos...

</identidade>

<item_edital>

Item nº {idx+1}
Descrição: {descricao_item}
Unidade: {unidade}
Quantidade: {quantidade}
Valor Unitário Ref.: {valor_unit}
Valor Total Ref.: {valor_total}

</item_edital>

<base_fornecedores>

{base_produtos_json}

</base_fornecedores>

<objetivo>

Compare tecnicamente o item do edital com os produtos da base de fornecedores acima. Use critérios de compatibilidade técnica, preço com margem (53%) e semanântica. Se houver mais de um produto compatível, priorize-os de acordo com os critérios. Se houver mais de um produto compatível, priorize-os de acordo com melhor preço.

</objetivo>

<saida_esperada>

Tabela com:
- Produto Sugerido
- Marca
- Código/Link
- Preço Fornecedor
- Preço com Margem 53%
- Comparação Técnica
- % Compatibilidade
- Justificativa Técnica/Jurídica
</saida_esperada>

<conclusao>
📊 Geração de Tabela
Para finalizar a avaliação de todos os itens, crie uma tabela com os produtos sugeridos. Segue o exemplo:
Após a análise, gere uma planilha estruturada com os seguintes campos:

Item Edital| Descrição Edital | Unidade de Medida | Quantidade | Valor Unitário de Referência | Valor Total de Referência  | Marca Sugerida | Produto Sugerido | Preço Fornecedor | Preço com Margem 53% | Comparação Técnica | % Compatibilidade

"""

    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)

    print(f"\n=== ITEM {idx+1} ===")
    print(response.text)
