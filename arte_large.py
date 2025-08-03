# arte_gemini.py
import pandas as pd
import google.generativeai as genai
import os

# CONFIG
GOOGLE_API_KEY = 'AIzaSyBdrzcton2jUCv5PSaXE38UCp-l8O42Fvc'
genai.configure(api_key=GOOGLE_API_KEY)

# Carrega produtos do edital
CAMINHO_EDITAL = r"C:\Users\pietr\Meu Drive\arte_comercial\ORÇARMENTO\ORÇANDO\102309_906242025_TESTE_3.xlsx"
df_edital = pd.read_excel(CAMINHO_EDITAL)

# Carrega base de fornecedores (já tratada com GEMINI via `gemini_base.py`)
CAMINHO_BASE = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\FORNECEDORES\data_base.xlsx"
df_base = pd.read_excel(CAMINHO_BASE)

# Pré-processa base para JSON limitado
df_base_filtrado = df_base[["DESCRICAO", "Marca", "Modelo", "Valor"]].head(1000)  # Limite para não estourar o token limit
base_produtos_json = df_base_filtrado.to_json(orient="records", force_ascii=False, indent=2)

# Lista para armazenar resultados
resultados = []

# Itera sobre os produtos do edital
for idx, row in df_edital.head(50).iterrows():
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
Compare tecnicamente o item do edital com os produtos da base de fornecedores acima. Use critérios de compatibilidade técnica, preço com margem (53%) e semântica. Se houver mais de um produto compatível, priorize-os de acordo com melhor preço.
Retorne apenas o produto que melhor atende ao item do edital, com os melhores preços!
</objetivo>

<saida_esperada>
- Marca Sugerida
- Modelo Sugerido
- Preço Fornecedor
- Preço com Margem 53%
- % Compatibilidade
</saida_esperada>

<conclusao>
📊 Geração de Tabela
Após analisar tudo, crie uma tabela com os produtos sugeridos. Segue o exemplo:
Item Edital | Descrição Edital | Unidade de Medida | Quantidade | Valor Unitário de Referência | Valor Total de Referência | Marca Sugerida | Produto Sugerido | Preço Fornecedor | Preço com Margem 53% | Comparação Técnica | % Compatibilidade
</conclusao>
"""

    model = genai.GenerativeModel("gemini-2.0-flash-lite")
    response = model.generate_content(prompt)

    # Extrair tabela do response (assumindo que Gemini retorna texto formatado como tabela)
    tabela_texto = response.text
    linhas = tabela_texto.split('\n')
    dados_tabela = []
    
    for linha in linhas:
        if '|' in linha:
            colunas = [col.strip() for col in linha.split('|')]
            if len(colunas) >= 12:  # Verifica se a linha tem todas as colunas esperadas
                dados_tabela.append(colunas)

    # Adiciona resultados à lista
    for linha in dados_tabela:
        resultados.append({
            'Item Edital': linha[0],
            'Descrição Edital': linha[1],
            'Unidade de Medida': linha[2],
            'Quantidade': linha[3],
            'Valor Unitário de Referência': linha[4],
            'Valor Total de Referência': linha[5],
            'Marca Sugerida': linha[6],
            'Modelo Sugerido': linha[7],
            'Preço Fornecedor': linha[8],
            'Preço com Margem 53%': linha[9],
            '% Compatibilidade': linha[11]
        })

    print(f"\n=== ITEM {idx+1} ===")
    print(tabela_texto)

# Cria DataFrame com os resultados
df_resultados = pd.DataFrame(resultados)

# Exporta para Excel e CSV
output_dir = r"C:\Users\pietr\Meu Drive\arte_comercial\ORÇARMENTO\RESULTADOS"
os.makedirs(output_dir, exist_ok=True)
df_resultados.to_excel(os.path.join(output_dir, "resultados_arte_gemini.xlsx"), index=False)
df_resultados.to_csv(os.path.join(output_dir, "resultados_arte_gemini.csv"), index=False)
print(f"\nResultados exportados para {output_dir}")