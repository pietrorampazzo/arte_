"""
Automação para categorização e matching de itens de edital com base de fornecedores usando Google Gemini.
Versão: 1.2.0
"""

import pandas as pd
import google.generativeai as genai
import os
import time
import json
import re

# --- CONFIGURAÇÕES ---
modelo = "gemini-2.5-flash-lite"  # Modelo eficiente
GOOGLE_API_KEY = 'AIzaSyBdrzcton2jUCv5PSaXE38UCp-l8O42Fvc'
genai.configure(api_key=GOOGLE_API_KEY)

CAMINHO_EDITAL = r"master_teste.xlsx"  # Ajuste caminhos conforme necessário
CAMINHO_BASE = r"RESULTADO/produtos_categorizados.xlsx"
output_dir = r"RESULTADO"
CAMINHO_SAIDA = os.path.join(output_dir, "arte_heavy_categorizado.xlsx")

# --- CARREGAMENTO ---
try:
    df_edital = pd.read_excel(CAMINHO_EDITAL)
    df_base = pd.read_excel(CAMINHO_BASE)
    print(f"✅ Edital: {len(df_edital)} itens | Base: {len(df_base)} produtos")
except FileNotFoundError as e:
    print(f"Erro: {e}")
    exit()

# --- ESTRUTURA DE CATEGORIAS (para prompt) ---
categorias_prompt = """
ESTRUTURA DE CATEGORIAS (USE APENAS ESTAS):
- INSTRUMENTO_SOPRO: trompete, bombardino, trompa, trombone, tuba, sousafone, clarinete, saxofone, flauta
- INSTRUMENTO_PERCUSSAO: bateria, bumbo, timbales, timpano, surdo, tarol, caixa de guerra, quadriton, tambor, afuché
- INSTRUMENTO_CORDA: violino, viola, violão, guitarra, baixo, violoncelo
- INSTRUMENTO_TECLAS: piano, Lira, teclado digital, Glockenspiel
- ACESSORIO_SOPRO: bocal, Lubrificante, boquilha, surdina, graxa, Lever Oil, oleo lubrificante, palheta de saxofone/clarinete
- ACESSORIO_PERCUSSAO: baqueta, Máquina de Hi Hat, talabarte, pele, esteira, prato, triângulo, carrilhão, sino
- ACESSORIO_CORDA: corda, arco, cavalete
- ACESSORIO_GERAL: estante de partitura, suporte, banco, bag
- EQUIPAMENTO_SOM: caixa de som, amplificador, cubo para guitarra
- EQUIPAMENTO_AUDIO: microfone, mesa áudio, mesa de som, fone de ouvido
- EQUIPAMENTO_CABO: cabo HDMI, xlr M/F, P10, P2xP10, Medusa, caixa medusa, Cabo CAT5e,cabo de rede, cabo CFTV 
- OUTROS: use esta categoria apenas se o produto não se encaixar em nenhuma das categorias acima.
"""

# --- FUNÇÕES AUXILIARES ---
def parse_llm_response(response_text):
    match = re.search(r'\[.*\]', response_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None

def categorizar_item(model, descricao):
    prompt = f"""
Você é um especialista em categorização de produtos musicais.
Sua tarefa é classificar a descrição: "{descricao}"
Usando ESTRITAMENTE as categorias definidas abaixo.
Retorne APENAS uma lista com um objeto JSON: [{{"CATEGORIA_PRINCIPAL": "<categoria>"}}]
Sem texto extra.
{categorias_prompt}
"""
    response = model.generate_content(prompt)
    parsed = parse_llm_response(response.text)
    if parsed and len(parsed) > 0:
        return parsed[0].get('CATEGORIA_PRINCIPAL', 'OUTROS')
    return 'OUTROS'

def selecionar_melhor(model, item_data, base_filtrada_json):
    prompt = f"""
<identidade>
Você é um consultor sênior em instrumentos musicais.
</identidade>

<item_edital>
Descrição: {item_data['DESCRICAO']}
Valor Unitário Ref.: {item_data['VALOR_UNIT']}
</item_edital>

<base_fornecedores>
{base_filtrada_json}
</base_fornecedores>

<objetivo>
Analise tecnicamente os itens de um edital de licitação, buscando correspondência com produtos na base de fornecedores. A saída deve sugerir até 5 itens compatíveis por produto, respeitando critérios técnicos e legais. O objetivo é garantir a proposta mais competitiva, tecnicamente adequada e legalmente defensável.
Compare apenas com produtos da mesma categoria (ex: microfone com microfone, trompete com trompete, e suas subcategorias tambem, como microfone de lapela com microfone de lapela.).
Compare especificações técnicas listadas.
Calcule o índice de compatibilidade:
compatibilidade = (especificações coincidentes / total de especificações do edital) × 100

Validação:
Compatibilidade ≥80%: produto é compatível.
Compatibilidade entre 70% e 80%: produto é alternativa técnica viável.

Priorização entre os compatíveis:
1) Maior compatibilidade técnica.
2) Melhor custo-benefício.
3) Menor preço.

Upgrades relevantes (sem custo adicional).
Lembrete de Conformidade Legal:
A IA deve considerar os princípios da Lei 14.133/21:
Isonomia (não favorecer marcas específicas sem justificativa técnica).
Impessoalidade (análise técnica objetiva).
Economicidade (propor a melhor relação custo-benefício).
Competitividade (permitir disputa entre fornecedores equivalentes).

Resumo das Regras-Chave:
1) Categorias não podem se misturar.
2) Sempre preferir menor preço compatível.
3) Upgrades são bem-vindos se não houver aumento de custo.
4) Tenha certeza que o 

</objetivo>

<formato_saida>
Responda somente com uma única linha no formato Markdown de tabela, sem cabeçalho, sem explicações, sem texto extra:
| Marca Sugerida | Modelo Sugerido | Preço Fornecedor | Preço com Margem 53% | Descrição Fornecedor | % Compatibilidade |

IMPORTANTE:
- Não escreva nada além desta linha de tabela.
- Se não encontrar produto adequado, retorne "| N/A | N/A | N/A | N/A | N/A | 0% |".
- Respeite o formato da tabela, com pipes e colunas exatamente na ordem pedida.
- Não utilize aspas, nem quebre linha.
</formato_saida>
"""
    response = model.generate_content(prompt)
    tabela_texto = response.text.strip()
    linhas = [linha for linha in tabela_texto.split('\n') if '|' in linha and not linha.strip().startswith('|--')]
    if len(linhas) > 0:
        linha_dados = linhas[-1]
        colunas = [col.strip() for col in linha_dados.strip('|').split('|')]
        if len(colunas) >= 6:
            return colunas
    return ['N/A', 'N/A', 'N/A', 'N/A', 'N/A', '0%']

# --- PROCESSAMENTO ---
resultados = []
model = genai.GenerativeModel(modelo)
total_itens = len(df_edital)

for idx, row in df_edital.iterrows():
    item_data = row.to_dict()
    print(f"Processando item {idx + 1}/{total_itens}: {item_data['DESCRICAO'][:50]}...")

    # Passo: Categorizar
    categoria = categorizar_item(model, item_data['DESCRICAO'])
    time.sleep(2)  # Pausa leve

    # Passo: Filtrar base
    df_filtrado = df_base[df_base['categoria_principal'] == categoria]
    if df_filtrado.empty:
        print(f"⚠️ Sem produtos na categoria {categoria}")
        colunas = ['N/A', 'N/A', 'N/A', 'N/A', 'N/A', '0%']
    else:
        base_json = df_filtrado[['categoria_principal', 'subcategoria', 'MARCA', 'MODELO', 'VALOR_MARGEM', 'DESCRICAO']].to_json(orient="records", force_ascii=False, indent=2)

        # Passo: Selecionar melhor via LLM
        colunas = selecionar_melhor(model, item_data, base_json)
    time.sleep(15)  # Pausa para API

    resultados.append({
        'ARQUIVO': item_data['ARQUIVO'],
        'Nº': item_data['Nº'],
        'DESCRICAO': item_data['DESCRICAO'],
        'UNID_FORN': item_data['UNID_FORN'],
        'QTDE': item_data['QTDE'],
        'VALOR_UNIT': item_data['VALOR_UNIT'],
        'VALOR_TOTAL': item_data['VALOR_TOTAL'],
        'LOCAL_ENTREGA': item_data['LOCAL_ENTREGA'],
        'Marca Sugerida': colunas[0],
        'Modelo Sugerido': colunas[1],
        'Preço Fornecedor': colunas[2],
        'Preço com Margem 53%': colunas[3],
        'Descrição Fornecedor': colunas[4],
        '% Compatibilidade': colunas[5]
    })

# --- EXPORTAÇÃO ---
if resultados:
    colunas_exportacao = [
        'ARQUIVO','DESCRICAO','VALOR_UNIT', 'VALOR_TOTAL', 'LOCAL_ENTREGA',
        'Nº', 'UNID_FORN', 'QTDE','Marca Sugerida', 'Modelo Sugerido','Preço com Margem 53%',
        'Preço Fornecedor','Descrição Fornecedor', '% Compatibilidade'
    ]
    df_resultados = pd.DataFrame(resultados)[colunas_exportacao]
    os.makedirs(output_dir, exist_ok=True)
    df_resultados.to_excel(CAMINHO_SAIDA, index=False)
    print(f"✅ Exportado: {CAMINHO_SAIDA}")
else:
    print("⚠️ Sem resultados")