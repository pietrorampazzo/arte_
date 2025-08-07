"""
Automação para comparação de itens de edital com base de fornecedores usando Google Gemini.

Requisitos:
- Google Generative AI API configurada
- Pandas para manipulação de dados
- Excel e CSV para exportação de resultados
- Base de fornecedores pré-processada para compatibilidade com o modelo

SOLUÇÃO DEFINITIVA: Encontrar o produto mais adequado da base de fornecedores para cada item do edital, 
priorizando compatibilidade técnica e preço.Visando a lei de licitações e a melhor proposta para o cliente.
Lei 14.133/2021 e Lei 8.666/1993.

Autor: arte_comercial
Data: 03/07/2025
Versão: 1.1.0

"""
# arte_largeheavy.py
import pandas as pd
import google.generativeai as genai
import os
import time

# --- CONFIGURAÇÕES ---
# É uma boa prática carregar chaves de API de variáveis de ambiente para segurança
# GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', 'SUA_CHAVE_API_AQUI')
modelo = "gemini-2.0-flash"
GOOGLE_API_KEY = 'AIzaSyBdrzcton2jUCv5PSaXE38UCp-l8O42Fvc' # Mantendo como no seu exemplo
genai.configure(api_key=GOOGLE_API_KEY)

# Caminhos para os arquivos
CAMINHO_EDITAL = r"C:\Users\pietr\Meu Drive\arte_comercial\ORÇARMENTO\ORÇANDO\pregão_gemini_fazer_Copia.xlsx"
CAMINHO_BASE = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\base_bling.xlsx"
output_dir = r"C:\Users\pietr\Meu Drive\arte_comercial\ORÇARMENTO\RESULTADOS"

# --- CARREGAMENTO E PRÉ-PROCESSAMENTO DOS DADOS ---
try:
    df_edital = pd.read_excel(CAMINHO_EDITAL)
    df_base = pd.read_excel(CAMINHO_BASE)
    print(f"✅ Edital carregado: {len(df_edital)} itens")
    print(f"✅ Base carregada: {len(df_base)} produtos")
except FileNotFoundError as e:
    print(f"Erro: Arquivo não encontrado. Verifique os caminhos. Detalhes: {e}")
    exit() # Encerra o script se os arquivos não forem encontrados

# Pré-processa base para JSON limitado
# Limitar a base de fornecedores aqui é uma boa estratégia para controlar o tamanho do prompt
df_base_filtrado = df_base[["DESCRICAO", "Marca", "Modelo", "Valor"]].head(3000)
base_produtos_json = df_base_filtrado.to_json(orient="records", force_ascii=False, indent=2)
print(f"✅ Base filtrada: {len(df_base_filtrado)} produtos para análise")

# --- PROCESSAMENTO COM O GEMINI ---
resultados = []
model = genai.GenerativeModel(modelo) 
total_itens = len(df_edital)

# Itera sobre os produtos do edital
for idx, row in df_edital.iterrows():
    # Verifica se a linha contém os campos necessários
    campos_necessarios = ["ARQUIVO", "Nº", "DESCRICAO", "UNID_FORN", "QTDE", "VALOR_UNIT", "VALOR_TOTAL", "LOCAL_ENTREGA", "INTERVALO_LANCES"]
    if not all(col in row for col in campos_necessarios):
        print(f"⚠️ Linha {idx + 1} não contém todos os campos necessários. Pulando...")
        continue
    
    # Coleta de dados da linha do edital
    arquivo = row["ARQUIVO"]
    item_num = row["Nº"]
    descricao_item = row["DESCRICAO"]
    unidade = row["UNID_FORN"]
    quantidade = row["QTDE"]
    valor_unit = row["VALOR_UNIT"]
    valor_total = row["VALOR_TOTAL"]
    local_entrega = row["LOCAL_ENTREGA"]
    intervalo_lances = row["INTERVALO_LANCES"]
    
    # Montagem do prompt
    prompt = f"""
<identidade>
Você é um consultor sênior em instrumentos musicais, com mais de 20 anos de experiência.
</identidade>

<item_edital>
ARQUIVO: {arquivo}
Item nº {item_num}
Descrição: {descricao_item}
Unidade: {unidade}
Quantidade: {quantidade}
Valor Unitário Ref.: {valor_unit}
Valor Total Ref.: {valor_total}
Local Entrega: {local_entrega}
Intervalo de Lances: {intervalo_lances}
</item_edital>

<base_fornecedores>
{base_produtos_json}
</base_fornecedores>

<objetivo>
Encontre o produto mais compatível tecnicamente com menor preço 50% abaixo do valor unitário do item do edital. 
Aplique uma margem de 53% sobre o preço do fornecedor para chegar ao preço final.
</objetivo>

<formato_saida>
Responda APENAS com uma linha no formato de tabela, sem cabeçalho:
| Marca Sugerida | Modelo Sugerido | Preço Fornecedor | Preço com Margem 53% | % Compatibilidade |
</formato_saida>
"""
    
    print(f"Processando item {idx + 1}/{total_itens}: {descricao_item[:50]}...")

    try:
        response = model.generate_content(prompt)
        tabela_texto = response.text.strip()
        linhas = [linha for linha in tabela_texto.split('\n') if '|' in linha and not linha.strip().startswith('|--')]
        
        if len(linhas) > 0:
            # Pega a última linha com dados (ignora cabeçalhos)
            linha_dados = linhas[-1]
            colunas = [col.strip() for col in linha_dados.strip('|').split('|')]
            
            # CORREÇÃO PRINCIPAL: Mudança de >= 10 para >= 5
            if len(colunas) >= 5:
                # ESTRUTURA CORRIGIDA
                resultados.append({
                    'ARQUIVO': arquivo,
                    'Nº': item_num,
                    'DESCRICAO': descricao_item,
                    'UNID_FORN': unidade,
                    'QTDE': quantidade,
                    'VALOR_UNIT': valor_unit,
                    'VALOR_TOTAL': valor_total,
                    'LOCAL_ENTREGA': local_entrega,
                    'INTERVALO_LANCES': intervalo_lances,
                    'Marca Sugerida': colunas[0],
                    'Modelo Sugerido': colunas[1],
                    'Preço Fornecedor': colunas[2],
                    'Preço com Margem 53%': colunas[3],
                    '% Compatibilidade': colunas[4]
                })
                print(f"✅ Sucesso: Item {idx + 1} processado")
            else:
                print(f"⚠️ AVISO: Colunas insuficientes no item {idx + 1} (recebidas: {len(colunas)})")
                print(f"   Resposta: {tabela_texto[:100]}...")
        else:
            print(f"⚠️ AVISO: Sem tabela válida no item {idx + 1}")
            print(f"   Resposta: {tabela_texto[:100]}...")

    except Exception as e:
        print(f"❌ ERRO no item {idx + 1}: {e}")

    # Pausa otimizada
    time.sleep(80)# 60 segundos entre as requisições para evitar sobrecarga

# --- EXPORTAÇÃO CORRIGIDA ---
if resultados:
    colunas_exportacao = [
        'ARQUIVO', 'Nº', 'DESCRICAO', 'UNID_FORN', 'QTDE', 
        'VALOR_UNIT', 'VALOR_TOTAL', 'LOCAL_ENTREGA', 'INTERVALO_LANCES',
        'Marca Sugerida', 'Modelo Sugerido', 
        'Preço Fornecedor', 'Preço com Margem 53%', '% Compatibilidade'
    ]
    
    df_resultados = pd.DataFrame(resultados)
    
    # Garante ordem correta e remove duplicatas
    df_resultados = df_resultados[colunas_exportacao].drop_duplicates()
    
    os.makedirs(output_dir, exist_ok=True)
    caminho_excel = os.path.join(output_dir, "arte_gemini_heavy.xlsx")
    df_resultados.to_excel(caminho_excel, index=False)
    
    print(f"\n✅ SUCESSO: {len(df_resultados)} itens exportados para {caminho_excel}")
    print(f"📊 Taxa de sucesso: {len(df_resultados)}/{total_itens} ({len(df_resultados)/total_itens*100:.1f}%)")
else:
    print("\n⚠️ Nenhum resultado para exportar")

print("\n🎉 Processo concluído!")