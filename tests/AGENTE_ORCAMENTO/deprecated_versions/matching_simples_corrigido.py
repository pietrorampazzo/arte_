"""
🎯 SISTEMA SIMPLES E EFICIENTE DE MATCHING PARA LICITAÇÕES
Versão Corrigida - Sem Erros de Sintaxe

Funcionalidades:
- Matching inteligente com TF-IDF básico
- Pipeline Transformers para análise semântica
- Análise jurídica automatizada
- Relatórios em Excel e CSV
- Configuração simples e rápida

Autor: Sistema Otimizado
Data: Janeiro 2025
"""

import os
import re
import pandas as pd
import numpy as np
from pathlib import Path
import warnings
from datetime import datetime
warnings.filterwarnings('ignore')

# Importações com fallback
try:
    from transformers import pipeline
    TRANSFORMERS_AVAILABLE = True
    print("✅ Transformers disponível")
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    print("⚠️ Transformers não disponível - usando matching básico")

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
    print("✅ Scikit-learn disponível")
except ImportError:
    SKLEARN_AVAILABLE = False
    print("⚠️ Scikit-learn não disponível")

class ConfigSimples:
    """Configurações simplificadas"""
    
    # 🔧 AJUSTE AQUI OS CAMINHOS
    PRODUTOS_PATH = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\PRODUTOS.xlsx"
    ORCAMENTOS_PATH = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\ORCAMENTOS"

    
    # Parâmetros
    MARGEM_DISPUTA = 0.53  # 53%
    MIN_COMPATIBILIDADE = 75.0  # Mínimo para considerar
    MAX_SUGESTOES = 5

class ProcessadorTextoSimples:
    """Processador de texto simplificado mas eficiente"""
    
    def __init__(self):
        print("🔄 Inicializando processador...")
        
        # Inicializar pipeline de texto (se disponível)
        self.text_pipeline = None
        if TRANSFORMERS_AVAILABLE:
            try:
                # Usar pipeline para análise de texto
                self.text_pipeline = pipeline(
                    "feature-extraction",
                    model="distilbert-base-uncased",
                    return_tensors="np"
                )
                print("✅ Pipeline Transformers inicializado")
            except Exception as e:
                print("⚠️ Erro no pipeline: " + str(e))
                self.text_pipeline = None
        
        # TF-IDF como backup
        self.tfidf = None
        if SKLEARN_AVAILABLE:
            self.tfidf = TfidfVectorizer(
                max_features=1000,
                ngram_range=(1, 2),
                lowercase=True
            )
            print("✅ TF-IDF inicializado")
    
    def normalizar(self, texto):
        """Normalização básica mas eficiente"""
        if pd.isna(texto) or not texto:
            return ""
        
        texto = str(texto).upper()
        
        # Remover acentos
        acentos = {
            'Á': 'A', 'À': 'A', 'Ã': 'A', 'Â': 'A',
            'É': 'E', 'È': 'E', 'Ê': 'E',
            'Í': 'I', 'Ì': 'I', 'Î': 'I',
            'Ó': 'O', 'Ò': 'O', 'Õ': 'O', 'Ô': 'O',
            'Ú': 'U', 'Ù': 'U', 'Û': 'U',
            'Ç': 'C'
        }
        
        for k, v in acentos.items():
            texto = texto.replace(k, v)
        
        # Limpar caracteres especiais
        texto = re.sub(r'[^A-Z0-9\s]', ' ', texto)
        texto = re.sub(r'\s+', ' ', texto).strip()
        
        return texto
    
    def extrair_specs(self, texto):
        """Extrai especificações técnicas básicas"""
        specs = []
        texto_norm = self.normalizar(texto)
        
        # Padrões simples mas eficazes
        padroes = [
            r'(\d+)\s*(V|VOLTS?|W|WATTS?)',  # Voltagem/Potência
            r'(\d+)\s*(MM|CM|M)',            # Medidas
            r'(\d+)\s*(CORDAS?|TECLAS?)',    # Musicais
            r'(USB|BLUETOOTH|MIDI)',         # Conectividade
            r'(MADEIRA|METAL|ACO)',          # Materiais
        ]
        
        for padrao in padroes:
            matches = re.findall(padrao, texto_norm)
            for match in matches:
                if isinstance(match, tuple):
                    specs.append(' '.join(match))
                else:
                    specs.append(match)
        
        return list(set(specs))
    
    def calcular_similaridade(self, texto1, texto2):
        """Calcula similaridade usando a melhor técnica disponível"""
        
        # Método 1: Pipeline Transformers (mais preciso)
        if self.text_pipeline:
            try:
                # Usar embeddings para similaridade semântica
                emb1 = self.text_pipeline(self.normalizar(texto1))
                emb2 = self.text_pipeline(self.normalizar(texto2))
                
                # Calcular similaridade coseno
                from numpy.linalg import norm
                similarity = np.dot(emb1[0].mean(axis=0), emb2[0].mean(axis=0)) / (
                    norm(emb1[0].mean(axis=0)) * norm(emb2[0].mean(axis=0))
                )
                return float(similarity * 100)
            except:
                pass
        
        # Método 2: TF-IDF (backup confiável)
        if self.tfidf:
            try:
                textos = [self.normalizar(texto1), self.normalizar(texto2)]
                tfidf_matrix = self.tfidf.fit_transform(textos)
                similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
                return float(similarity * 100)
            except:
                pass
        
        # Método 3: Jaccard (fallback básico)
        palavras1 = set(self.normalizar(texto1).split())
        palavras2 = set(self.normalizar(texto2).split())
        
        if not palavras1 or not palavras2:
            return 0.0
        
        intersecao = palavras1.intersection(palavras2)
        uniao = palavras1.union(palavras2)
        
        return (len(intersecao) / len(uniao)) * 100 if uniao else 0.0

class AnalisadorJuridicoSimples:
    """Análise jurídica simplificada"""
    
    @staticmethod
    def analisar(descricao):
        """Analisa direcionamento de forma simples"""
        texto = descricao.upper()
        
        # Padrões de direcionamento
        direcionamentos = [
            r'\bMARCA\s+(\w+)',
            r'\bEXCLUSIVAMENTE\b',
            r'\bAPENAS\b',
            r'\bUNICAMENTE\b',
            r'\bEXCLUSIVO\b'
        ]
        
        problemas = []
        for padrao in direcionamentos:
            if re.search(padrao, texto):
                problemas.append(padrao)
        
        if problemas:
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

class MatchingSimples:
    """Sistema principal simplificado"""
    
    def __init__(self):
        print("🚀 Inicializando Sistema de Matching Simples...")
        self.processador = ProcessadorTextoSimples()
        self.analisador = AnalisadorJuridicoSimples()
        self.produtos_df = None
        self.resultados = []
    
    def carregar_dados(self):
        """Carrega dados com validação básica"""
        print("\n📂 Carregando dados...")
        
        try:
            # Verificar arquivos
            if not os.path.exists(ConfigSimples.PRODUTOS_PATH):
                print("❌ Arquivo não encontrado: " + ConfigSimples.PRODUTOS_PATH)
                return False
            
            if not os.path.exists(ConfigSimples.ORCAMENTOS_PATH):
                print("❌ Pasta não encontrada: " + ConfigSimples.ORCAMENTOS_PATH)
                return False
            
            # Carregar produtos
            self.produtos_df = pd.read_excel(ConfigSimples.PRODUTOS_PATH)
            self.produtos_df.columns = self.produtos_df.columns.str.strip()
            print("✅ " + str(len(self.produtos_df)) + " produtos carregados")
            
            # Listar orçamentos
            pasta = Path(ConfigSimples.ORCAMENTOS_PATH)
            self.arquivos = list(pasta.glob("*.xlsx"))
            print("✅ " + str(len(self.arquivos)) + " arquivos de orçamento encontrados")
            
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
    
    def calcular_score(self, desc_edital, produto):
        """Calcula score de compatibilidade"""
        # Preparar textos
        texto_produto = str(produto.get('MODELO', '')) + " " + str(produto.get('DESCRIÇÃO', '')) + " " + str(produto.get('DESCRICAO', ''))
        
        if not texto_produto.strip():
            return 0.0, {}
        
        # 1. Similaridade principal (70%)
        score_principal = self.processador.calcular_similaridade(desc_edital, texto_produto)
        
        # 2. Match exato de modelo (30%)
        modelo = str(produto.get('MODELO', ''))
        score_exato = 0.0
        if modelo and len(modelo) > 2:
            if modelo.upper() in desc_edital.upper():
                score_exato = 100.0
            elif any(palavra in desc_edital.upper() for palavra in modelo.upper().split() if len(palavra) > 2):
                score_exato = 80.0
        
        # 3. Bônus por especificações (até 15%)
        specs_edital = self.processador.extrair_specs(desc_edital)
        specs_produto = self.processador.extrair_specs(texto_produto)
        
        bonus_specs = 0.0
        if specs_edital and specs_produto:
            specs_comuns = set(specs_edital) & set(specs_produto)
            bonus_specs = (len(specs_comuns) / len(specs_edital)) * 15
        
        # Score final
        if score_exato > 0:
            score_final = score_exato + bonus_specs
        else:
            score_final = score_principal * 0.7 + bonus_specs
        
        detalhes = {
            'principal': round(score_principal, 2),
            'exato': round(score_exato, 2),
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
                
                for _, item in df_edital.iterrows():
                    total_items += 1
                    matches = self.processar_item(item, arquivo.name)
                    total_matches += matches
                
                print("   ✅ Processado com " + str(matches) + " matches")
                
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
            score, detalhes = self.calcular_score(desc_edital, produto)
            
            if score >= ConfigSimples.MIN_COMPATIBILIDADE:
                valor_produto = self.extrair_valor(produto.get('VALOR', produto.get('Valor', 0)))
                
                if valor_produto > 0:
                    valor_disputa = valor_produto * (1 + ConfigSimples.MARGEM_DISPUTA)
                    
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
        
        for match in matches_encontrados[:ConfigSimples.MAX_SUGESTOES]:
            self.adicionar_resultado(num_item, desc_edital, unidade, qtd, valor_ref, match, analise, arquivo)
        
        return len(matches_encontrados[:ConfigSimples.MAX_SUGESTOES])
    
    def adicionar_resultado(self, num_item, desc_edital, unidade, qtd, valor_ref, match, analise, arquivo):
        """Adiciona resultado à lista"""
        produto = match['produto']
        score = match['score']
        detalhes = match['detalhes']
        valor_produto = match['valor_produto']
        valor_disputa = match['valor_disputa']
        
        # Comparação técnica
        comparacao = "Score: " + str(round(score, 1)) + "%"
        if detalhes['specs_edital']:
            comparacao += " | Specs: " + ', '.join(detalhes['specs_edital'][:2])
        
        # Capacidade de substituição
        if score >= 95:
            pode_substituir = "Excelente"
        elif score >= 85:
            pode_substituir = "Sim"
        else:
            pode_substituir = "Parcialmente"
        
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
        """Gera relatórios simples mas completos"""
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
        pasta_saida = Path(ConfigSimples.ORCAMENTOS_PATH)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 1. CSV Principal (sobrescrever conforme solicitado)
        arquivo_csv = pasta_saida / "RESULTADO_MATCHING_INTELIGENTE.csv"
        df_final.to_csv(arquivo_csv, index=False, encoding='utf-8-sig')
        
        # 2. Excel Principal (sobrescrever conforme solicitado)
        arquivo_excel = pasta_saida / "RELATORIO_MATCHING_COMPLETO.xlsx"
        df_final.to_excel(arquivo_excel, index=False)
        
        # 3. Relatório com timestamp
        arquivo_csv_ts = pasta_saida / ("MATCHING_SIMPLES_" + timestamp + ".csv")
        df_final.to_csv(arquivo_csv_ts, index=False, encoding='utf-8-sig')
        
        # 4. Resumo em texto
        resumo = """
# 📊 Relatório de Matching - """ + datetime.now().strftime('%d/%m/%Y %H:%M') + """

## Resumo Executivo
- **Itens Analisados**: """ + str(total_items) + """
- **Matches Encontrados**: """ + str(len(df_final)) + """
- **Matches de Qualidade (≥85%)**: """ + str(matches_bons) + """
- **Economia Estimada**: R$ """ + "{:,.2f}".format(economia_total) + """

## Top 10 Melhores Matches
""" + df_final.nlargest(10, '% Compatibilidade')[['Item', 'Produto Sugerido', '% Compatibilidade', 'Preço com Margem 53%']].to_string(index=False) + """

## Análise Jurídica
- **Itens com Risco**: """ + str(len(df_final[df_final['Exige Impugnação?'] == 'Sim'])) + """
- **Itens Seguros**: """ + str(len(df_final[df_final['Exige Impugnação?'] == 'Não'])) + """

---
*Relatório gerado pelo Sistema Simples de Matching*
"""
        
        arquivo_resumo = pasta_saida / ("RESUMO_MATCHING_" + timestamp + ".md")
        with open(arquivo_resumo, 'w', encoding='utf-8') as f:
            f.write(resumo)
        
        print("✅ Relatórios gerados!")
        print("   📁 Pasta: " + str(pasta_saida))
        print("   📄 CSV Principal: RESULTADO_MATCHING_INTELIGENTE.csv")
        print("   📊 Excel Principal: RELATORIO_MATCHING_COMPLETO.xlsx")
        print("   📄 CSV Timestamped: " + arquivo_csv_ts.name)
        print("   📝 Resumo: " + arquivo_resumo.name)
        print("   💰 Economia: R$ " + "{:,.2f}".format(economia_total))
        
        return True

def main():
    """Função principal"""
    print("🎯 SISTEMA SIMPLES DE MATCHING PARA LICITAÇÕES")
    print("=" * 60)
    print("Versão: Simples e Eficiente | Data: " + datetime.now().strftime('%d/%m/%Y'))
    print("=" * 60)
    
    # Executar
    matcher = MatchingSimples()
    
    try:
        if matcher.processar_tudo():
            if matcher.gerar_relatorios():
                print("\n🎉 SUCESSO! Processo concluído.")
                print("📁 Verifique os arquivos na pasta de orçamentos")
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

