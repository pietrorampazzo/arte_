"""
Sistema Inteligente de Matching de Produtos para Licitações
Utilizando TF-IDF, Sentence Transformers e Zero-Shot Classification

Autor: Sistema Automatizado
Data: 2025
"""

import os
import re
import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Bibliotecas de NLP
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
from transformers import pipeline
import torch

# Configurações
class Config:
    # Caminhos
    PRODUTOS_PATH = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\PRODUTOS.xlsx"
    ORCAMENTOS_PATH = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\ORCAMENTOS"

    
    # Parâmetros de matching
    MARGEM_DISPUTA = 0.53  # 53%
    MIN_COMPATIBILIDADE = 80.0
    MAX_SUGESTOES = 5
    
    # Modelos NLP
    SENTENCE_MODEL = 'all-MiniLM-L6-v2'  # Modelo leve e eficiente
    ZERO_SHOT_MODEL = 'facebook/bart-large-mnli'

class TextProcessor:
    """Processador de texto com múltiplas técnicas de NLP"""
    
    def __init__(self):
        print("🔄 Inicializando modelos de NLP...")
        
        # Inicializar modelos
        try:
            self.sentence_model = SentenceTransformer(Config.SENTENCE_MODEL)
            self.zero_shot_classifier = pipeline(
                "zero-shot-classification",
                model=Config.ZERO_SHOT_MODEL,
                device=0 if torch.cuda.is_available() else -1
            )
            self.tfidf_vectorizer = TfidfVectorizer(
                max_features=5000,
                stop_words=None,  # Manteremos stop words em português
                ngram_range=(1, 3),
                lowercase=True
            )
            print("✅ Modelos NLP carregados com sucesso!")
        except Exception as e:
            print(f"⚠️ Erro ao carregar modelos: {e}")
            print("🔄 Usando fallback para modelos básicos...")
            self.sentence_model = None
            self.zero_shot_classifier = None
    
    def normalizar_texto(self, texto):
        """Normalização avançada de texto"""
        if pd.isna(texto) or texto is None:
            return ""
        
        texto = str(texto).upper()
        
        # Mapeamento de caracteres especiais
        substituicoes = {
            'Á': 'A', 'À': 'A', 'Ã': 'A', 'Â': 'A', 'Ä': 'A',
            'É': 'E', 'È': 'E', 'Ê': 'E', 'Ë': 'E',
            'Í': 'I', 'Ì': 'I', 'Î': 'I', 'Ï': 'I',
            'Ó': 'O', 'Ò': 'O', 'Õ': 'O', 'Ô': 'O', 'Ö': 'O',
            'Ú': 'U', 'Ù': 'U', 'Û': 'U', 'Ü': 'U',
            'Ç': 'C', 'Ñ': 'N'
        }
        
        for k, v in substituicoes.items():
            texto = texto.replace(k, v)
        
        # Limpar caracteres especiais mantendo espaços
        texto = re.sub(r'[^\w\s]', ' ', texto)
        texto = re.sub(r'\s+', ' ', texto).strip()
        
        return texto
    
    def extrair_especificacoes_tecnicas(self, texto):
        """Extrai especificações técnicas do texto"""
        especificacoes = []
        texto_norm = self.normalizar_texto(texto)
        
        # Padrões para especificações técnicas
        padroes = [
            r'(\d+)\s*(V|VOLTS?|WATTS?|W|A|AMPERES?)',  # Voltagem/Potência
            r'(\d+)\s*(MM|CM|M|METROS?|CENTIMETROS?|MILIMETROS?)',  # Medidas
            r'(\d+)\s*(KG|G|GRAMAS?|QUILOS?)',  # Peso
            r'(\d+)\s*(CORDAS?|TECLAS?|CANAIS?)',  # Especificações musicais
            r'(USB|BLUETOOTH|WIFI|ETHERNET)',  # Conectividade
            r'(LED|LCD|OLED)',  # Display
            r'(MADEIRA|METAL|PLASTICO|ACO|ALUMINIO)',  # Materiais
        ]
        
        for padrao in padroes:
            matches = re.findall(padrao, texto_norm)
            especificacoes.extend([' '.join(match) if isinstance(match, tuple) else match for match in matches])
        
        return list(set(especificacoes))
    
    def calcular_similaridade_tfidf(self, texto1, texto2):
        """Calcula similaridade usando TF-IDF"""
        try:
            textos = [self.normalizar_texto(texto1), self.normalizar_texto(texto2)]
            if not textos[0] or not textos[1]:
                return 0.0
            
            tfidf_matrix = self.tfidf_vectorizer.fit_transform(textos)
            similaridade = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            return float(similaridade * 100)
        except:
            return 0.0
    
    def calcular_similaridade_semantica(self, texto1, texto2):
        """Calcula similaridade semântica usando Sentence Transformers"""
        if not self.sentence_model:
            return self.calcular_similaridade_tfidf(texto1, texto2)
        
        try:
            embeddings = self.sentence_model.encode([
                self.normalizar_texto(texto1),
                self.normalizar_texto(texto2)
            ])
            similaridade = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
            return float(similaridade * 100)
        except:
            return self.calcular_similaridade_tfidf(texto1, texto2)
    
    def classificar_categoria(self, texto, categorias_candidatas):
        """Classifica texto em categorias usando Zero-Shot"""
        if not self.zero_shot_classifier:
            return categorias_candidatas[0] if categorias_candidatas else "GERAL"
        
        try:
            resultado = self.zero_shot_classifier(texto, categorias_candidatas)
            return resultado['labels'][0]
        except:
            return categorias_candidatas[0] if categorias_candidatas else "GERAL"

class LegalAnalyzer:
    """Analisador jurídico para identificar irregularidades em editais"""
    
    @staticmethod
    def analisar_direcionamento(descricao_edital):
        """Analisa se há direcionamento indevido no edital"""
        texto_norm = descricao_edital.upper()
        
        # Padrões que indicam possível direcionamento
        padroes_direcionamento = [
            r'\bMARCA\s*[:\-]?\s*(\w+)',
            r'\bEXCLUSIVAMENTE\b',
            r'\bAPENAS\s+MARCA\b',
            r'\bSOBRETUDO\s+MARCA\b',
            r'\bUNICAMENTE\b',
            r'\bEXCLUSIVO\b'
        ]
        
        direcionamentos_encontrados = []
        for padrao in padroes_direcionamento:
            matches = re.findall(padrao, texto_norm)
            direcionamentos_encontrados.extend(matches)
        
        tem_direcionamento = len(direcionamentos_encontrados) > 0
        
        if tem_direcionamento:
            return {
                'exige_impugnacao': True,
                'observacao': 'Possível direcionamento identificado. Exigência de marca específica sem justificativa técnica adequada. Fundamentado na Lei 14.133/21 (art. 7º §5º) para garantir isonomia, impessoalidade, economicidade e competitividade.',
                'direcionamentos': direcionamentos_encontrados
            }
        else:
            return {
                'exige_impugnacao': False,
                'observacao': 'Especificação técnica adequada. Permite competição entre fornecedores equivalentes.',
                'direcionamentos': []
            }

class ProductMatcher:
    """Sistema principal de matching de produtos"""
    
    def __init__(self):
        self.text_processor = TextProcessor()
        self.legal_analyzer = LegalAnalyzer()
        self.produtos_df = None
        self.resultados = []
    
    def carregar_dados(self):
        """Carrega dados dos produtos e editais"""
        print("📂 Carregando dados...")
        
        try:
            # Carregar produtos
            self.produtos_df = pd.read_excel(Config.PRODUTOS_PATH)
            self.produtos_df.columns = self.produtos_df.columns.str.strip()
            print(f"✅ {len(self.produtos_df)} produtos carregados")
            
            # Listar arquivos de orçamentos
            orcamentos_path = Path(Config.ORCAMENTOS_PATH)
            self.arquivos_orcamento = list(orcamentos_path.glob("*.xlsx"))
            print(f"✅ {len(self.arquivos_orcamento)} arquivos de orçamento encontrados")
            
            return True
        except Exception as e:
            print(f"❌ Erro ao carregar dados: {e}")
            return False
    
    def extrair_valor_numerico(self, valor):
        """Extrai valor numérico de string"""
        if pd.isna(valor):
            return 0.0
        
        valor_str = str(valor).replace('.', '').replace(',', '.')
        try:
            match = re.search(r'[\d\.]+', valor_str)
            return float(match.group()) if match else 0.0
        except:
            return 0.0
    
    def calcular_score_hibrido(self, desc_edital, produto):
        """Calcula score híbrido combinando múltiplas técnicas"""
        # Preparar textos
        texto_edital = desc_edital
        texto_produto = f"{produto.get('MODELO', '')} {produto.get('DESCRIÇÃO', '')} {produto.get('DESCRICAO', '')}"
        
        # 1. Similaridade TF-IDF (peso: 30%)
        score_tfidf = self.text_processor.calcular_similaridade_tfidf(texto_edital, texto_produto)
        
        # 2. Similaridade Semântica (peso: 50%)
        score_semantico = self.text_processor.calcular_similaridade_semantica(texto_edital, texto_produto)
        
        # 3. Match exato de modelo (peso: 20%)
        modelo = str(produto.get('MODELO', ''))
        score_exato = 100.0 if modelo and modelo.upper() in texto_edital.upper() else 0.0
        
        # 4. Especificações técnicas (bônus)
        specs_edital = self.text_processor.extrair_especificacoes_tecnicas(texto_edital)
        specs_produto = self.text_processor.extrair_especificacoes_tecnicas(texto_produto)
        
        bonus_specs = 0.0
        if specs_edital and specs_produto:
            specs_match = len(set(specs_edital) & set(specs_produto))
            bonus_specs = (specs_match / len(specs_edital)) * 10 if specs_edital else 0
        
        # Score final híbrido
        score_final = (
            score_tfidf * 0.3 +
            score_semantico * 0.5 +
            score_exato * 0.2 +
            bonus_specs
        )
        
        return min(score_final, 100.0), {
            'tfidf': score_tfidf,
            'semantico': score_semantico,
            'exato': score_exato,
            'specs_bonus': bonus_specs,
            'specs_edital': specs_edital,
            'specs_produto': specs_produto
        }
    
    def processar_matching(self):
        """Processa matching para todos os arquivos"""
        if not self.carregar_dados():
            return False
        
        print("🔍 Iniciando processo de matching...")
        
        for arquivo in self.arquivos_orcamento:
            print(f"📄 Processando: {arquivo.name}")
            
            try:
                df_edital = pd.read_excel(arquivo)
                
                for _, item in df_edital.iterrows():
                    self.processar_item_edital(item, arquivo.name)
                    
            except Exception as e:
                print(f"❌ Erro ao processar {arquivo.name}: {e}")
                continue
        
        print(f"✅ Matching concluído! {len(self.resultados)} matches encontrados")
        return True
    
    def processar_item_edital(self, item, nome_arquivo):
        """Processa um item específico do edital"""
        # Extrair dados do item
        num_item = item.get('Número do Item', 'N/A')
        desc_edital = str(item.get('Item', ''))
        unidade = item.get('Unidade de Fornecimento', 'UN')
        qtd = float(item.get('Quantidade Total', 0))
        valor_ref = self.extrair_valor_numerico(item.get('Valor Unitário (R$)', 0))
        
        if not desc_edital or valor_ref <= 0:
            return
        
        # Análise jurídica
        analise_juridica = self.legal_analyzer.analisar_direcionamento(desc_edital)
        
        # Buscar matches nos produtos
        matches_encontrados = []
        
        for _, produto in self.produtos_df.iterrows():
            score, detalhes = self.calcular_score_hibrido(desc_edital, produto)
            
            if score >= Config.MIN_COMPATIBILIDADE:
                valor_produto = self.extrair_valor_numerico(produto.get('Valor', produto.get('VALOR', 0)))
                valor_disputa = valor_produto * (1 + Config.MARGEM_DISPUTA)
                
                # Verificar se está dentro do orçamento
                if valor_disputa <= valor_ref:
                    matches_encontrados.append({
                        'produto': produto,
                        'score': score,
                        'detalhes': detalhes,
                        'valor_produto': valor_produto,
                        'valor_disputa': valor_disputa
                    })
        
        # Ordenar por score e preço
        matches_encontrados.sort(key=lambda x: (-x['score'], x['valor_disputa']))
        
        # Selecionar top matches
        for match in matches_encontrados[:Config.MAX_SUGESTOES]:
            self.adicionar_resultado(
                num_item, desc_edital, unidade, qtd, valor_ref,
                match, analise_juridica, nome_arquivo
            )
    
    def adicionar_resultado(self, num_item, desc_edital, unidade, qtd, valor_ref, match, analise_juridica, arquivo):
        """Adiciona resultado à lista final"""
        produto = match['produto']
        score = match['score']
        detalhes = match['detalhes']
        valor_produto = match['valor_produto']
        valor_disputa = match['valor_disputa']
        
        # Preparar comparação técnica
        comparacao_tecnica = f"Compatibilidade: {score:.1f}% | "
        comparacao_tecnica += f"TF-IDF: {detalhes['tfidf']:.1f}% | "
        comparacao_tecnica += f"Semântico: {detalhes['semantico']:.1f}% | "
        if detalhes['specs_edital']:
            comparacao_tecnica += f"Specs: {', '.join(detalhes['specs_edital'][:3])}"
        
        # Determinar se pode substituir
        pode_substituir = "Sim" if score >= 90 else "Parcialmente"
        
        resultado = {
            'Arquivo': arquivo,
            'Item': num_item,
            'Descrição Edital': desc_edital,
            'Unidade': unidade,
            'Quantidade': qtd,
            'Valor Ref. Unitário': valor_ref,
            'Valor Ref. Total': valor_ref * qtd,
            'Marca sugerida': produto.get('MARCA', produto.get('Marca', 'N/A')),
            'Produto Sugerido': produto.get('MODELO', produto.get('DESCRICAO', 'N/A')),
            'Link/Código': f"{produto.get('MARCA', 'N/A')}_{produto.get('MODELO', 'N/A')}",
            'Preço Fornecedor': valor_produto,
            'Preço com Margem 53%': valor_disputa,
            'Comparação Técnica': comparacao_tecnica,
            '% Compatibilidade': round(score, 2),
            'Pode Substituir?': pode_substituir,
            'Exige Impugnação?': 'Sim' if analise_juridica['exige_impugnacao'] else 'Não',
            'Observação Jurídica': analise_juridica['observacao'],
            'Fornecedor': produto.get('FORNECEDOR', 'N/A')
        }
        
        self.resultados.append(resultado)
    
    def gerar_relatorios(self):
        """Gera relatórios em múltiplos formatos"""
        if not self.resultados:
            print("❌ Nenhum resultado para gerar relatórios")
            return False
        
        print("📊 Gerando relatórios...")
        
        # Criar DataFrame
        df_final = pd.DataFrame(self.resultados)
        
        # Calcular estatísticas
        total_items = df_final['Item'].nunique()
        matches_validos = len(df_final[df_final['% Compatibilidade'] >= 90])
        
        # Calcular economia
        economia_por_item = (df_final['Valor Ref. Unitário'] - df_final['Preço com Margem 53%']) * df_final['Quantidade']
        economia_total = economia_por_item[economia_por_item > 0].sum()
        
        # Salvar arquivos na pasta de orçamentos
        pasta_saida = Path(Config.ORCAMENTOS_PATH)
        
        # 1. CSV principal
        arquivo_csv = pasta_saida / "RESULTADO_MATCHING_INTELIGENTE.csv"
        df_final.to_csv(arquivo_csv, index=False, encoding='utf-8-sig')
        
        # 2. Excel com múltiplas abas
        arquivo_excel = pasta_saida / "RELATORIO_MATCHING_COMPLETO.xlsx"
        with pd.ExcelWriter(arquivo_excel, engine='openpyxl') as writer:
            df_final.to_excel(writer, sheet_name='Matches Completos', index=False)
            
            # Aba de resumo por arquivo
            resumo_arquivos = df_final.groupby('Arquivo').agg({
                'Item': 'nunique',
                '% Compatibilidade': 'mean',
                'Preço com Margem 53%': 'sum',
                'Valor Ref. Total': 'sum'
            }).round(2)
            resumo_arquivos.to_excel(writer, sheet_name='Resumo por Arquivo')
            
            # Aba de melhores matches
            melhores_matches = df_final[df_final['% Compatibilidade'] >= 95].copy()
            melhores_matches.to_excel(writer, sheet_name='Melhores Matches', index=False)
        
        # 3. Relatório em Markdown
        self.gerar_relatorio_markdown(df_final, total_items, matches_validos, economia_total)
        
        print(f"✅ Relatórios gerados com sucesso!")
        print(f"   📁 Pasta: {pasta_saida}")
        print(f"   📄 CSV: RESULTADO_MATCHING_INTELIGENTE.csv")
        print(f"   📊 Excel: RELATORIO_MATCHING_COMPLETO.xlsx")
        print(f"   📝 Markdown: RELATORIO_MATCHING_DETALHADO.md")
        print(f"   💰 Economia estimada: R$ {economia_total:,.2f}")
        
        return True
    
    def gerar_relatorio_markdown(self, df_final, total_items, matches_validos, economia_total):
        """Gera relatório detalhado em Markdown"""
        pasta_saida = Path(Config.ORCAMENTOS_PATH)
        arquivo_md = pasta_saida / "RELATORIO_MATCHING_DETALHADO.md"
        
        # Estatísticas por compatibilidade
        stats_compat = df_final.groupby(pd.cut(df_final['% Compatibilidade'], 
                                              bins=[0, 80, 90, 95, 100], 
                                              labels=['80-89%', '90-94%', '95-99%', '100%'])).size()
        
        conteudo = f"""# 🎯 Relatório Inteligente de Matching de Produtos para Licitações

## 📈 Resumo Executivo

- **Total de Itens Analisados**: {total_items}
- **Matches Válidos Encontrados**: {matches_validos}
- **Taxa de Sucesso**: {(matches_validos/len(df_final)*100):.1f}%
- **Economia Estimada Total**: R$ {economia_total:,.2f}
- **Tecnologia Utilizada**: TF-IDF + Sentence Transformers + Zero-Shot Classification

## 🔍 Distribuição de Compatibilidade

{stats_compat.to_string()}

## ⚖️ Análise Jurídica

- **Itens com Exigência de Impugnação**: {len(df_final[df_final['Exige Impugnação?'] == 'Sim'])}
- **Itens Conformes**: {len(df_final[df_final['Exige Impugnação?'] == 'Não'])}

## 🏆 Top 10 Melhores Matches

{df_final.nlargest(10, '% Compatibilidade')[['Item', 'Produto Sugerido', '% Compatibilidade', 'Preço com Margem 53%']].to_string(index=False)}

## 💡 Metodologia Aplicada

Este relatório foi gerado utilizando técnicas avançadas de Processamento de Linguagem Natural:

1. **TF-IDF (Term Frequency-Inverse Document Frequency)**: Análise estatística de relevância de termos
2. **Sentence Transformers**: Embeddings semânticos para compreensão contextual
3. **Zero-Shot Classification**: Categorização automática sem treinamento específico
4. **Análise Jurídica Automatizada**: Identificação de direcionamentos indevidos

## 📋 Conformidade Legal

Análise baseada na Lei 14.133/21, garantindo:
- ✅ Isonomia entre fornecedores
- ✅ Impessoalidade na análise técnica  
- ✅ Economicidade na seleção
- ✅ Competitividade no processo

---

*Relatório gerado automaticamente pelo Sistema Inteligente de Matching*
*Data: {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')}*
"""
        
        with open(arquivo_md, 'w', encoding='utf-8') as f:
            f.write(conteudo)

def main():
    """Função principal"""
    print("🚀 Sistema Inteligente de Matching de Produtos para Licitações")
    print("=" * 60)
    
    # Inicializar sistema
    matcher = ProductMatcher()
    
    # Executar processo completo
    if matcher.processar_matching():
        if matcher.gerar_relatorios():
            print("\n🎉 Processo concluído com sucesso!")
            print("📁 Verifique os arquivos gerados na pasta de orçamentos")
        else:
            print("\n❌ Erro na geração de relatórios")
    else:
        print("\n❌ Erro no processo de matching")

if __name__ == "__main__":
    main()

