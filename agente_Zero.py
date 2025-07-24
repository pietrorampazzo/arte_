#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zero-Shot 🐢 Lenta🧙 Muito inteligenteIA geral, contexto mais aberto
3. Zero-Shot Classification (ainda mais esperto, tipo uma IA que responde perguntas)
Essa técnica pergunta diretamente para a IA:

“Esse item parece com alguma dessas categorias: Microfone, Caixa de som, Estante, etc.?”

A IA não foi treinada só com nossos dados — ela entende o mundo inteiro. 
Então ela é capaz de responder mesmo sem nunca ter visto aquele texto antes.

Exemplo:
Você diz: “Mesa com 8 canais de entrada para mixagem de áudio”.
A IA responde: “Parece muito com a categoria ‘Mesa de Som’ com 91% de certeza.”
"""

import os
import re
import pandas as pd
from pathlib import Path
from datetime import datetime
from transformers import pipeline

class Config:
    """Configurações básicas"""
    
    # 🔧 AJUSTE AQUI OS CAMINHOS
    PRODUTOS_PATH = r"c:\Users\pietr\OneDrive\Área de Trabalho\ARTE\PRODUTOS.xlsx"
    ORCAMENTOS_PATH = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\ORCAMENTOS"
    
    # Parâmetros
    MARGEM_DISPUTA = 0.53  # 53%
    MIN_COMPATIBILIDADE = 75.0
    MAX_SUGESTOES = 5

# MODELO ZERO-SHOT CLASSIFICATION COM HUGGING FACE

# ⚙️ Inicialize o pipeline (demora só na primeira vez)
zero_shot_classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

def correlacionar_catmat_zero_shot(descricao_edital, categorias_catmat):
    """
    Usa classificação zero-shot para sugerir qual categoria CATMAT
    é mais compatível com a descrição do edital.
    Retorna as top 3 categorias mais prováveis.
    """
    resultado = zero_shot_classifier(
        descricao_edital,
        candidate_labels=categorias_catmat,
        multi_label=False
    )
    
    # Extrair e ordenar os resultados
    scores = list(zip(resultado['labels'], resultado['scores']))
    scores_ordenados = sorted(scores, key=lambda x: x[1], reverse=True)
    return scores_ordenados[:3]


class AnalisadorJuridico:
    """Análise jurídica básica"""
    
    @staticmethod
    def analisar(descricao):
        """Analisa direcionamento"""
        texto = descricao.upper()
        
        # Padrões de direcionamento
        padroes = [
            r'\bMARCA\s+(\w+)',
            r'\bEXCLUSIVAMENTE\b',
            r'\bAPENAS\b',
            r'\bUNICAMENTE\b',
            r'\bEXCLUSIVO\b'
        ]
        
        tem_direcionamento = any(re.search(padrao, texto) for padrao in padroes)
        
        if tem_direcionamento:
            return {
                'exige_impugnacao': True,
                'observacao': 'Possível direcionamento identificado. Recomenda-se impugnação baseada na Lei 14.133/21 (Art. 7º §5º) para garantir competitividade.',
                'risco': 'ALTO'
            }
        else:
            return {
                'exige_impugnacao': False,
                'observacao': 'Especificação adequada. Permite competição entre fornecedores.',
                'risco': 'BAIXO'
            }

class MatchingBasico:
    """Sistema principal básico"""
    
    def __init__(self):
        print("🚀 Inicializando Sistema Básico de Matching...")
        self.processador = ProcessadorBasico()
        self.analisador = AnalisadorJuridico()
        self.produtos_df = None
        self.resultados = []
    
    def carregar_dados(self):
        """Carrega dados"""
        print("\n📂 Carregando dados...")
        
        try:
            # Verificar arquivos
            if not os.path.exists(Config.PRODUTOS_PATH):
                print("❌ Arquivo não encontrado: " + Config.PRODUTOS_PATH)
                return False
            
            if not os.path.exists(Config.ORCAMENTOS_PATH):
                print("❌ Pasta não encontrada: " + Config.ORCAMENTOS_PATH)
                return False
            
            # Carregar produtos
            self.produtos_df = pd.read_excel(Config.PRODUTOS_PATH)
            self.produtos_df.columns = self.produtos_df.columns.str.strip()
            print("✅ " + str(len(self.produtos_df)) + " produtos carregados")
            
            # Listar orçamentos
            pasta = Path(Config.ORCAMENTOS_PATH)
            self.arquivos = list(pasta.glob("*.xlsx"))
            print("✅ " + str(len(self.arquivos)) + " arquivos encontrados")
            
            return len(self.arquivos) > 0
            
        except Exception as e:
            print("❌ Erro: " + str(e))
            return False
    
    def extrair_valor(self, valor):
        """Extrai valor numérico"""
        if pd.isna(valor):
            return 0.0
        
        valor_str = str(valor).replace('.', '').replace(',', '.')
        try:
            match = re.search(r'[\d\.]+', valor_str)
            return float(match.group()) if match else 0.0
        except:
            return 0.0
    
    def calcular_compatibilidade(self, desc_edital, produto):
        """Calcula compatibilidade entre edital e produto"""
        # Preparar textos
        texto_produto = ""
        for campo in ['MODELO', 'DESCRIÇÃO', 'DESCRICAO']:
            if campo in produto and pd.notna(produto[campo]):
                texto_produto += " " + str(produto[campo])
        
        if not texto_produto.strip():
            return 0.0, {}
        
        # 1. Similaridade básica (60%)
        score_basico = self.processador.calcular_similaridade(desc_edital, texto_produto)
        
        # 2. Match exato de modelo (40%)
        modelo = str(produto.get('MODELO', ''))
        score_modelo = 0.0
        if modelo and len(modelo) > 2:
            if modelo.upper() in desc_edital.upper():
                score_modelo = 100.0
            elif any(palavra in desc_edital.upper() for palavra in modelo.upper().split() if len(palavra) > 2):
                score_modelo = 70.0
        
        # 3. Bônus especificações (até 20%)
        specs_edital = self.processador.extrair_especificacoes(desc_edital)
        specs_produto = self.processador.extrair_especificacoes(texto_produto)
        
        bonus_specs = 0.0
        if specs_edital and specs_produto:
            specs_comuns = set(specs_edital) & set(specs_produto)
            bonus_specs = (len(specs_comuns) / len(specs_edital)) * 20
        
        # Score final
        if score_modelo > 0:
            score_final = max(score_modelo, score_basico) + bonus_specs
        else:
            score_final = score_basico + bonus_specs
        
        detalhes = {
            'basico': round(score_basico, 2),
            'modelo': round(score_modelo, 2),
            'bonus': round(bonus_specs, 2),
            'specs_edital': specs_edital,
            'specs_produto': specs_produto
        }
        
        return min(score_final, 100.0), detalhes
    
    def processar_tudo(self):
        """Processa todos os arquivos"""
        if not self.carregar_dados():
            return False
        
        print("\n🔍 Processando matching...")
        
        total_items = 0
        total_matches = 0
        
        for arquivo in self.arquivos:
            print("\n📄 Processando: " + arquivo.name)
            
            try:
                df_edital = pd.read_excel(arquivo)
                matches_arquivo = 0
                
                for _, item in df_edital.iterrows():
                    total_items += 1
                    matches = self.processar_item(item, arquivo.name)
                    matches_arquivo += matches
                    total_matches += matches
                
                print("   ✅ " + str(matches_arquivo) + " matches encontrados")
                
            except Exception as e:
                print("   ❌ Erro: " + str(e))
                continue
        
        print("\n✅ Concluído! " + str(total_items) + " itens, " + str(total_matches) + " matches")
        return True
    
    def processar_item(self, item, arquivo):
        """Processa um item do edital"""
        # Extrair dados
        num_item = item.get('Número do Item', 'N/A')
        desc_edital = str(item.get('Item', ''))
        unidade = item.get('Unidade de Fornecimento', 'UN')
        qtd = float(item.get('Quantidade Total', 0))
        valor_ref = self.extrair_valor(item.get('Valor Unitário (R$)', 0))
        
        if not desc_edital or valor_ref <= 0:
            return 0
        
        # Análise jurídica
        analise = self.analisador.analisar(desc_edital)
        
        # Buscar matches
        matches_encontrados = []
        
        for _, produto in self.produtos_df.iterrows():
            score, detalhes = self.calcular_compatibilidade(desc_edital, produto)
            
            if score >= Config.MIN_COMPATIBILIDADE:
                valor_produto = self.extrair_valor(produto.get('VALOR', produto.get('Valor', 0)))
                
                if valor_produto > 0:
                    valor_disputa = valor_produto * (1 + Config.MARGEM_DISPUTA)
                    
                    if valor_disputa <= valor_ref:
                        matches_encontrados.append({
                            'produto': produto,
                            'score': score,
                            'detalhes': detalhes,
                            'valor_produto': valor_produto,
                            'valor_disputa': valor_disputa
                        })
        
        # Ordenar e selecionar
        matches_encontrados.sort(key=lambda x: (-x['score'], x['valor_disputa']))
        
        for match in matches_encontrados[:Config.MAX_SUGESTOES]:
            self.adicionar_resultado(num_item, desc_edital, unidade, qtd, valor_ref, match, analise, arquivo)
        
        return len(matches_encontrados[:Config.MAX_SUGESTOES])
    
    def adicionar_resultado(self, num_item, desc_edital, unidade, qtd, valor_ref, match, analise, arquivo):
        """Adiciona resultado à lista"""
        produto = match['produto']
        score = match['score']
        detalhes = match['detalhes']
        valor_produto = match['valor_produto']
        valor_disputa = match['valor_disputa']
        
        # Comparação técnica
        comparacao = "Score: " + str(round(score, 1)) + "%"
        if detalhes['modelo'] > 0:
            comparacao += " | Modelo: " + str(round(detalhes['modelo'], 1)) + "%"
        if detalhes['specs_edital']:
            comparacao += " | Specs: " + ', '.join(detalhes['specs_edital'][:2])
        
        # Capacidade de substituição
        if score >= 90:
            pode_substituir = "Sim"
        elif score >= 80:
            pode_substituir = "Parcialmente"
        else:
            pode_substituir = "Limitado"
        
        resultado = {
            'Arquivo': arquivo,
            'Item': num_item,
            'Descrição Edital': desc_edital,
            'Unidade': unidade,
            'Quantidade': qtd,
            'Valor Ref. Unitário': valor_ref,
            'Valor Ref. Total': valor_ref * qtd,
            'Marca sugerida': produto.get('MARCA', 'N/A'),
            'Produto Sugerido': produto.get('MODELO', 'N/A'),
            'Link/Código': str(produto.get('MARCA', 'N/A')) + "_" + str(produto.get('MODELO', 'N/A')),
            'Preço Fornecedor': valor_produto,
            'Preço com Margem 53%': valor_disputa,
            'Comparação Técnica': comparacao,
            '% Compatibilidade': round(score, 2),
            'Pode Substituir?': pode_substituir,
            'Exige Impugnação?': 'Sim' if analise['exige_impugnacao'] else 'Não',
            'Observação Jurídica': analise['observacao'],
            'Fornecedor': produto.get('FORNECEDOR', 'N/A')
        }
        
        self.resultados.append(resultado)
    
    def gerar_relatorios(self):
        """Gera relatórios"""
        if not self.resultados:
            print("❌ Nenhum resultado para relatórios")
            return False
        
        print("\n📊 Gerando relatórios...")
        
        df_final = pd.DataFrame(self.resultados)
        
        # Estatísticas
        total_items = df_final['Item'].nunique()
        matches_bons = len(df_final[df_final['% Compatibilidade'] >= 85])
        economia_total = (df_final['Valor Ref. Unitário'] - df_final['Preço com Margem 53%']) * df_final['Quantidade']
        economia_total = economia_total[economia_total > 0].sum()
        
        # Pasta de saída
        pasta_saida = Path(Config.ORCAMENTOS_PATH)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Arquivos principais (sobrescrever conforme solicitado)
        arquivo_csv = pasta_saida / "RESULTADO_MATCHING_INTELIGENTE.csv"
        arquivo_excel = pasta_saida / "RELATORIO_MATCHING_COMPLETO.xlsx"
        
        df_final.to_csv(arquivo_csv, index=False, encoding='utf-8-sig')
        df_final.to_excel(arquivo_excel, index=False)
        
        # Arquivo com timestamp
        arquivo_basico = pasta_saida / ("MATCHING_BASICO_" + timestamp + ".csv")
        df_final.to_csv(arquivo_basico, index=False, encoding='utf-8-sig')
        
        print("✅ Relatórios gerados!")
        print("   📁 Pasta: " + str(pasta_saida))
        print("   📄 CSV Principal: RESULTADO_MATCHING_INTELIGENTE.csv")
        print("   📊 Excel Principal: RELATORIO_MATCHING_COMPLETO.xlsx")
        print("   📄 Básico CSV: " + arquivo_basico.name)
        print("   💰 Economia: R$ " + "{:,.2f}".format(economia_total))
        print("   🎯 Matches Bons (≥85%): " + str(matches_bons))
        
        return True

def main():
    """Função principal"""
    print("🎯 SISTEMA BÁSICO DE MATCHING PARA LICITAÇÕES")
    print("=" * 60)
    print("Versão: Básica e Funcional | Data: " + datetime.now().strftime('%d/%m/%Y'))
    print("=" * 60)
    
    # Executar
    matcher = MatchingBasico()
    
    try:
        if matcher.processar_tudo():
            if matcher.gerar_relatorios():
                print("\n🎉 SUCESSO! Processo concluído.")
                print("📁 Verifique os arquivos na pasta de orçamentos")
                print("✅ Sistema básico funcionando perfeitamente!")
            else:
                print("\n❌ Erro na geração de relatórios")
        else:
            print("\n❌ Erro no processamento")
    
    except Exception as e:
        print("\n💥 Erro: " + str(e))
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()