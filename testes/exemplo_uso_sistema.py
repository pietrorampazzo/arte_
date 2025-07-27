"""
Sistema de Matching para Licitações - Processamento em Lote
==========================================================

Este script processa todos os arquivos de licitação do diretório especificado,
aplicando o matching com a base de produtos e gerando relatórios consolidados.
"""

import pandas as pd
import os
from typing import List, Dict, Optional
from testes.sistema_licitacao_inteligente.sistema_matching_final_producao import SistemaMatchingLicitacao

def processar_licitacao(edital_data: List[Dict], base_produtos: pd.DataFrame,
                       salvar_em: str = None) -> pd.DataFrame:
    """
    Função principal para processar uma licitação
    
    Args:
        edital_data: Lista de dicionários com itens do edital
        base_produtos: DataFrame com produtos disponíveis
        salvar_em: Caminho para salvar resultado (opcional)
        
    Returns:
        DataFrame com resultados do matching
    """
    sistema = SistemaMatchingLicitacao()
    return sistema.processar_edital(edital_data, base_produtos, salvar_em)

def carregar_edital_do_excel(caminho_excel: str) -> List[Dict]:
    """
    Carrega dados do edital de um arquivo Excel, tentando todas as abas se necessário
    
    Args:
        caminho_excel: Caminho para o arquivo Excel do edital
        
    Returns:
        Lista de dicionários com os dados do edital
    """
    try:
        # Tenta ler todas as abas
        xls = pd.ExcelFile(caminho_excel)
        sheets = xls.sheet_names
        
        for sheet in sheets:
            try:
                df_edital = pd.read_excel(caminho_excel, sheet_name=sheet)
                if not df_edital.empty:
                    # Verifica se tem colunas mínimas necessárias
                    if 'Item do Edital' in df_edital.columns or 'Descrição' in df_edital.columns:
                        print(f"✅ Edital carregado da aba '{sheet}': {len(df_edital)} itens")
                        return df_edital.to_dict('records')
            except:
                continue
        
        print(f"⚠️ Nenhuma aba válida encontrada em {os.path.basename(caminho_excel)}")
        return []
        
    except Exception as e:
        print(f"❌ Erro ao carregar edital {os.path.basename(caminho_excel)}: {str(e)}")
        return []

def processar_todos_editais(diretorio_editais: str, base_produtos: pd.DataFrame,
                           diretorio_saida: str = None) -> pd.DataFrame:
    """
    Processa todos os arquivos Excel no diretório de editais
    
    Args:
        diretorio_editais: Caminho para o diretório com os arquivos de edital
        base_produtos: DataFrame com produtos disponíveis
        diretorio_saida: Diretório para salvar resultados individuais (opcional)
        
    Returns:
        DataFrame consolidado com todos os resultados
    """
    consolidado = []
    arquivos_processados = 0
    
    print(f"\n🔍 Buscando arquivos em {diretorio_editais}...")
    
    # Lista todos os arquivos Excel no diretório
    arquivos = [f for f in os.listdir(diretorio_editais) 
               if f.endswith(('.xlsx', '.xls')) and not f.startswith('~$')]
    
    if not arquivos:
        print("❌ Nenhum arquivo Excel encontrado no diretório!")
        return pd.DataFrame()
    
    print(f"📋 {len(arquivos)} arquivos encontrados. Iniciando processamento...\n")
    
    for arquivo in arquivos:
        caminho_completo = os.path.join(diretorio_editais, arquivo)
        nome_arquivo = os.path.splitext(arquivo)[0]
        
        print(f"📄 Processando {arquivo}...")
        
        # Carrega dados do edital
        edital_data = carregar_edital_do_excel(caminho_completo)
        
        if not edital_data:
            print(f"⚠️ Pulando {arquivo} - sem dados válidos")
            continue
        
        # Processa o edital
        try:
            caminho_saida = os.path.join(diretorio_saida, f"RESULTADO_{nome_arquivo}.xlsx") if diretorio_saida else None
            
            resultado = processar_licitacao(
                edital_data=edital_data,
                base_produtos=base_produtos,
                salvar_em=caminho_saida
            )
            
            # Adiciona identificação do arquivo original
            resultado['Arquivo Origem'] = arquivo
            consolidado.append(resultado)
            arquivos_processados += 1
            
            if caminho_saida:
                print(f"   ✅ Resultado salvo em {caminho_saida}")
            
        except Exception as e:
            print(f"❌ Erro ao processar {arquivo}: {str(e)}")
            continue
    
    if consolidado:
        df_consolidado = pd.concat(consolidado, ignore_index=True)
        print(f"\n🎉 Processamento concluído! {arquivos_processados}/{len(arquivos)} arquivos processados com sucesso.")
        return df_consolidado
    else:
        print("\n❌ Nenhum arquivo foi processado com sucesso.")
        return pd.DataFrame()

def gerar_relatorio_consolidado(resultados: pd.DataFrame, caminho_saida: str):
    """
    Gera um relatório consolidado com estatísticas de todos os processamentos
    
    Args:
        resultados: DataFrame consolidado com todos os resultados
        caminho_saida: Caminho completo para salvar o relatório
    """
    if resultados.empty:
        print("⚠️ Nenhum dado para gerar relatório consolidado")
        return
    
    # Cálculo de estatísticas
    estatisticas = {
        'Total de Itens Processados': len(resultados),
        'Itens com Match': len(resultados[resultados['Pode Substituir?'] == 'Sim']),
        'Taxa de Sucesso (%)': len(resultados[resultados['Pode Substituir?'] == 'Sim']) / len(resultados) * 100,
        'Economia Total Estimada (R$)': resultados['Economia Estimada (R$)'].sum(),
        'Número de Arquivos Processados': resultados['Arquivo Origem'].nunique()
    }
    
    # Salva o relatório
    try:
        with pd.ExcelWriter(caminho_saida) as writer:
            # Salva os dados completos
            resultados.to_excel(writer, sheet_name='Dados Completos', index=False)
            
            # Salva um resumo estatístico
            pd.DataFrame.from_dict(estatisticas, orient='index', columns=['Valor']).to_excel(
                writer, sheet_name='Resumo')
            
            # Salva os melhores matches por arquivo
            melhores_matches = resultados[resultados['Pode Substituir?'] == 'Sim']
            if not melhores_matches.empty:
                melhores_matches.to_excel(writer, sheet_name='Melhores Matches', index=False)
            
        print(f"\n📊 Relatório consolidado salvo em: {caminho_saida}")
    except Exception as e:
        print(f"❌ Erro ao salvar relatório consolidado: {str(e)}")

def main():
    print("=" * 60)
    print("SISTEMA DE MATCHING PARA LICITAÇÕES - PROCESSAMENTO EM LOTE")
    print("=" * 60)
    
    # Configurações (ajuste conforme necessário)
    DIR_EDITAIS = r'C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\ORCAMENTOS'
    DIR_SAIDA = r'C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\RESULTADOS'
    ARQUIVO_BASE = r'C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\data_base.xlsx'
    RELATORIO_CONSOLIDADO = os.path.join(DIR_SAIDA, 'RELATORIO_CONSOLIDADO.xlsx')
    
    # Verifica e cria diretório de saída se necessário
    os.makedirs(DIR_SAIDA, exist_ok=True)
    
    # Carrega base de produtos
    try:
        print("\n📦 Carregando base de produtos...")
        base_produtos = pd.read_excel(ARQUIVO_BASE)
        print(f"✅ Base carregada: {len(base_produtos)} produtos disponíveis")
    except Exception as e:
        print(f"❌ Erro ao carregar base de produtos: {str(e)}")
        return
    
    # Processa todos os editais
    resultados = processar_todos_editais(
        diretorio_editais=DIR_EDITAIS,
        base_produtos=base_produtos,
        diretorio_saida=DIR_SAIDA
    )
    
    # Gera relatório consolidado se houve resultados
    if not resultados.empty:
        gerar_relatorio_consolidado(resultados, RELATORIO_CONSOLIDADO)
    
    print("\n" + "=" * 60)
    print("PROCESSAMENTO CONCLUÍDO")
    print("=" * 60)

if __name__ == "__main__":
    main()