"""
Sistema Inteligente de Matching de Produtos para Licitações - Versão Simplificada
Funciona sem dependências pesadas de NLP para teste inicial
"""

import os
import re
import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Tentar importar bibliotecas de NLP (fallback se não disponível)
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
    print("✅ Scikit-learn disponível - usando TF-IDF avançado")
except ImportError:
    SKLEARN_AVAILABLE = False
    print("⚠️ Scikit-learn não disponível - usando matching básico")

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
    print("✅ Sentence Transformers disponível")
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    print("⚠️ Sentence Transformers não disponível - usando fallback")

# Configurações
class Config:
    # Caminhos (ajustáveis)
    PRODUTOS_PATH = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\PRODUTOS.xlsx"
    ORCAMENTOS_PATH = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\ORCAMENTOS"

    
    # Para teste local
    TEST_PRODUTOS_PATH = "/home/ubuntu/teste_matching/PRODUTOS.xlsx"
    TEST_ORCAMENTOS_PATH = "/home/ubuntu/teste_matching/ORCAMENTOS"
    
    # Parâmetros
    MARGEM_DISPUTA = 0.53  # 53%
    MIN_COMPATIBILIDADE = 80.0
    MAX_SUGESTOES = 5

class TextProcessor:
    """Processador de texto com fallback para ambientes sem NLP pesado"""
    
    def __init__(self):
        self.tfidf_vectorizer = None
        self.sentence_model = None
        
        if SKLEARN_AVAILABLE:
            self.tfidf_vectorizer = TfidfVectorizer(
                max_features=1000,
                ngram_range=(1, 2),
                lowercase=True
            )
        
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
            except:
                self.sentence_model = None
    
    def normalizar_texto(self, texto):
        """Normalização de texto"""
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
        
        # Limpar caracteres especiais
        texto = re.sub(r'[^\w\s]', ' ', texto)
        texto = re.sub(r'\s+', ' ', texto).strip()
        
        return texto
    
    def extrair_especificacoes(self, texto):
        """Extrai especificações técnicas"""
        specs = []
        texto_norm = self.normalizar_texto(texto)
        
        # Padrões técnicos
        padroes = [
            r'(\d+)\s*(V|VOLTS?|WATTS?|W|A|AMPERES?)',
            r'(\d+)\s*(MM|CM|M|METROS?)',
            r'(\d+)\s*(KG|G|GRAMAS?)',
            r'(\d+)\s*(CORDAS?|TECLAS?|CANAIS?)',
            r'(USB|BLUETOOTH|WIFI|ETHERNET)',
            r'(LED|LCD|OLED)',
            r'(MADEIRA|METAL|PLASTICO|ACO|ALUMINIO)',
        ]
        
        for padrao in padroes:
            matches = re.findall(padrao, texto_norm)
            specs.extend([' '.join(match) if isinstance(match, tuple) else match for match in matches])
        
        return list(set(specs))
    
    def calcular_similaridade_basica(self, texto1, texto2):
        """Similaridade básica por palavras em comum"""
        palavras1 = set(self.normalizar_texto(texto1).split())
        palavras2 = set(self.normalizar_texto(texto2).split())
        
        if not palavras1 or not palavras2:
            return 0.0
        
        intersecao = palavras1.intersection(palavras2)
        uniao = palavras1.union(palavras2)
        
        return (len(intersecao) / len(uniao)) * 100 if uniao else 0.0
    
    def calcular_similaridade_tfidf(self, texto1, texto2):
        """Similaridade usando TF-IDF (se disponível)"""
        if not self.tfidf_vectorizer:
            return self.calcular_similaridade_basica(texto1, texto2)
        
        try:
            textos = [self.normalizar_texto(texto1), self.normalizar_texto(texto2)]
            tfidf_matrix = self.tfidf_vectorizer.fit_transform(textos)
            similaridade = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            return float(similaridade * 100)
        except:
            return self.calcular_similaridade_basica(texto1, texto2)

class LegalAnalyzer:
    """Analisador jurídico"""
    
    @staticmethod
    def analisar_direcionamento(descricao):
        """Analisa direcionamento indevido"""
        texto_upper = descricao.upper()
        
        padroes_direcionamento = [
            r'\bMARCA\s*[:\-]?\s*(\w+)',
            r'\bEXCLUSIVAMENTE\b',
            r'\bAPENAS\s+MARCA\b',
            r'\bUNICAMENTE\b',
            r'\bEXCLUSIVO\b'
        ]
        
        direcionamentos = []
        for padrao in padroes_direcionamento:
            matches = re.findall(padrao, texto_upper)
            direcionamentos.extend(matches)
        
        tem_direcionamento = len(direcionamentos) > 0
        
        if tem_direcionamento:
            return {
                'exige_impugnacao': True,
                'observacao': 'Possível direcionamento identificado. Exigência de marca específica sem justificativa técnica adequada. Fundamentado na Lei 14.133/21 (art. 7º §5º) para garantir isonomia, impessoalidade, economicidade e competitividade.',
                'direcionamentos': direcionamentos
            }
        else:
            return {
                'exige_impugnacao': False,
                'observacao': 'Especificação técnica adequada. Permite competição entre fornecedores equivalentes.',
                'direcionamentos': []
            }

class ProductMatcher:
    """Sistema principal de matching"""
    
    def __init__(self, usar_dados_teste=False):
        self.text_processor = TextProcessor()
        self.legal_analyzer = LegalAnalyzer()
        self.usar_dados_teste = usar_dados_teste
        self.produtos_df = None
        self.resultados = []
    
    def carregar_dados(self):
        """Carrega dados"""
        print("📂 Carregando dados...")
        
        try:
            if self.usar_dados_teste:
                produtos_path = Config.TEST_PRODUTOS_PATH
                orcamentos_path = Config.TEST_ORCAMENTOS_PATH
            else:
                produtos_path = Config.PRODUTOS_PATH
                orcamentos_path = Config.ORCAMENTOS_PATH
            
            # Carregar produtos
            self.produtos_df = pd.read_excel(produtos_path)
            self.produtos_df.columns = self.produtos_df.columns.str.strip()
            print(f"✅ {len(self.produtos_df)} produtos carregados")
            
            # Listar arquivos de orçamentos
            orcamentos_path_obj = Path(orcamentos_path)
            self.arquivos_orcamento = list(orcamentos_path_obj.glob("*.xlsx"))
            print(f"✅ {len(self.arquivos_orcamento)} arquivos de orçamento encontrados")
            
            return True
        except Exception as e:
            print(f"❌ Erro ao carregar dados: {e}")
            return False
    
    def extrair_valor_numerico(self, valor):
        """Extrai valor numérico"""
        if pd.isna(valor):
            return 0.0
        
        valor_str = str(valor).replace('.', '').replace(',', '.')
        try:
            match = re.search(r'[\d\.]+', valor_str)
            return float(match.group()) if match else 0.0
        except:
            return 0.0
    
    def calcular_score_hibrido(self, desc_edital, produto):
        """Score híbrido simplificado"""
        # Preparar textos
        texto_edital = desc_edital
        texto_produto = f"{produto.get('MODELO', '')} {produto.get('DESCRIÇÃO', '')} {produto.get('DESCRICAO', '')}"
        
        # 1. Similaridade básica/TF-IDF
        score_principal = self.text_processor.calcular_similaridade_tfidf(texto_edital, texto_produto)
        
        # 2. Match exato de modelo
        modelo = str(produto.get('MODELO', ''))
        score_exato = 100.0 if modelo and modelo.upper() in texto_edital.upper() else 0.0
        
        # 3. Especificações técnicas
        specs_edital = self.text_processor.extrair_especificacoes(texto_edital)
        specs_produto = self.text_processor.extrair_especificacoes(texto_produto)
        
        bonus_specs = 0.0
        if specs_edital and specs_produto:
            specs_match = len(set(specs_edital) & set(specs_produto))
            bonus_specs = (specs_match / len(specs_edital)) * 10 if specs_edital else 0
        
        # Score final
        if score_exato > 0:
            score_final = score_exato
        else:
            score_final = score_principal * 0.8 + bonus_specs
        
        return min(score_final, 100.0), {
            'principal': score_principal,
            'exato': score_exato,
            'specs_bonus': bonus_specs,
            'specs_edital': specs_edital,
            'specs_produto': specs_produto
        }
    
    def processar_matching(self):
        """Processa matching"""
        if not self.carregar_dados():
            return False
        
        print("🔍 Iniciando matching...")
        
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
        """Processa item do edital"""
        # Extrair dados
        num_item = item.get('Número do Item', 'N/A')
        desc_edital = str(item.get('Item', ''))
        unidade = item.get('Unidade de Fornecimento', 'UN')
        qtd = float(item.get('Quantidade Total', 0))
        valor_ref = self.extrair_valor_numerico(item.get('Valor Unitário (R$)', 0))
        
        if not desc_edital or valor_ref <= 0:
            return
        
        # Análise jurídica
        analise_juridica = self.legal_analyzer.analisar_direcionamento(desc_edital)
        
        # Buscar matches
        matches_encontrados = []
        
        for _, produto in self.produtos_df.iterrows():
            score, detalhes = self.calcular_score_hibrido(desc_edital, produto)
            
            if score >= Config.MIN_COMPATIBILIDADE:
                valor_produto = self.extrair_valor_numerico(produto.get('VALOR', produto.get('Valor', 0)))
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
            self.adicionar_resultado(
                num_item, desc_edital, unidade, qtd, valor_ref,
                match, analise_juridica, nome_arquivo
            )
    
    def adicionar_resultado(self, num_item, desc_edital, unidade, qtd, valor_ref, match, analise_juridica, arquivo):
        """Adiciona resultado"""
        produto = match['produto']
        score = match['score']
        detalhes = match['detalhes']
        valor_produto = match['valor_produto']
        valor_disputa = match['valor_disputa']
        
        # Comparação técnica
        comparacao = f"Score: {score:.1f}% | "
        if detalhes['specs_edital']:
            comparacao += f"Specs: {', '.join(detalhes['specs_edital'][:3])}"
        
        pode_substituir = "Sim" if score >= 90 else "Parcialmente"
        
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
            'Link/Código': f"{produto.get('MARCA', 'N/A')}_{produto.get('MODELO', 'N/A')}",
            'Preço Fornecedor': valor_produto,
            'Preço com Margem 53%': valor_disputa,
            'Comparação Técnica': comparacao,
            '% Compatibilidade': round(score, 2),
            'Pode Substituir?': pode_substituir,
            'Exige Impugnação?': 'Sim' if analise_juridica['exige_impugnacao'] else 'Não',
            'Observação Jurídica': analise_juridica['observacao'],
            'Fornecedor': produto.get('FORNECEDOR', 'N/A')
        }
        
        self.resultados.append(resultado)
    
    def gerar_relatorios(self):
        """Gera relatórios"""
        if not self.resultados:
            print("❌ Nenhum resultado para relatórios")
            return False
        
        print("📊 Gerando relatórios...")
        
        df_final = pd.DataFrame(self.resultados)
        
        # Estatísticas
        total_items = df_final['Item'].nunique()
        matches_validos = len(df_final[df_final['% Compatibilidade'] >= 90])
        
        # Economia
        economia_por_item = (df_final['Valor Ref. Unitário'] - df_final['Preço com Margem 53%']) * df_final['Quantidade']
        economia_total = economia_por_item[economia_por_item > 0].sum()
        
        # Definir pasta de saída
        if self.usar_dados_teste:
            pasta_saida = Path("/home/ubuntu/teste_matching")
        else:
            pasta_saida = Path(Config.ORCAMENTOS_PATH)
        
        # Salvar arquivos
        arquivo_csv = pasta_saida / "RESULTADO_MATCHING_INTELIGENTE.csv"
        df_final.to_csv(arquivo_csv, index=False, encoding='utf-8-sig')
        
        arquivo_excel = pasta_saida / "RELATORIO_MATCHING_COMPLETO.xlsx"
        df_final.to_excel(arquivo_excel, index=False)
        
        # Relatório resumido
        resumo = f"""
# 🎯 Relatório de Matching de Produtos

## 📈 Resumo
- **Itens Analisados**: {total_items}
- **Matches Válidos**: {matches_validos}
- **Economia Estimada**: R$ {economia_total:,.2f}

## 🏆 Top Matches
{df_final.nlargest(5, '% Compatibilidade')[['Item', 'Produto Sugerido', '% Compatibilidade']].to_string(index=False)}

---
*Relatório gerado pelo Sistema Inteligente de Matching*
"""
        
        arquivo_md = pasta_saida / "RELATORIO_RESUMO.md"
        with open(arquivo_md, 'w', encoding='utf-8') as f:
            f.write(resumo)
        
        print(f"✅ Relatórios gerados!")
        print(f"   📁 Pasta: {pasta_saida}")
        print(f"   📄 CSV: {arquivo_csv.name}")
        print(f"   📊 Excel: {arquivo_excel.name}")
        print(f"   📝 Resumo: {arquivo_md.name}")
        print(f"   💰 Economia: R$ {economia_total:,.2f}")
        
        return True

def main():
    """Função principal"""
    print("🚀 Sistema Inteligente de Matching - Versão Simplificada")
    print("=" * 60)
    
    # Detectar se está em ambiente de teste
    usar_teste = os.path.exists("/home/ubuntu/teste_matching/PRODUTOS.xlsx")
    
    if usar_teste:
        print("🧪 Modo de teste detectado - usando dados de exemplo")
    else:
        print("🏢 Modo produção - usando dados reais")
    
    # Inicializar sistema
    matcher = ProductMatcher(usar_dados_teste=usar_teste)
    
    # Executar
    if matcher.processar_matching():
        if matcher.gerar_relatorios():
            print("\n🎉 Processo concluído com sucesso!")
        else:
            print("\n❌ Erro na geração de relatórios")
    else:
        print("\n❌ Erro no matching")

if __name__ == "__main__":
    main()

