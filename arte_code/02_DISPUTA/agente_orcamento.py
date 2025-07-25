import pandas as pd
import re
import difflib
import os
import glob
from nltk.stem import SnowballStemmer  # Para stemming em português
import nltk
nltk.download('punkt')  # Baixe se necessário

stemmer = SnowballStemmer("portuguese")

def normalizar_texto(texto):
    if not isinstance(texto, str):
        return ""
    texto = texto.lower()
    texto = re.sub(r"[^\w\s]", " ", texto)  # remove pontuação
    texto = re.sub(r"\s+", " ", texto)      # remove espaços múltiplos
    return texto.strip()

def extrair_palavras_chave(texto):
    palavras = re.findall(r"\b\w{3,}\b", normalizar_texto(texto))  # Reduzi para 3+ letras para capturar mais
    return set(stemmer.stem(p) for p in palavras)  # Aplica stemming

def calcular_similaridade_regex(chaves_edital, chaves_produto):
    if not chaves_edital or not chaves_produto:
        return 0.0
    intersecao = chaves_edital.intersection(chaves_produto)
    return len(intersecao) / len(chaves_edital) * 100

def calcular_similaridade_fuzzy(texto_edital, texto_produto):
    return difflib.SequenceMatcher(None, texto_edital, texto_produto).ratio() * 100

def processar(edital_path, base_path, salvar_em=None):
    print(f"🔁 Processando {edital_path} com regex melhorado...")

    base_df = pd.read_excel(base_path)
    edital_df = pd.read_excel(edital_path)

    resultados = []
    matches = 0
    economia_total = 0.0

    for _, item in edital_df.iterrows():
        texto_edital = item["Item"]  # Descrição do edital
        chaves_edital = extrair_palavras_chave(texto_edital)
        print(f"Chaves edital: {chaves_edital}")  # Debug

        melhor_match = None
        melhor_score = 0.0
        melhor_preco = float('inf')

        for _, produto in base_df.iterrows():
            texto_produto = produto["Descrição"]
            chaves_produto = extrair_palavras_chave(texto_produto)
            print(f"Chaves produto {produto['Item']}: {chaves_produto}")  # Debug opcional

            score_regex = calcular_similaridade_regex(chaves_edital, chaves_produto)
            score_fuzzy = calcular_similaridade_fuzzy(texto_edital, texto_produto)
            score_combinado = (score_regex * 0.5) + (score_fuzzy * 0.5)  # Média ponderada

            if score_combinado > melhor_score or (score_combinado == melhor_score and produto["Valor"] < melhor_preco):
                melhor_score = score_combinado
                melhor_match = produto
                melhor_preco = produto["Valor"]

        valor_ref_unit = item.get("Valor Unitário (R$)", 0)
        qtd = item.get("Quantidade Total", 1)
        valor_ref_total = valor_ref_unit * qtd

        if melhor_score >= 40:  # Threshold ajustado para mais matches realistas
            matches += 1
            preco_fornecedor = melhor_match["Valor"]
            preco_disputa = preco_fornecedor * 1.53
            economia = max(0, valor_ref_total - (preco_disputa * qtd))
            economia_total += economia
            pode_substituir = "Sim"
            exige_impugnacao = "Não"
            obs_juridica = "Compatível com princípios de economicidade e isonomia (Lei 14.133/21)."
            comparacao = f"Semelhanças: Interseção stemmed {score_regex:.2f}% + Fuzzy {score_fuzzy:.2f}%. Diferenças: Ajustes baseados em specs aproximadas."
        else:
            preco_fornecedor = 0
            preco_disputa = 0
            pode_substituir = "Não"
            exige_impugnacao = "Sim, ausência de equivalente."
            obs_juridica = "Buscar impugnação para inclusão de equivalentes ou pesquisa de mercado. [Não Verificado]"
            comparacao = "Nenhum produto compatível na base."

        resultado = {
            # Colunas do Edital
            "Número do Item": item.get("Número do Item", "N/A"),
            "Item do Edital": texto_edital,
            "Quantidade Total": qtd,
            "Valor Unitário Edital (R$)": valor_ref_unit,
            "Valor Ref. Total": valor_ref_total,
            "Unidade de Fornecimento": item.get("Unidade de Fornecimento", "N/A"),
            "Intervalo Mínimo entre Lances (R$)": item.get("Intervalo Mínimo entre Lances (R$)", "N/A"),
            "Local de Entrega (Quantidade)": item.get("Local de Entrega (Quantidade)", "N/A"),
            
            # Colunas da Base e Análise
            "Marca": melhor_match["Marca"] if melhor_match is not None else "N/A",
            "Produto Sugerido": melhor_match["Item"] if melhor_match is not None else "N/A",
            "Descrição do Produto": melhor_match["Descrição"] if melhor_match is not None else "N/A",
            "Preço Fornecedor": preco_fornecedor,
            "Preço com Margem 53% (para Disputa)": preco_disputa,
            "Comparação Técnica": comparacao,
            "% Compatibilidade": round(melhor_score, 2),
            "Pode Substituir?": pode_substituir,
            "Exige Impugnação?": exige_impugnacao,
            "Observação Jurídica": obs_juridica,
            "Estado": melhor_match["Estado"] if melhor_match is not None else "N/A",
            "Foto": melhor_match["Foto"] if melhor_match is not None else "N/A"
        }
        
        resultados.append(resultado)

    df_final = pd.DataFrame(resultados)
    
    if salvar_em:
        df_final.to_excel(salvar_em, index=False)
        print(f"✅ Resultado salvo em: {salvar_em}")
    
    # Resumo
    resumo = f"Resumo: Matches encontrados: {matches}, economia total estimada: {economia_total:.2f} (baseada no preço com margem vs. referência)."
    print(resumo)
    
    return df_final

# Processar todos os arquivos no diretório
if __name__ == "__main__":
    edital_dir = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\ORCAMENTOS"
    base_path = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\P_FAZER\data_base.xlsx"
    xlsx_files = glob.glob(os.path.join(edital_dir, "*.xlsx"))
    
    for file in xlsx_files:
        try:
            salvar_em = os.path.join(edital_dir, f"{os.path.splitext(os.path.basename(file))[0]}_estudo.xlsx")
            resultado = processar(file, base_path, salvar_em)
            print(resultado.head())  # Preview
        except Exception as e:
            print(f"Erro ao processar {file}: {e}")