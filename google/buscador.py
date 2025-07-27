import pandas as pd
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import google.generativeai as genai
import os
from tqdm import tqdm
from api import GOOGLE_API_KEY
# --- CONFIGURAÇÕES ---
# Cole sua chave de API do Google AI Studio aqui
GOOGLE_API_KEY = GOOGLE_API_KEY

# Pastas
PASTA_INDICE = "indice_faiss"
PASTA_EDITAIS = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\ORCAMENTOS"
PASTA_RESULTADOS = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\RESULTADOS"

# Arquivos de índice (gerados pelo indexador.py)
ARQUIVO_INDICE = os.path.join(PASTA_INDICE, "produtos.index")
ARQUIVO_MAPEAMENTO = os.path.join(PASTA_INDICE, "mapeamento_produtos.csv")

# Modelo de embedding (DEVE SER O MESMO do indexador.py)
NOME_MODELO = 'all-mpnet-base-v2'

# Limiar de similaridade para considerar um match ruim
LIMIAR_SIMILARIDADE = 0.70 # Corresponde a 70%

# --- INICIALIZAÇÃO DOS MODELOS ---
try:
    genai.configure(api_key=GOOGLE_API_KEY)
    model_generativo = genai.GenerativeModel('gemini-1.5-flash-latest') # 'flash' é rápido e econômico
except Exception as e:
    print(f"ERRO ao configurar a API do Google: {e}")
    print("Verifique se a sua GOOGLE_API_KEY está correta.")
    exit()

print("Carregando modelo de embedding...")
model_embedding = SentenceTransformer(NOME_MODELO)

print("Carregando índice Faiss e mapeamento de produtos...")
try:
    index = faiss.read_index(ARQUIVO_INDICE)
    df_mapeamento = pd.read_csv(ARQUIVO_MAPEAMENTO, index_col=0)
except FileNotFoundError:
    print("ERRO: Arquivos de índice não encontrados. Execute o 'indexador.py' primeiro.")
    exit()

# --- FUNÇÕES ---

def gerar_comparacao_tecnica_com_llm(item_edital, produto_sugerido):
    """Usa o Gemini para gerar uma comparação técnica entre dois itens."""
    prompt = f"""
    Analise os dois produtos a seguir e gere uma comparação técnica concisa.

    Item Requisitado no Edital:
    "{item_edital}"

    Produto Sugerido de nossa base:
    "{produto_sugerido}"

    Sua tarefa é criar uma análise para a coluna "Comparação Técnica" de uma planilha.
    Seja objetivo e profissional.
    - Se o produto sugerido for um bom substituto, explique por quê (ex: "Produto compatível, atende às especificações de potência e conectividade.").
    - Se houver diferenças, aponte-as (ex: "Atenção: O modelo sugerido tem 600W, enquanto o edital pede 800W.").
    - Se for totalmente incompatível, seja claro (ex: "Incompatível. O edital pede um microfone e o produto sugerido é um cabo.").

    A resposta deve ser um parágrafo curto.
    """
    try:
        response = model_generativo.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Erro ao gerar comparação: {e}"

def processar_edital(caminho_edital):
    """Função principal que processa uma única planilha de edital."""
    nome_arquivo = os.path.basename(caminho_edital)
    print(f"\nProcessando edital: {nome_arquivo}")

    df_edital = pd.read_excel(caminho_edital)
    resultados = []

    # Usando tqdm para uma barra de progresso
    for _, row in tqdm(df_edital.iterrows(), total=df_edital.shape[0], desc="Analisando itens"):
        item_catmat = str(row['Item']) if not pd.isna(row['Item']) else ""
        
        # Gerar embedding para o item do edital
        embedding_consulta = model_embedding.encode([item_catmat])
        embedding_consulta = np.array(embedding_consulta).astype('float32')
        faiss.normalize_L2(embedding_consulta)

        # Buscar no índice (k=1 para pegar apenas o melhor resultado)
        distancias, indices = index.search(embedding_consulta, 1)
        
        idx_melhor_match = indices[0][0]
        similaridade = distancias[0][0] # Com IndexFlatIP e vetores normalizados, isso é a similaridade de cosseno

        # Preparar dados do resultado
        dados_resultado = row.to_dict()

        if similaridade >= LIMIAR_SIMILARIDADE:
            produto_sugerido_info = df_mapeamento.iloc[idx_melhor_match]
            
            # Adicionar colunas do nosso estudo
            dados_resultado['Marca Sugerida'] = produto_sugerido_info['Marca']
            dados_resultado['Produto Sugerido'] = produto_sugerido_info['Modelo']
            dados_resultado['Descrição do Produto Sugerido'] = produto_sugerido_info['Descrição']
            dados_resultado['Preço Produto'] = produto_sugerido_info['Valor']
            dados_resultado['% Compatibilidade'] = f"{similaridade:.2%}"
            
            texto_produto_sugerido = f"Marca: {produto_sugerido_info['Marca']}. Modelo: {produto_sugerido_info['Modelo']}. Descrição: {produto_sugerido_info['Descrição']}"
            dados_resultado['Comparação Técnica'] = gerar_comparacao_tecnica_com_llm(item_catmat, texto_produto_sugerido)
        else:
            # Se a similaridade for muito baixa, não sugerimos nada
            dados_resultado['Marca Sugerida'] = "N/A - Baixa Compatibilidade"
            dados_resultado['Produto Sugerido'] = "N/A"
            dados_resultado['Descrição do Produto Sugerido'] = "N/A"
            dados_resultado['Preço Produto'] = "N/A"
            dados_resultado['% Compatibilidade'] = f"{similaridade:.2%}"
            dados_resultado['Comparação Técnica'] = "Nenhuma sugestão viável encontrada na base de dados devido à baixa similaridade com o item solicitado."

        resultados.append(dados_resultado)
        
    # Criar o DataFrame final e salvar
    df_resultado = pd.DataFrame(resultados)
    
    # Garantir a ordem correta das colunas
    colunas_finais = list(df_edital.columns) + [
        'Marca Sugerida', 'Produto Sugerido', 'Descrição do Produto Sugerido', 
        'Preço Produto', 'Comparação Técnica', '% Compatibilidade'
    ]
    df_resultado = df_resultado[colunas_finais]

    nome_base, extensao = os.path.splitext(nome_arquivo)
    caminho_saida = os.path.join(PASTA_RESULTADOS, f"{nome_base}_estudo{extensao}")
    
    if not os.path.exists(PASTA_RESULTADOS):
        os.makedirs(PASTA_RESULTADOS)

    df_resultado.to_excel(caminho_saida, index=False)
    print(f"Estudo salvo em: {caminho_saida}")


# --- SCRIPT PRINCIPAL ---
if __name__ == "__main__":
    # Encontrar todos os arquivos .xlsx na pasta de editais
    arquivos_editais = [
        os.path.join(PASTA_EDITAIS, f) 
        for f in os.listdir(PASTA_EDITAIS) 
        if f.endswith('.xlsx')
    ]
    
    if not arquivos_editais:
        print(f"Nenhum arquivo .xlsx encontrado em '{PASTA_EDITAIS}'.")
    else:
        for edital in arquivos_editais:
            processar_edital(edital)
    
    print("\nProcessamento de todos os editais concluído.")