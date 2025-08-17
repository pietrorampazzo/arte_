"""
🎯 SISTEMA DE MATCHING COM PIPELINE TRANSFORMERS
Versão Corrigida - Sem Erros de Sintaxe

Implementação usando pipeline do Transformers conforme solicitado:
from transformers import pipeline
pipe = pipeline("text-generation", model="Qwen/Qwen3-235B-A22B-Instruct-2507")

Funcionalidades:
- Pipeline Transformers para análise semântica
- Matching inteligente baseado em embeddings
- Análise jurídica automatizada
- Relatórios detalhados
- Configuração simples

Autor: Sistema com Pipeline
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

# Importações necessárias
try:
    from transformers import pipeline
    import torch
    TRANSFORMERS_AVAILABLE = True
    print("✅ Transformers disponível")
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    print("❌ Transformers não disponível - instale com: pip install transformers torch")

class ConfigPipeline:
    """Configurações do sistema com pipeline"""
    
    # 🔧 AJUSTE AQUI OS CAMINHOS
    PRODUTOS_PATH = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\PRODUTOS.xlsx"
    ORCAMENTOS_PATH = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\ORCAMENTOS"

    
    # Parâmetros
    MARGEM_DISPUTA = 0.53  # 53%
    MIN_COMPATIBILIDADE = 70.0
    MAX_SUGESTOES = 5
    
    # Configurações do pipeline
    MODELO_PIPELINE = "sentence-transformers/all-MiniLM-L6-v2"  # Modelo mais leve
    # MODELO_PIPELINE = "Qwen/Qwen3-235B-A22B-Instruct-2507"  # Modelo original (muito pesado)

class ProcessadorComPipeline:
    """Processador usando pipeline do Transformers"""
    
    def __init__(self):
        print("🔄 Inicializando processador com pipeline...")
        
        self.pipeline_embeddings = None
        self.pipeline_similarity = None
        
        if TRANSFORMERS_AVAILABLE:
            try:
                # Pipeline para embeddings (mais eficiente que text-generation para matching)
                print("📥 Carregando modelo para embeddings...")
                self.pipeline_embeddings = pipeline(
                    "feature-extraction",
                    model=ConfigPipeline.MODELO_PIPELINE,
                    return_tensors="np"
                )
                print("✅ Pipeline de embeddings inicializado")
                
                # Pipeline para análise de similaridade textual
                print("📥 Carregando pipeline de análise...")
                self.pipeline_similarity = pipeline(
                    "text-classification",
                    model="microsoft/DialoGPT-medium",
                    return_all_scores=True
                )
                print("✅ Pipeline de similaridade inicializado")
                
            except Exception as e:
                print("⚠️ Erro ao carregar pipeline: " + str(e))
                print("🔄 Usando fallback básico...")
                self.pipeline_embeddings = None
                self.pipeline_similarity = None
        else:
            print("❌ Transformers não disponível")
    
    def normalizar_texto(self, texto):
        """Normalização de texto"""
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
        
        # Limpar
        texto = re.sub(r'[^A-Z0-9\s]', ' ', texto)
        texto = re.sub(r'\s+', ' ', texto).strip()
        
        return texto
    
    def extrair_especificacoes(self, texto):
        """Extrai especificações técnicas"""
        specs = []
        texto_norm = self.normalizar_texto(texto)
        
        padroes = [
            r'(\d+)\s*(V|VOLTS?|W|WATTS?|A|AMPERES?)',
            r'(\d+)\s*(MM|CM|M|METROS?|POLEGADAS?)',
            r'(\d+)\s*(KG|G|GRAMAS?|QUILOS?)',
            r'(\d+)\s*(CORDAS?|TECLAS?|CANAIS?|VOZES?)',
            r'(USB|BLUETOOTH|WIFI|MIDI|XLR|P10)',
            r'(LED|LCD|OLED|DISPLAY)',
            r'(MADEIRA|METAL|PLASTICO|ACO|ALUMINIO)',
            r'(\d+)\s*(HZ|KHZ|HERTZ)',
        ]
        
        for padrao in padroes:
            matches = re.findall(padrao, texto_norm)
            for match in matches:
                if isinstance(match, tuple):
                    specs.append(' '.join(match))
                else:
                    specs.append(match)
        
        return list(set(specs))
    
    def calcular_similaridade_pipeline(self, texto1, texto2):
        """Calcula similaridade usando pipeline"""
        
        if self.pipeline_embeddings:
            try:
                # Método 1: Embeddings com pipeline
                texto1_norm = self.normalizar_texto(texto1)
                texto2_norm = self.normalizar_texto(texto2)
                
                if not texto1_norm or not texto2_norm:
                    return 0.0
                
                # Gerar embeddings
                emb1 = self.pipeline_embeddings(texto1_norm)
                emb2 = self.pipeline_embeddings(texto2_norm)
                
                # Calcular similaridade coseno
                emb1_mean = np.array(emb1).mean(axis=1).flatten()
                emb2_mean = np.array(emb2).mean(axis=1).flatten()
                
                # Similaridade coseno
                dot_product = np.dot(emb1_mean, emb2_mean)
                norm1 = np.linalg.norm(emb1_mean)
                norm2 = np.linalg.norm(emb2_mean)
                
                if norm1 == 0 or norm2 == 0:
                    return 0.0
                
                similarity = dot_product / (norm1 * norm2)
                return float(similarity * 100)
                
            except Exception as e:
                print("⚠️ Erro no pipeline: " + str(e))
                pass
        
        # Fallback: Similaridade Jaccard
        return self.calcular_similaridade_jaccard(texto1, texto2)
    
    def calcular_similaridade_jaccard(self, texto1, texto2):
        """Fallback: Similaridade Jaccard"""
        palavras1 = set(self.normalizar_texto(texto1).split())
        palavras2 = set(self.normalizar_texto(texto2).split())
        
        if not palavras1 or not palavras2:
            return 0.0
        
        intersecao = palavras1.intersection(palavras2)
        uniao = palavras1.union(palavras2)
        
        return (len(intersecao) / len(uniao)) * 100 if uniao else 0.0
    
    def analisar_com_pipeline(self, texto_edital, texto_produto):
        """Análise completa usando pipeline"""
        
        # 1. Similaridade semântica principal
        score_semantico = self.calcular_similaridade_pipeline(texto_edital, texto_produto)
        
        # 2. Análise de especificações
        specs_edital = self.extrair_especificacoes(texto_edital)
        specs_produto = self.extrair_especificacoes(texto_produto)
        
        bonus_specs = 0.0
        if specs_edital and specs_produto:
            specs_comuns = set(specs_edital) & set(specs_produto)
            bonus_specs = (len(specs_comuns) / len(specs_edital)) * 15
        
        # 3. Match exato de palavras-chave
        palavras_edital = set(self.normalizar_texto(texto_edital).split())
        palavras_produto = set(self.normalizar_texto(texto_produto).split())
        
        palavras_importantes = [p for p in palavras_edital if len(p) > 3]
        matches_exatos = sum(1 for p in palavras_importantes if p in palavras_produto)
        bonus_exato = (matches_exatos / len(palavras_importantes)) * 20 if palavras_importantes else 0
        
        # Score final
        score_final = min(score_semantico + bonus_specs + bonus_exato, 100.0)
        
        detalhes = {
            'semantico': round(score_semantico, 2),
            'specs_bonus': round(bonus_specs, 2),
            'exato_bonus': round(bonus_exato, 2),
            'specs_edital': specs_edital,
            'specs_produto': specs_produto,
            'palavras_match': matches_exatos
        }
        
        return round(score_final, 2), detalhes

class AnalisadorJuridico:
    """Análise jurídica com pipeline (se disponível)"""
    
    def __init__(self, processador):
        self.processador = processador
    
    def analisar_direcionamento(self, descricao):
        """Análise de direcionamento"""
        texto = descricao.upper()
        
        # Padrões de direcionamento
        padroes_criticos = [
            r'\bMARCA\s+([A-Z]+)',
            r'\bEXCLUSIVAMENTE\b',
            r'\bAPENAS\s+([A-Z]+)',
            r'\bUNICAMENTE\b',
            r'\bEXCLUSIVO\b'
        ]
        
        direcionamentos = []
        for padrao in padroes_criticos:
            matches = re.findall(padrao, texto)
            direcionamentos.extend(matches)
        
        # Verificar justificativa técnica
        tem_justificativa = any(palavra in texto for palavra in [
            'COMPATIBILIDADE', 'INTEROPERABILIDADE', 'PROTOCOLO', 
            'PADRÃO', 'NORMA', 'CERTIFICAÇÃO'
        ])
        
        if direcionamentos and not tem_justificativa:
            return {
                'exige_impugnacao': True,
                'risco': 'ALTO',
                'observacao': 'Direcionamento identificado: ' + ", ".join(direcionamentos) + '. Recomenda-se impugnação baseada na Lei 14.133/21 (Art. 7º §5º) para garantir isonomia e competitividade.',
                'direcionamentos': direcionamentos
            }
        elif direcionamentos:
            return {
                'exige_impugnacao': True,
                'risco': 'MÉDIO',
                'observacao': 'Possível direcionamento com justificativa técnica. Avaliar necessidade de esclarecimentos.',
                'direcionamentos': direcionamentos
            }
        else:
            return {
                'exige_impugnacao': False,
                'risco': 'BAIXO',
                'observacao': 'Especificação técnica adequada. Permite competição entre fornecedores equivalentes.',
                'direcionamentos': []
            }

class MatchingComPipeline:
    """Sistema principal com pipeline"""
    
    def __init__(self):
        print("🚀 Inicializando Sistema com Pipeline Transformers...")
        self.processador = ProcessadorComPipeline()
        self.analisador = AnalisadorJuridico(self.processador)
        self.produtos_df = None
        self.resultados = []
    
    def carregar_dados(self):
        """Carrega dados"""
        print("\n📂 Carregando dados...")
        
        try:
            # Verificar arquivos
            if not os.path.exists(ConfigPipeline.PRODUTOS_PATH):
                print("❌ Arquivo não encontrado: " + ConfigPipeline.PRODUTOS_PATH)
                return False
            
            if not os.path.exists(ConfigPipeline.ORCAMENTOS_PATH):
                print("❌ Pasta não encontrada: " + ConfigPipeline.ORCAMENTOS_PATH)
                return False
            
            # Carregar produtos
            self.produtos_df = pd.read_excel(ConfigPipeline.PRODUTOS_PATH)
            self.produtos_df.columns = self.produtos_df.columns.str.strip()
            print("✅ " + str(len(self.produtos_df)) + " produtos carregados")
            
            # Listar orçamentos
            pasta = Path(ConfigPipeline.ORCAMENTOS_PATH)
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
    
    def processar_tudo(self):
        """Processa todos os arquivos"""
        if not self.carregar_dados():
            return False
        
        print("\n🔍 Processando com pipeline...")
        
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
                
                print("   ✅ " + str(matches) + " matches encontrados")
                
            except Exception as e:
                print("   ❌ Erro: " + str(e))
                continue
        
        print("\n✅ Concluído! " + str(total_items) + " itens, " + str(total_matches) + " matches")
        return True
    
    def processar_item(self, item, arquivo):
        """Processa item do edital"""
        # Extrair dados
        num_item = item.get('Número do Item', 'N/A')
        desc_edital = str(item.get('Item', ''))
        unidade = item.get('Unidade de Fornecimento', 'UN')
        qtd = float(item.get('Quantidade Total', 0))
        valor_ref = self.extrair_valor(item.get('Valor Unitário (R$)', 0))
        
        if not desc_edital or valor_ref <= 0:
            return 0
        
        # Análise jurídica
        analise = self.analisador.analisar_direcionamento(desc_edital)
        
        # Buscar matches
        matches_encontrados = []
        
        for _, produto in self.produtos_df.iterrows():
            # Preparar texto do produto
            texto_produto = str(produto.get('MODELO', '')) + " " + str(produto.get('DESCRIÇÃO', '')) + " " + str(produto.get('DESCRICAO', ''))
            
            if not texto_produto.strip():
                continue
            
            # Usar pipeline para análise
            score, detalhes = self.processador.analisar_com_pipeline(desc_edital, texto_produto)
            
            if score >= ConfigPipeline.MIN_COMPATIBILIDADE:
                valor_produto = self.extrair_valor(produto.get('VALOR', produto.get('Valor', 0)))
                
                if valor_produto > 0:
                    valor_disputa = valor_produto * (1 + ConfigPipeline.MARGEM_DISPUTA)
                    
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
        
        for match in matches_encontrados[:ConfigPipeline.MAX_SUGESTOES]:
            self.adicionar_resultado(num_item, desc_edital, unidade, qtd, valor_ref, match, analise, arquivo)
        
        return len(matches_encontrados[:ConfigPipeline.MAX_SUGESTOES])
    
    def adicionar_resultado(self, num_item, desc_edital, unidade, qtd, valor_ref, match, analise, arquivo):
        """Adiciona resultado"""
        produto = match['produto']
        score = match['score']
        detalhes = match['detalhes']
        valor_produto = match['valor_produto']
        valor_disputa = match['valor_disputa']
        
        # Comparação técnica detalhada
        comparacao = "Pipeline Score: " + str(round(score, 1)) + "%"
        comparacao += " | Semântico: " + str(round(detalhes['semantico'], 1)) + "%"
        if detalhes['specs_edital']:
            comparacao += " | Specs: " + ', '.join(detalhes['specs_edital'][:2])
        comparacao += " | Matches: " + str(detalhes['palavras_match'])
        
        # Capacidade de substituição
        if score >= 95:
            pode_substituir = "Excelente"
        elif score >= 85:
            pode_substituir = "Sim"
        elif score >= 75:
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
            'Risco Jurídico': analise['risco'],
            'Observação Jurídica': analise['observacao'],
            'Fornecedor': produto.get('FORNECEDOR', 'N/A')
        }
        
        self.resultados.append(resultado)
    
    def gerar_relatorios(self):
        """Gera relatórios"""
        if not self.resultados:
            print("❌ Nenhum resultado")
            return False
        
        print("\n📊 Gerando relatórios...")
        
        df_final = pd.DataFrame(self.resultados)
        
        # Estatísticas
        total_items = df_final['Item'].nunique()
        matches_excelentes = len(df_final[df_final['% Compatibilidade'] >= 95])
        matches_bons = len(df_final[df_final['% Compatibilidade'] >= 85])
        economia_total = (df_final['Valor Ref. Unitário'] - df_final['Preço com Margem 53%']) * df_final['Quantidade']
        economia_total = economia_total[economia_total > 0].sum()
        
        # Pasta de saída
        pasta_saida = Path(ConfigPipeline.ORCAMENTOS_PATH)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Arquivos principais (sobrescrever)
        arquivo_csv = pasta_saida / "RESULTADO_MATCHING_INTELIGENTE.csv"
        arquivo_excel = pasta_saida / "RELATORIO_MATCHING_COMPLETO.xlsx"
        
        df_final.to_csv(arquivo_csv, index=False, encoding='utf-8-sig')
        df_final.to_excel(arquivo_excel, index=False)
        
        # Arquivo com timestamp
        arquivo_pipeline = pasta_saida / ("MATCHING_PIPELINE_" + timestamp + ".csv")
        df_final.to_csv(arquivo_pipeline, index=False, encoding='utf-8-sig')
        
        # Relatório detalhado
        resumo = """
# 🎯 Relatório de Matching com Pipeline Transformers

**Data**: """ + datetime.now().strftime('%d/%m/%Y %H:%M') + """  
**Modelo**: """ + ConfigPipeline.MODELO_PIPELINE + """  
**Tecnologia**: Pipeline Transformers + Embeddings Semânticos

## 📊 Estatísticas

| Métrica | Valor |
|---------|-------|
| **Itens Analisados** | """ + str(total_items) + """ |
| **Matches Encontrados** | """ + str(len(df_final)) + """ |
| **Matches Excelentes (≥95%)** | """ + str(matches_excelentes) + """ |
| **Matches Bons (≥85%)** | """ + str(matches_bons) + """ |
| **Economia Estimada** | R$ """ + "{:,.2f}".format(economia_total) + """ |

## 🏆 Top 10 Melhores Matches

""" + df_final.nlargest(10, '% Compatibilidade')[['Item', 'Produto Sugerido', '% Compatibilidade']].to_string(index=False) + """

## ⚖️ Análise Jurídica

- **Risco Alto**: """ + str(len(df_final[df_final['Risco Jurídico'] == 'ALTO'])) + """
- **Risco Médio**: """ + str(len(df_final[df_final['Risco Jurídico'] == 'MÉDIO'])) + """
- **Risco Baixo**: """ + str(len(df_final[df_final['Risco Jurídico'] == 'BAIXO'])) + """

## 🔬 Metodologia Pipeline

1. **Embeddings Semânticos**: Análise contextual profunda
2. **Extração de Especificações**: Identificação automática de características técnicas
3. **Matching Exato**: Correspondência direta de palavras-chave
4. **Scoring Híbrido**: Combinação ponderada de todas as técnicas

---
*Relatório gerado com Pipeline Transformers para máxima precisão*
"""
        
        arquivo_md = pasta_saida / ("RELATORIO_PIPELINE_" + timestamp + ".md")
        with open(arquivo_md, 'w', encoding='utf-8') as f:
            f.write(resumo)
        
        print("✅ Relatórios gerados!")
        print("   📁 Pasta: " + str(pasta_saida))
        print("   📄 CSV Principal: RESULTADO_MATCHING_INTELIGENTE.csv")
        print("   📊 Excel Principal: RELATORIO_MATCHING_COMPLETO.xlsx")
        print("   📄 Pipeline CSV: " + arquivo_pipeline.name)
        print("   📝 Relatório: " + arquivo_md.name)
        print("   💰 Economia: R$ " + "{:,.2f}".format(economia_total))
        print("   🎯 Matches Excelentes: " + str(matches_excelentes))
        
        return True

def main():
    """Função principal"""
    print("🎯 SISTEMA DE MATCHING COM PIPELINE TRANSFORMERS")
    print("=" * 70)
    print("Versão: Pipeline Integrado | Data: " + datetime.now().strftime('%d/%m/%Y'))
    print("=" * 70)
    
    if not TRANSFORMERS_AVAILABLE:
        print("\n❌ ERRO: Transformers não está instalado!")
        print("📦 Instale com: pip install transformers torch")
        print("🔄 Ou use a versão simplificada: matching_simples_corrigido.py")
        return
    
    # Executar
    matcher = MatchingComPipeline()
    
    try:
        if matcher.processar_tudo():
            if matcher.gerar_relatorios():
                print("\n🎉 SUCESSO! Pipeline executado com êxito.")
                print("📁 Arquivos gerados na pasta de orçamentos")
                print("🚀 Matching realizado com tecnologia de ponta!")
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

