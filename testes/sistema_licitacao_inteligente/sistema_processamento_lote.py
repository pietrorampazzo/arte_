# sistema_processamento_lote.py
import pandas as pd
import os
import re
import sys
from testes.sistema_licitacao_inteligente.sistema_matching_final_producao import SistemaMatchingLicitacao

def carregar_base_produtos(caminho_base):
    """Carrega e padroniza a base de produtos"""
    df = pd.read_excel(caminho_base)
    colunas_necessarias = ['Item', 'Descrição', 'Marca', 'Valor', 'Estado', 'Foto']
    for col in colunas_necessarias:
        if col not in df.columns:
            raise ValueError(f"Coluna obrigatória não encontrada: {col}")
    return df

def carregar_edital(caminho_edital):
    """Carrega dados do edital com tratamento de erros"""
    try:
        df = pd.read_excel(caminho_edital)
        colunas_necessarias = ['Item', 'Quantidade Total', 'Valor Unitário (R$)']
        for col in colunas_necessarias:
            if col not in df.columns:
                raise ValueError(f"Coluna obrigatória não encontrada: {col}")
        return df
    except Exception as e:
        print(f"Erro ao carregar edital: {str(e)}")
        return None

def processar_arquivos(diretorio_editais, caminho_base, json_path, diretorio_saida):
    """Processa todos os arquivos de edital no diretório"""
    sistema = SistemaMatchingLicitacao(json_path)
    base_produtos = carregar_base_produtos(caminho_base)
    
    if not os.path.exists(diretorio_saida):
        os.makedirs(diretorio_saida)
    
    resultados_consolidados = []
    arquivos_processados = 0
    
    for arquivo in os.listdir(diretorio_editais):
        if not arquivo.endswith(('.xlsx', '.xls')):
            continue
            
        caminho_completo = os.path.join(diretorio_editais, arquivo)
        print(f"\nProcessando: {arquivo}")
        
        edital_df = carregar_edital(caminho_completo)
        if edital_df is None:
            continue
        
        try:
            caminho_saida = os.path.join(diretorio_saida, f"RESULTADO_{os.path.splitext(arquivo)[0]}.xlsx")
            resultado = sistema.processar_edital(edital_df, base_produtos, caminho_saida)
            resultado['Arquivo Origem'] = arquivo
            resultados_consolidados.append(resultado)
            arquivos_processados += 1
        except Exception as e:
            print(f"Erro no processamento: {str(e)}")
    
    if resultados_consolidados:
        df_consolidado = pd.concat(resultados_consolidados)
        caminho_consolidado = os.path.join(diretorio_saida, "CONSOLIDADO.xlsx")
        df_consolidado.to_excel(caminho_consolidado, index=False)
        print(f"\n✅ Processamento completo! {arquivos_processados} arquivos processados")
        print(f"✅ Consolidado salvo em: {caminho_consolidado}")
        return df_consolidado
    
    print("\nNenhum arquivo processado com sucesso")
    return None

def gerar_relatorio_avancado(df_consolidado, caminho_saida):
    """Gera relatório analítico completo"""
    if df_consolidado is None or df_consolidado.empty:
        return
    
    # Cálculos estatísticos
    resumo = {
        'Total de Itens': len(df_consolidado),
        'Itens Substituíveis': len(df_consolidado[df_consolidado['Pode Substituir?'] == 'Sim']),
        'Taxa de Sucesso (%)': round(len(df_consolidado[df_consolidado['Pode Substituir?'] == 'Sim']) / len(df_consolidado) * 100, 2),
        'Economia Total (R$)': df_consolidado['Economia Estimada (R$)'].sum(),
        'Economia Média por Item (R$)': df_consolidado['Economia Estimada (R$)'].mean(),
        'Compatibilidade Média (%)': df_consolidado['% Compatibilidade'].mean()
    }
    
    # Análise por categoria
    df_consolidado['Categoria'] = df_consolidado['Item do Edital'].apply(
        lambda x: re.search(r"(percussão|sopro|piano|amplificador|mesa áudio|microfone|caixa acústica|projetor|instrumento)", x, re.I).group(0) 
        if re.search(r"(percussão|sopro|piano|amplificador|mesa áudio|microfone|caixa acústica|projetor|instrumento)", x, re.I) 
        else 'Outros')
    
    analise_categorias = df_consolidado.groupby('Categoria').agg({
        'Pode Substituir?': lambda x: (x == 'Sim').sum(),
        'Economia Estimada (R$)': 'sum',
        '% Compatibilidade': 'mean'
    }).rename(columns={
        'Pode Substituir?': 'Itens Substituíveis',
        '% Compatibilidade': 'Compatibilidade Média'
    })
    
    # Salvar relatório
    with pd.ExcelWriter(caminho_saida) as writer:
        df_consolidado.to_excel(writer, sheet_name='Dados Completos', index=False)
        
        pd.DataFrame([resumo]).to_excel(
            writer, sheet_name='Resumo Executivo', index=False)
        
        analise_categorias.to_excel(
            writer, sheet_name='Análise por Categoria')
        
        # Top 10 economias
        df_consolidado.nlargest(10, 'Economia Estimada (R$)').to_excel(
            writer, sheet_name='Top 10 Economias', index=False)
    
    print(f"📊 Relatório analítico salvo em: {caminho_saida}")

if __name__ == "__main__":
    # Configurações
    DIR_EDITAIS = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\ORCAMENTOS"
    DIR_SAIDA = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\RESULTADOS"
    ARQUIVO_BASE = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\data_base.xlsx"
    JSON_CATEGORIAS = r"C:\Users\pietr\.vscode\arte_\testes\gov_reges.json"
    RELATORIO_ANALITICO = os.path.join(DIR_SAIDA, "RELATORIO_ANALITICO.xlsx")
    
    print("=" * 60)
    print("SISTEMA DE MATCHING PARA LICITAÇÕES - PROCESSAMENTO EM LOTE")
    print("=" * 60)
    
    # Processamento principal
    consolidado = processar_arquivos(
        diretorio_editais=DIR_EDITAIS,
        caminho_base=ARQUIVO_BASE,
        json_path=JSON_CATEGORIAS,
        diretorio_saida=DIR_SAIDA
    )
    
    # Geração do relatório avançado
    if consolidado is not None:
        gerar_relatorio_avancado(consolidado, RELATORIO_ANALITICO)
    
    print("\n" + "=" * 60)
    print("PROCESSAMENTO CONCLUÍDO")
    print("=" * 60)