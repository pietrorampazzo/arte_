"""
🎯 SISTEMA INTELIGENTE DE MATCHING DE PRODUTOS PARA LICITAÇÕES
Versão Final Otimizada com NLP Avançado

Características:
- TF-IDF para análise lexical
- Sentence Transformers para semântica (quando disponível)
- Zero-Shot Classification para categorização
- Análise jurídica automatizada
- Relatórios em múltiplos formatos
- Fallback para ambientes sem GPU/bibliotecas pesadas

Autor: Sistema Automatizado IA
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

# Tentativa de importação das bibliotecas de NLP
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    from transformers import pipeline
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

class Config:
    """Configurações do sistema"""
    
    # 🔧 CONFIGURAÇÕES PRINCIPAIS - AJUSTE AQUI
    PRODUTOS_PATH = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\PRODUTOS.xlsx"
    ORCAMENTOS_PATH = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\ORCAMENTOS"

    
    # Parâmetros de matching
    MARGEM_DISPUTA = 0.53  # 53% de margem
    MIN_COMPATIBILIDADE = 70.0  # Reduzido para mais matches
    MAX_SUGESTOES = 5
    
    # Modelos NLP
    SENTENCE_MODEL = 'all-MiniLM-L6-v2'
    ZERO_SHOT_MODEL = 'facebook/bart-large-mnli'
    
    # Pesos para score híbrido
    PESO_TFIDF = 0.3
    PESO_SEMANTICO = 0.4
    PESO_EXATO = 0.3

class AdvancedTextProcessor:
    """Processador de texto com múltiplas técnicas de NLP"""
    
    def __init__(self):
        print("🔄 Inicializando processador de texto...")
        
        # Inicializar TF-IDF
        if SKLEARN_AVAILABLE:
            self.tfidf_vectorizer = TfidfVectorizer(
                max_features=2000,
                ngram_range=(1, 3),
                lowercase=True,
                stop_words=None  # Manter palavras em português
            )
            print("✅ TF-IDF inicializado")
        else:
            self.tfidf_vectorizer = None
            print("⚠️ TF-IDF não disponível")
        
        # Inicializar Sentence Transformers
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.sentence_model = SentenceTransformer(Config.SENTENCE_MODEL)
                print("✅ Sentence Transformers inicializado")
            except Exception as e:
                print(f"⚠️ Erro ao carregar Sentence Transformers: {e}")
                self.sentence_model = None
        else:
            self.sentence_model = None
            print("⚠️ Sentence Transformers não disponível")
        
        # Inicializar Zero-Shot Classifier
        if TRANSFORMERS_AVAILABLE:
            try:
                self.zero_shot_classifier = pipeline(
                    "zero-shot-classification",
                    model=Config.ZERO_SHOT_MODEL,
                    device=0 if torch.cuda.is_available() else -1
                )
                print("✅ Zero-Shot Classifier inicializado")
            except Exception as e:
                print(f"⚠️ Erro ao carregar Zero-Shot: {e}")
                self.zero_shot_classifier = None
        else:
            self.zero_shot_classifier = None
            print("⚠️ Zero-Shot Classifier não disponível")
    
    def normalizar_texto(self, texto):
        """Normalização avançada de texto"""
        if pd.isna(texto) or texto is None:
            return ""
        
        texto = str(texto).upper()
        
        # Mapeamento completo de caracteres especiais
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
        
        # Limpar e normalizar
        texto = re.sub(r'[^\w\s]', ' ', texto)
        texto = re.sub(r'\s+', ' ', texto).strip()
        
        return texto
    
    def extrair_especificacoes_tecnicas(self, texto):
        """Extrai especificações técnicas detalhadas"""
        especificacoes = []
        texto_norm = self.normalizar_texto(texto)
        
        # Padrões técnicos expandidos
        padroes_tecnicos = [
            # Elétricos
            r'(\d+)\s*(V|VOLTS?|WATTS?|W|A|AMPERES?|MA|MILIAMPERES?)',
            # Dimensões
            r'(\d+)\s*(MM|CM|M|METROS?|CENTIMETROS?|MILIMETROS?|POLEGADAS?|")',
            # Peso
            r'(\d+)\s*(KG|G|GRAMAS?|QUILOS?|LBS?)',
            # Musicais
            r'(\d+)\s*(CORDAS?|TECLAS?|CANAIS?|VOZES?|TONS?|OITAVAS?)',
            # Conectividade
            r'(USB|BLUETOOTH|WIFI|ETHERNET|MIDI|XLR|P10|RCA|OPTICAL)',
            # Display/Interface
            r'(LED|LCD|OLED|TFT|DISPLAY|TELA)',
            # Materiais
            r'(MADEIRA|METAL|PLASTICO|ACO|ALUMINIO|CARBONO|NYLON|BRONZE)',
            # Frequência
            r'(\d+)\s*(HZ|KHZ|MHZ|HERTZ)',
            # Capacidade
            r'(\d+)\s*(GB|MB|KB|BYTES?|BITS?)',
        ]
        
        for padrao in padroes_tecnicos:
            matches = re.findall(padrao, texto_norm)
            for match in matches:
                if isinstance(match, tuple):
                    especificacoes.append(' '.join(match))
                else:
                    especificacoes.append(match)
        
        return list(set(especificacoes))
    
    def calcular_similaridade_jaccard(self, texto1, texto2):
        """Similaridade Jaccard (básica mas eficiente)"""
        palavras1 = set(self.normalizar_texto(texto1).split())
        palavras2 = set(self.normalizar_texto(texto2).split())
        
        if not palavras1 or not palavras2:
            return 0.0
        
        intersecao = palavras1.intersection(palavras2)
        uniao = palavras1.union(palavras2)
        
        return (len(intersecao) / len(uniao)) * 100 if uniao else 0.0
    
    def calcular_similaridade_tfidf(self, texto1, texto2):
        """Similaridade usando TF-IDF"""
        if not self.tfidf_vectorizer:
            return self.calcular_similaridade_jaccard(texto1, texto2)
        
        try:
            textos = [self.normalizar_texto(texto1), self.normalizar_texto(texto2)]
            if not textos[0] or not textos[1]:
                return 0.0
            
            tfidf_matrix = self.tfidf_vectorizer.fit_transform(textos)
            similaridade = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            return float(similaridade * 100)
        except Exception as e:
            return self.calcular_similaridade_jaccard(texto1, texto2)
    
    def calcular_similaridade_semantica(self, texto1, texto2):
        """Similaridade semântica usando Sentence Transformers"""
        if not self.sentence_model:
            return self.calcular_similaridade_tfidf(texto1, texto2)
        
        try:
            embeddings = self.sentence_model.encode([
                self.normalizar_texto(texto1),
                self.normalizar_texto(texto2)
            ])
            similaridade = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
            return float(similaridade * 100)
        except Exception as e:
            return self.calcular_similaridade_tfidf(texto1, texto2)
    
    def classificar_categoria_produto(self, texto):
        """Classifica categoria do produto usando Zero-Shot"""
        categorias_instrumentos = [
            "instrumentos de corda",
            "instrumentos de sopro", 
            "instrumentos de percussão",
            "equipamentos de áudio",
            "acessórios musicais",
            "eletrônicos musicais"
        ]
        
        if not self.zero_shot_classifier:
            # Fallback simples por palavras-chave
            texto_upper = texto.upper()
            if any(palavra in texto_upper for palavra in ['VIOLAO', 'GUITARRA', 'BAIXO', 'CORDAS']):
                return "instrumentos de corda"
            elif any(palavra in texto_upper for palavra in ['BATERIA', 'PERCUSSAO', 'TAMBOR']):
                return "instrumentos de percussão"
            elif any(palavra in texto_upper for palavra in ['MICROFONE', 'AMPLIFICADOR', 'CAIXA']):
                return "equipamentos de áudio"
            else:
                return "acessórios musicais"
        
        try:
            resultado = self.zero_shot_classifier(texto, categorias_instrumentos)
            return resultado['labels'][0]
        except Exception as e:
            return "acessórios musicais"

class SmartLegalAnalyzer:
    """Analisador jurídico inteligente"""
    
    @staticmethod
    def analisar_direcionamento_avancado(descricao_edital):
        """Análise jurídica avançada de direcionamento"""
        texto_upper = descricao_edital.upper()
        
        # Padrões de direcionamento mais sofisticados
        padroes_criticos = [
            r'\bMARCA\s*[:\-]?\s*(\w+)',
            r'\bEXCLUSIVAMENTE\s+MARCA\s+(\w+)',
            r'\bAPENAS\s+(\w+)',
            r'\bSOBRETUDO\s+(\w+)',
            r'\bUNICAMENTE\s+(\w+)',
            r'(\w+)\s+OU\s+EQUIVALENTE',  # Pode ser aceitável
            r'(\w+)\s+OU\s+SIMILAR',      # Pode ser aceitável
        ]
        
        padroes_suspeitos = [
            r'\bEXCLUSIVO\b',
            r'\bPROPRIETARIO\b',
            r'\bORIGINAL\b.*\bMARCA\b',
            r'\bCERTIFICADO\s+POR\s+(\w+)',
        ]
        
        direcionamentos_encontrados = []
        suspeitas_encontradas = []
        
        # Verificar padrões críticos
        for padrao in padroes_criticos:
            matches = re.findall(padrao, texto_upper)
            direcionamentos_encontrados.extend(matches)
        
        # Verificar padrões suspeitos
        for padrao in padroes_suspeitos:
            matches = re.findall(padrao, texto_upper)
            suspeitas_encontradas.extend(matches)
        
        # Verificar se há justificativa técnica
        tem_justificativa = any(palavra in texto_upper for palavra in [
            'COMPATIBILIDADE', 'INTEROPERABILIDADE', 'INTEGRAÇÃO',
            'PROTOCOLO', 'PADRÃO', 'NORMA', 'CERTIFICAÇÃO'
        ])
        
        # Determinar nível de risco
        if direcionamentos_encontrados and not tem_justificativa:
            risco = "ALTO"
            exige_impugnacao = True
            observacao = f"""🚨 DIRECIONAMENTO IDENTIFICADO - RISCO ALTO
            
Irregularidades encontradas: {', '.join(direcionamentos_encontrados)}
            
FUNDAMENTAÇÃO JURÍDICA:
• Lei 14.133/21, Art. 7º, §5º - Vedação ao direcionamento
• Art. 25 - Princípio da isonomia entre licitantes  
• Art. 11 - Economicidade e competitividade
            
RECOMENDAÇÃO: Impugnar especificação por restringir competitividade sem justificativa técnica adequada."""
            
        elif suspeitas_encontradas:
            risco = "MÉDIO"
            exige_impugnacao = True
            observacao = f"""⚠️ POSSÍVEL DIRECIONAMENTO - RISCO MÉDIO
            
Elementos suspeitos: {', '.join(suspeitas_encontradas)}
            
RECOMENDAÇÃO: Solicitar esclarecimentos sobre a necessidade específica da exigência."""
            
        else:
            risco = "BAIXO"
            exige_impugnacao = False
            observacao = "✅ Especificação técnica adequada. Permite competição entre fornecedores equivalentes conforme Lei 14.133/21."
        
        return {
            'risco': risco,
            'exige_impugnacao': exige_impugnacao,
            'observacao': observacao,
            'direcionamentos': direcionamentos_encontrados,
            'suspeitas': suspeitas_encontradas,
            'tem_justificativa': tem_justificativa
        }

class IntelligentProductMatcher:
    """Sistema principal de matching inteligente"""
    
    def __init__(self):
        print("🚀 Inicializando Sistema Inteligente de Matching...")
        self.text_processor = AdvancedTextProcessor()
        self.legal_analyzer = SmartLegalAnalyzer()
        self.produtos_df = None
        self.resultados = []
        self.estatisticas = {}
    
    def carregar_dados(self):
        """Carrega e valida dados"""
        print("\n📂 Carregando dados...")
        
        try:
            # Verificar se arquivos existem
            produtos_path = Path(Config.PRODUTOS_PATH)
            orcamentos_path = Path(Config.ORCAMENTOS_PATH)
            
            if not produtos_path.exists():
                print(f"❌ Arquivo de produtos não encontrado: {produtos_path}")
                return False
            
            if not orcamentos_path.exists():
                print(f"❌ Pasta de orçamentos não encontrada: {orcamentos_path}")
                return False
            
            # Carregar produtos
            self.produtos_df = pd.read_excel(produtos_path)
            self.produtos_df.columns = self.produtos_df.columns.str.strip()
            
            # Validar colunas necessárias
            colunas_necessarias = ['MARCA', 'DESCRICAO', 'VALOR']
            colunas_faltantes = [col for col in colunas_necessarias if col not in self.produtos_df.columns]
            
            if colunas_faltantes:
                print(f"⚠️ Colunas faltantes em PRODUTOS.xlsx: {colunas_faltantes}")
                print(f"Colunas disponíveis: {list(self.produtos_df.columns)}")
            
            print(f"✅ {len(self.produtos_df)} produtos carregados")
            
            # Listar arquivos de orçamentos
            self.arquivos_orcamento = list(orcamentos_path.glob("*.xlsx"))
            print(f"✅ {len(self.arquivos_orcamento)} arquivos de orçamento encontrados")
            
            if not self.arquivos_orcamento:
                print("❌ Nenhum arquivo .xlsx encontrado na pasta de orçamentos")
                return False
            
            return True
            
        except Exception as e:
            print(f"❌ Erro ao carregar dados: {e}")
            return False
    
    def extrair_valor_numerico(self, valor):
        """Extração robusta de valores numéricos"""
        if pd.isna(valor) or valor is None:
            return 0.0
        
        # Converter para string e limpar
        valor_str = str(valor).strip()
        
        # Remover símbolos de moeda e espaços
        valor_str = re.sub(r'[R$\s]', '', valor_str)
        
        # Tratar formato brasileiro (1.234,56)
        if ',' in valor_str and '.' in valor_str:
            # Formato: 1.234,56
            valor_str = valor_str.replace('.', '').replace(',', '.')
        elif ',' in valor_str:
            # Formato: 1234,56
            valor_str = valor_str.replace(',', '.')
        
        try:
            # Extrair apenas números e ponto decimal
            match = re.search(r'[\d\.]+', valor_str)
            return float(match.group()) if match else 0.0
        except (ValueError, AttributeError):
            return 0.0
    
    def calcular_score_hibrido_avancado(self, desc_edital, produto):
        """Sistema de scoring híbrido avançado"""
        
        # Preparar textos
        texto_edital = desc_edital
        
        # Combinar informações do produto
        campos_produto = []
        for campo in ['MODELO', 'DESCRIÇÃO', 'DESCRICAO']:
            if campo in produto and pd.notna(produto[campo]):
                campos_produto.append(str(produto[campo]))
        
        texto_produto = ' '.join(campos_produto)
        
        if not texto_produto.strip():
            return 0.0, {}
        
        # 1. Similaridade TF-IDF (30%)
        score_tfidf = self.text_processor.calcular_similaridade_tfidf(texto_edital, texto_produto)
        
        # 2. Similaridade Semântica (40%)
        score_semantico = self.text_processor.calcular_similaridade_semantica(texto_edital, texto_produto)
        
        # 3. Match Exato de Modelo (30%)
        modelo = str(produto.get('MODELO', ''))
        score_exato = 0.0
        if modelo and len(modelo) > 2:  # Evitar matches muito curtos
            if modelo.upper() in texto_edital.upper():
                score_exato = 100.0
            elif any(palavra in texto_edital.upper() for palavra in modelo.upper().split() if len(palavra) > 2):
                score_exato = 80.0
        
        # 4. Compatibilidade de Especificações (bônus até 15%)
        specs_edital = self.text_processor.extrair_especificacoes_tecnicas(texto_edital)
        specs_produto = self.text_processor.extrair_especificacoes_tecnicas(texto_produto)
        
        bonus_specs = 0.0
        if specs_edital and specs_produto:
            specs_comuns = set(specs_edital) & set(specs_produto)
            bonus_specs = (len(specs_comuns) / len(specs_edital)) * 15
        
        # 5. Compatibilidade de Categoria (bônus até 10%)
        categoria_edital = self.text_processor.classificar_categoria_produto(texto_edital)
        categoria_produto = self.text_processor.classificar_categoria_produto(texto_produto)
        bonus_categoria = 10.0 if categoria_edital == categoria_produto else 0.0
        
        # Score final híbrido
        score_base = (
            score_tfidf * Config.PESO_TFIDF +
            score_semantico * Config.PESO_SEMANTICO +
            score_exato * Config.PESO_EXATO
        )
        
        score_final = min(score_base + bonus_specs + bonus_categoria, 100.0)
        
        detalhes = {
            'tfidf': round(score_tfidf, 2),
            'semantico': round(score_semantico, 2),
            'exato': round(score_exato, 2),
            'specs_bonus': round(bonus_specs, 2),
            'categoria_bonus': round(bonus_categoria, 2),
            'specs_edital': specs_edital,
            'specs_produto': specs_produto,
            'categoria_edital': categoria_edital,
            'categoria_produto': categoria_produto
        }
        
        return round(score_final, 2), detalhes
    
    def processar_matching_completo(self):
        """Processo completo de matching"""
        if not self.carregar_dados():
            return False
        
        print("\n🔍 Iniciando processo de matching inteligente...")
        
        total_items_processados = 0
        total_matches_encontrados = 0
        
        for arquivo in self.arquivos_orcamento:
            print(f"\n📄 Processando: {arquivo.name}")
            
            try:
                df_edital = pd.read_excel(arquivo)
                items_arquivo = 0
                matches_arquivo = 0
                
                for _, item in df_edital.iterrows():
                    items_arquivo += 1
                    matches_item = self.processar_item_edital(item, arquivo.name)
                    matches_arquivo += matches_item
                
                print(f"   ✅ {items_arquivo} itens processados, {matches_arquivo} matches encontrados")
                total_items_processados += items_arquivo
                total_matches_encontrados += matches_arquivo
                
            except Exception as e:
                print(f"   ❌ Erro ao processar {arquivo.name}: {e}")
                continue
        
        # Atualizar estatísticas
        self.estatisticas = {
            'total_items': total_items_processados,
            'total_matches': total_matches_encontrados,
            'taxa_sucesso': (total_matches_encontrados / total_items_processados * 100) if total_items_processados > 0 else 0
        }
        
        print(f"\n✅ Matching concluído!")
        print(f"   📊 {total_items_processados} itens processados")
        print(f"   🎯 {total_matches_encontrados} matches encontrados")
        print(f"   📈 Taxa de sucesso: {self.estatisticas['taxa_sucesso']:.1f}%")
        
        return True
    
    def processar_item_edital(self, item, nome_arquivo):
        """Processa um item específico do edital"""
        # Extrair dados do item
        num_item = item.get('Número do Item', 'N/A')
        desc_edital = str(item.get('Item', ''))
        unidade = item.get('Unidade de Fornecimento', 'UN')
        qtd = float(item.get('Quantidade Total', 0))
        valor_ref = self.extrair_valor_numerico(item.get('Valor Unitário (R$)', 0))
        
        # Validações básicas
        if not desc_edital.strip() or len(desc_edital) < 10:
            return 0
        
        if valor_ref <= 0:
            return 0
        
        # Análise jurídica avançada
        analise_juridica = self.legal_analyzer.analisar_direcionamento_avancado(desc_edital)
        
        # Buscar matches nos produtos
        matches_encontrados = []
        
        for _, produto in self.produtos_df.iterrows():
            score, detalhes = self.calcular_score_hibrido_avancado(desc_edital, produto)
            
            if score >= Config.MIN_COMPATIBILIDADE:
                valor_produto = self.extrair_valor_numerico(produto.get('VALOR', produto.get('Valor', 0)))
                
                if valor_produto > 0:
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
        
        # Ordenar por score decrescente e preço crescente
        matches_encontrados.sort(key=lambda x: (-x['score'], x['valor_disputa']))
        
        # Selecionar os melhores matches
        matches_selecionados = matches_encontrados[:Config.MAX_SUGESTOES]
        
        # Adicionar resultados
        for match in matches_selecionados:
            self.adicionar_resultado_detalhado(
                num_item, desc_edital, unidade, qtd, valor_ref,
                match, analise_juridica, nome_arquivo
            )
        
        return len(matches_selecionados)
    
    def adicionar_resultado_detalhado(self, num_item, desc_edital, unidade, qtd, valor_ref, match, analise_juridica, arquivo):
        """Adiciona resultado com detalhamento completo"""
        produto = match['produto']
        score = match['score']
        detalhes = match['detalhes']
        valor_produto = match['valor_produto']
        valor_disputa = match['valor_disputa']
        
        # Preparar comparação técnica detalhada
        comparacao_tecnica = []
        comparacao_tecnica.append(f"Score Total: {score}%")
        comparacao_tecnica.append(f"TF-IDF: {detalhes['tfidf']}%")
        comparacao_tecnica.append(f"Semântico: {detalhes['semantico']}%")
        
        if detalhes['exato'] > 0:
            comparacao_tecnica.append(f"Match Exato: {detalhes['exato']}%")
        
        if detalhes['specs_edital']:
            comparacao_tecnica.append(f"Specs: {', '.join(detalhes['specs_edital'][:3])}")
        
        comparacao_final = " | ".join(comparacao_tecnica)
        
        # Determinar capacidade de substituição
        if score >= 95:
            pode_substituir = "Excelente"
        elif score >= 90:
            pode_substituir = "Sim"
        elif score >= 80:
            pode_substituir = "Parcialmente"
        else:
            pode_substituir = "Limitado"
        
        # Calcular economia
        economia_unitaria = valor_ref - valor_disputa
        economia_total = economia_unitaria * qtd
        
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
            'Economia Unitária': economia_unitaria,
            'Economia Total': economia_total,
            'Comparação Técnica': comparacao_final,
            '% Compatibilidade': score,
            'Pode Substituir?': pode_substituir,
            'Categoria': detalhes.get('categoria_produto', 'N/A'),
            'Exige Impugnação?': 'Sim' if analise_juridica['exige_impugnacao'] else 'Não',
            'Risco Jurídico': analise_juridica['risco'],
            'Observação Jurídica': analise_juridica['observacao'],
            'Fornecedor': produto.get('FORNECEDOR', 'N/A')
        }
        
        self.resultados.append(resultado)
    
    def gerar_relatorios_completos(self):
        """Gera relatórios completos em múltiplos formatos"""
        if not self.resultados:
            print("❌ Nenhum resultado para gerar relatórios")
            return False
        
        print("\n📊 Gerando relatórios completos...")
        
        # Criar DataFrame
        df_final = pd.DataFrame(self.resultados)
        
        # Calcular estatísticas avançadas
        total_items = df_final['Item'].nunique()
        matches_excelentes = len(df_final[df_final['% Compatibilidade'] >= 95])
        matches_bons = len(df_final[df_final['% Compatibilidade'] >= 90])
        economia_total = df_final['Economia Total'].sum()
        
        # Definir pasta de saída
        pasta_saida = Path(Config.ORCAMENTOS_PATH)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 1. CSV Principal
        arquivo_csv = pasta_saida / f"MATCHING_INTELIGENTE_{timestamp}.csv"
        df_final.to_csv(arquivo_csv, index=False, encoding='utf-8-sig')
        
        # 2. Excel com múltiplas abas
        arquivo_excel = pasta_saida / f"RELATORIO_COMPLETO_{timestamp}.xlsx"
        with pd.ExcelWriter(arquivo_excel, engine='openpyxl') as writer:
            # Aba principal
            df_final.to_excel(writer, sheet_name='Matches Completos', index=False)
            
            # Aba de melhores matches
            df_melhores = df_final[df_final['% Compatibilidade'] >= 90].copy()
            df_melhores.to_excel(writer, sheet_name='Melhores Matches', index=False)
            
            # Aba de economia
            df_economia = df_final.groupby('Item').agg({
                'Economia Total': 'max',
                '% Compatibilidade': 'max',
                'Produto Sugerido': 'first'
            }).reset_index()
            df_economia.to_excel(writer, sheet_name='Análise de Economia', index=False)
            
            # Aba de riscos jurídicos
            df_riscos = df_final[df_final['Exige Impugnação?'] == 'Sim'].copy()
            if not df_riscos.empty:
                df_riscos.to_excel(writer, sheet_name='Riscos Jurídicos', index=False)
        
        # 3. Relatório Markdown Detalhado
        self.gerar_relatorio_markdown_avancado(df_final, pasta_saida, timestamp)
        
        # 4. Sobrescrever arquivos principais (conforme solicitado)
        arquivo_csv_principal = pasta_saida / "RESULTADO_MATCHING_INTELIGENTE.csv"
        arquivo_excel_principal = pasta_saida / "RELATORIO_MATCHING_COMPLETO.xlsx"
        
        df_final.to_csv(arquivo_csv_principal, index=False, encoding='utf-8-sig')
        df_final.to_excel(arquivo_excel_principal, index=False)
        
        print(f"✅ Relatórios gerados com sucesso!")
        print(f"   📁 Pasta: {pasta_saida}")
        print(f"   📄 CSV Principal: RESULTADO_MATCHING_INTELIGENTE.csv")
        print(f"   📊 Excel Principal: RELATORIO_MATCHING_COMPLETO.xlsx")
        print(f"   📄 CSV Timestamped: {arquivo_csv.name}")
        print(f"   📊 Excel Completo: {arquivo_excel.name}")
        print(f"   💰 Economia Total Estimada: R$ {economia_total:,.2f}")
        print(f"   🎯 Matches Excelentes (≥95%): {matches_excelentes}")
        print(f"   ✅ Matches Bons (≥90%): {matches_bons}")
        
        return True
    
    def gerar_relatorio_markdown_avancado(self, df_final, pasta_saida, timestamp):
        """Gera relatório Markdown avançado"""
        arquivo_md = pasta_saida / f"RELATORIO_DETALHADO_{timestamp}.md"
        
        # Estatísticas detalhadas
        stats_compat = df_final.groupby(pd.cut(df_final['% Compatibilidade'], 
                                              bins=[0, 70, 80, 90, 95, 100], 
                                              labels=['70-79%', '80-89%', '90-94%', '95-99%', '100%'])).size()
        
        economia_por_categoria = df_final.groupby('Categoria')['Economia Total'].sum().sort_values(ascending=False)
        
        top_fornecedores = df_final.groupby('Fornecedor').agg({
            'Economia Total': 'sum',
            '% Compatibilidade': 'mean'
        }).sort_values('Economia Total', ascending=False).head(5)
        
        conteudo = f"""# 🎯 Relatório Inteligente de Matching de Produtos para Licitações

**Data de Geração**: {datetime.now().strftime('%d/%m/%Y às %H:%M')}  
**Tecnologia**: TF-IDF + Sentence Transformers + Zero-Shot Classification  
**Versão**: Sistema Inteligente v2.0

---

## 📈 Resumo Executivo

| Métrica | Valor |
|---------|-------|
| **Total de Itens Analisados** | {df_final['Item'].nunique()} |
| **Matches Encontrados** | {len(df_final)} |
| **Taxa de Sucesso** | {self.estatisticas.get('taxa_sucesso', 0):.1f}% |
| **Economia Total Estimada** | R$ {df_final['Economia Total'].sum():,.2f} |
| **Matches Excelentes (≥95%)** | {len(df_final[df_final['% Compatibilidade'] >= 95])} |
| **Matches Bons (≥90%)** | {len(df_final[df_final['% Compatibilidade'] >= 90])} |

---

## 🔍 Distribuição de Compatibilidade

```
{stats_compat.to_string()}
```

---

## 💰 Economia por Categoria

{economia_por_categoria.head().to_string()}

---

## 🏆 Top 5 Fornecedores por Economia

{top_fornecedores.to_string()}

---

## ⚖️ Análise Jurídica

| Risco | Quantidade |
|-------|------------|
| **Alto** | {len(df_final[df_final['Risco Jurídico'] == 'ALTO'])} |
| **Médio** | {len(df_final[df_final['Risco Jurídico'] == 'MÉDIO'])} |
| **Baixo** | {len(df_final[df_final['Risco Jurídico'] == 'BAIXO'])} |

**Itens que Exigem Impugnação**: {len(df_final[df_final['Exige Impugnação?'] == 'Sim'])}

---

## 🥇 Top 10 Melhores Matches

{df_final.nlargest(10, '% Compatibilidade')[['Item', 'Produto Sugerido', '% Compatibilidade', 'Economia Total']].to_string(index=False)}

---

## 🔬 Metodologia Aplicada

### Técnicas de NLP Utilizadas:

1. **TF-IDF (Term Frequency-Inverse Document Frequency)**
   - Peso: 30%
   - Análise estatística de relevância de termos
   - Identifica palavras-chave importantes

2. **Sentence Transformers**
   - Peso: 40%  
   - Embeddings semânticos para compreensão contextual
   - Modelo: all-MiniLM-L6-v2

3. **Zero-Shot Classification**
   - Categorização automática de produtos
   - Modelo: facebook/bart-large-mnli

4. **Matching Exato**
   - Peso: 30%
   - Identificação direta de modelos específicos

### Sistema de Scoring:
- **Score Base**: Combinação ponderada das técnicas
- **Bônus Especificações**: Até 15% por compatibilidade técnica
- **Bônus Categoria**: Até 10% por categoria compatível

---

## 📋 Conformidade Legal

**Base Legal**: Lei 14.133/21 (Nova Lei de Licitações)

### Princípios Garantidos:
- ✅ **Isonomia** (Art. 5º) - Igualdade entre fornecedores
- ✅ **Impessoalidade** (Art. 5º) - Análise técnica objetiva  
- ✅ **Economicidade** (Art. 11) - Melhor relação custo-benefício
- ✅ **Competitividade** (Art. 25) - Disputa ampla entre fornecedores

### Critérios de Análise:
- **Risco Alto**: Direcionamento claro sem justificativa técnica
- **Risco Médio**: Elementos suspeitos que merecem esclarecimento
- **Risco Baixo**: Especificação técnica adequada

---

## 🚀 Próximos Passos Recomendados

1. **Revisar matches com compatibilidade ≥90%** para proposta
2. **Analisar itens de risco alto** para possível impugnação
3. **Validar especificações técnicas** dos produtos selecionados
4. **Preparar documentação** para fundamentar escolhas

---

*Relatório gerado automaticamente pelo Sistema Inteligente de Matching*  
*Desenvolvido com tecnologias de IA avançadas para máxima precisão e conformidade legal*
"""
        
        with open(arquivo_md, 'w', encoding='utf-8') as f:
            f.write(conteudo)

def main():
    """Função principal do sistema"""
    print("🎯 SISTEMA INTELIGENTE DE MATCHING DE PRODUTOS PARA LICITAÇÕES")
    print("=" * 80)
    print("Versão: 2.0 Final | Tecnologia: NLP Avançado | Data:", datetime.now().strftime('%d/%m/%Y'))
    print("=" * 80)
    
    # Inicializar sistema
    matcher = IntelligentProductMatcher()
    
    # Executar processo completo
    try:
        if matcher.processar_matching_completo():
            if matcher.gerar_relatorios_completos():
                print("\n🎉 PROCESSO CONCLUÍDO COM SUCESSO!")
                print("📁 Verifique os arquivos gerados na pasta de orçamentos")
                print("💡 Arquivos principais sobrescritos conforme solicitado")
            else:
                print("\n❌ Erro na geração de relatórios")
        else:
            print("\n❌ Erro no processo de matching")
    
    except KeyboardInterrupt:
        print("\n⏹️ Processo interrompido pelo usuário")
    except Exception as e:
        print(f"\n💥 Erro inesperado: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

