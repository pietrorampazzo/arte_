"""
🎯 SISTEMA FINAL DE MATCHING PARA LICITAÇÕES
Versão Corrigida - Resolve Problemas de Caminho e Sintaxe

Problemas identificados e corrigidos:
1. Erro de permissão no caminho do arquivo
2. Erros de sintaxe com f-strings
3. Caminhos incorretos (OneDrive vs Google Drive)

Funcionalidades:
- Matching inteligente por similaridade
- Análise jurídica automatizada
- Relatórios em CSV e Excel
- Tratamento robusto de erros
- Caminhos flexíveis

Autor: Sistema Final Corrigido
Data: Janeiro 2025
"""

import os
import re
import pandas as pd
from pathlib import Path
from datetime import datetime
import sys

class ConfigFinal:
    """Configurações finais corrigidas"""
    
    # 🔧 CAMINHOS CORRIGIDOS - AJUSTE CONFORME NECESSÁRIO
    # Opção 1: Google Drive (conforme especificado originalmente)
    PRODUTOS_PATH = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\PRODUTOS.xlsx"
    ORCAMENTOS_PATH = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\ORCAMENTOS"

    
    # Opção 2: OneDrive (caso o arquivo esteja lá)
    # PRODUTOS_PATH = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\PRODUTOS.xlsx"
    # ORCAMENTOS_PATH = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\AUTO\ORCAMENTOS"
    
    # Opção 3: Pasta local (mais simples)
    # PRODUTOS_PATH = r"C:\Users\pietr\.vscode\arte_comercial\PRODUTOS.xlsx"
    # ORCAMENTOS_PATH = r"C:\Users\pietr\.vscode\arte_comercial\ORCAMENTOS"
    
    # Parâmetros
    MARGEM_DISPUTA = 0.53  # 53%
    MIN_COMPATIBILIDADE = 75.0
    MAX_SUGESTOES = 5

class ProcessadorFinal:
    """Processador de texto final"""
    
    def normalizar(self, texto):
        """Normalização robusta de texto"""
        if pd.isna(texto) or not texto:
            return ""
        
        texto = str(texto).upper()
        
        # Remover acentos
        acentos = {
            'Á': 'A', 'À': 'A', 'Ã': 'A', 'Â': 'A', 'Ä': 'A',
            'É': 'E', 'È': 'E', 'Ê': 'E', 'Ë': 'E',
            'Í': 'I', 'Ì': 'I', 'Î': 'I', 'Ï': 'I',
            'Ó': 'O', 'Ò': 'O', 'Õ': 'O', 'Ô': 'O', 'Ö': 'O',
            'Ú': 'U', 'Ù': 'U', 'Û': 'U', 'Ü': 'U',
            'Ç': 'C', 'Ñ': 'N'
        }
        
        for k, v in acentos.items():
            texto = texto.replace(k, v)
        
        # Limpar caracteres especiais
        texto = re.sub(r'[^A-Z0-9\s]', ' ', texto)
        texto = re.sub(r'\s+', ' ', texto).strip()
        
        return texto
    
    def extrair_especificacoes(self, texto):
        """Extrai especificações técnicas"""
        specs = []
        texto_norm = self.normalizar(texto)
        
        # Padrões técnicos
        padroes = [
            r'(\d+)\s*(V|VOLTS?|W|WATTS?|A|AMPERES?)',
            r'(\d+)\s*(MM|CM|M|METROS?|POLEGADAS?|POL)',
            r'(\d+)\s*(KG|G|GRAMAS?|QUILOS?|LIBRAS?)',
            r'(\d+)\s*(CORDAS?|TECLAS?|CANAIS?|VOZES?|PADS?)',
            r'(USB|BLUETOOTH|WIFI|MIDI|XLR|P10|RCA|HDMI)',
            r'(LED|LCD|OLED|DISPLAY|TELA)',
            r'(MADEIRA|METAL|PLASTICO|ACO|ALUMINIO|CARBONO)',
            r'(\d+)\s*(HZ|KHZ|MHZ|HERTZ)',
            r'(\d+)\s*(BIT|BITS?|KBPS|MBPS)',
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
        """Calcula similaridade usando múltiplas técnicas"""
        
        # Método 1: Jaccard (base)
        palavras1 = set(self.normalizar(texto1).split())
        palavras2 = set(self.normalizar(texto2).split())
        
        if not palavras1 or not palavras2:
            return 0.0
        
        intersecao = palavras1.intersection(palavras2)
        uniao = palavras1.union(palavras2)
        jaccard = (len(intersecao) / len(uniao)) * 100 if uniao else 0.0
        
        # Método 2: Palavras importantes (peso maior)
        palavras_importantes1 = set(p for p in palavras1 if len(p) > 3)
        palavras_importantes2 = set(p for p in palavras2 if len(p) > 3)
        
        if palavras_importantes1 and palavras_importantes2:
            intersecao_imp = palavras_importantes1.intersection(palavras_importantes2)
            bonus_importantes = (len(intersecao_imp) / len(palavras_importantes1)) * 30
        else:
            bonus_importantes = 0
        
        # Método 3: Sequências comuns
        texto1_norm = self.normalizar(texto1)
        texto2_norm = self.normalizar(texto2)
        
        bonus_sequencias = 0
        palavras_texto1 = texto1_norm.split()
        for i in range(len(palavras_texto1) - 1):
            bigrama = palavras_texto1[i] + " " + palavras_texto1[i + 1]
            if bigrama in texto2_norm:
                bonus_sequencias += 5
        
        # Score final combinado
        score_final = min(jaccard + bonus_importantes + bonus_sequencias, 100.0)
        return score_final

class AnalisadorJuridicoFinal:
    """Análise jurídica robusta"""
    
    @staticmethod
    def analisar(descricao):
        """Análise completa de direcionamento"""
        texto = descricao.upper()
        
        # Padrões críticos de direcionamento
        padroes_criticos = [
            (r'\bMARCA\s+([A-Z][A-Z0-9]*)', 'Especificação de marca específica'),
            (r'\bEXCLUSIVAMENTE\b', 'Uso de termo exclusivo'),
            (r'\bAPENAS\s+([A-Z]+)', 'Limitação a fornecedor específico'),
            (r'\bUNICAMENTE\b', 'Restrição única'),
            (r'\bEXCLUSIVO\b', 'Termo exclusivo'),
            (r'\bSOMENTE\s+([A-Z]+)', 'Limitação restritiva'),
        ]
        
        # Padrões de justificativa técnica
        justificativas = [
            'COMPATIBILIDADE', 'INTEROPERABILIDADE', 'PROTOCOLO',
            'PADRAO', 'NORMA', 'CERTIFICACAO', 'HOMOLOGACAO',
            'INTEGRACAO', 'INTERFACE', 'CONECTIVIDADE'
        ]
        
        direcionamentos_encontrados = []
        for padrao, descricao_padrao in padroes_criticos:
            matches = re.findall(padrao, texto)
            if matches:
                direcionamentos_encontrados.append(descricao_padrao)
        
        tem_justificativa = any(just in texto for just in justificativas)
        
        # Análise de risco
        if direcionamentos_encontrados and not tem_justificativa:
            return {
                'exige_impugnacao': True,
                'risco': 'ALTO',
                'observacao': 'Direcionamento identificado sem justificativa técnica adequada. Recomenda-se impugnação baseada na Lei 14.133/21 (Art. 7º §5º) para garantir isonomia e competitividade no certame.',
                'direcionamentos': direcionamentos_encontrados,
                'acao_recomendada': 'IMPUGNAR'
            }
        elif direcionamentos_encontrados and tem_justificativa:
            return {
                'exige_impugnacao': True,
                'risco': 'MÉDIO',
                'observacao': 'Possível direcionamento com justificativa técnica presente. Recomenda-se análise detalhada para verificar se a justificativa é suficiente e necessária.',
                'direcionamentos': direcionamentos_encontrados,
                'acao_recomendada': 'ANALISAR'
            }
        else:
            return {
                'exige_impugnacao': False,
                'risco': 'BAIXO',
                'observacao': 'Especificação técnica adequada que permite competição entre fornecedores equivalentes.',
                'direcionamentos': [],
                'acao_recomendada': 'PARTICIPAR'
            }

class MatchingFinal:
    """Sistema principal final"""
    
    def __init__(self):
        print("🎯 SISTEMA FINAL DE MATCHING PARA LICITAÇÕES")
        print("=" * 60)
        print("Versão: Final Corrigida | Data: " + datetime.now().strftime('%d/%m/%Y %H:%M'))
        print("=" * 60)
        print("🚀 Inicializando sistema...")
        
        self.processador = ProcessadorFinal()
        self.analisador = AnalisadorJuridicoFinal()
        self.produtos_df = None
        self.resultados = []
    
    def verificar_caminhos(self):
        """Verifica e sugere caminhos alternativos"""
        print("\n🔍 Verificando caminhos...")
        
        # Lista de caminhos possíveis
        caminhos_produtos = [
            ConfigFinal.PRODUTOS_PATH,
            r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\PRODUTOS.xlsx",
            r"C:\Users\pietr\.vscode\arte_comercial\PRODUTOS.xlsx",
            r"C:\Users\pietr\Desktop\ARTE\PRODUTOS.xlsx",
            r"C:\Users\pietr\Documents\ARTE\PRODUTOS.xlsx"
        ]
        
        caminhos_orcamentos = [
            ConfigFinal.ORCAMENTOS_PATH,
            r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\AUTO\ORCAMENTOS",
            r"C:\Users\pietr\.vscode\arte_comercial\ORCAMENTOS",
            r"C:\Users\pietr\Desktop\ARTE\AUTO\ORCAMENTOS",
            r"C:\Users\pietr\Documents\ARTE\AUTO\ORCAMENTOS"
        ]
        
        # Encontrar produtos
        produto_encontrado = None
        for caminho in caminhos_produtos:
            if os.path.exists(caminho):
                produto_encontrado = caminho
                print("✅ Produtos encontrado: " + caminho)
                break
        
        if not produto_encontrado:
            print("❌ Arquivo PRODUTOS.xlsx não encontrado em nenhum local!")
            print("📁 Locais verificados:")
            for caminho in caminhos_produtos:
                print("   - " + caminho)
            return None, None
        
        # Encontrar orçamentos
        orcamento_encontrado = None
        for caminho in caminhos_orcamentos:
            if os.path.exists(caminho):
                orcamento_encontrado = caminho
                print("✅ Orçamentos encontrado: " + caminho)
                break
        
        if not orcamento_encontrado:
            print("❌ Pasta ORCAMENTOS não encontrada em nenhum local!")
            print("📁 Locais verificados:")
            for caminho in caminhos_orcamentos:
                print("   - " + caminho)
            return produto_encontrado, None
        
        return produto_encontrado, orcamento_encontrado
    
    def carregar_dados(self):
        """Carrega dados com verificação robusta"""
        print("\n📂 Carregando dados...")
        
        try:
            # Verificar caminhos
            caminho_produtos, caminho_orcamentos = self.verificar_caminhos()
            
            if not caminho_produtos or not caminho_orcamentos:
                return False
            
            # Carregar produtos
            try:
                self.produtos_df = pd.read_excel(caminho_produtos)
                self.produtos_df.columns = self.produtos_df.columns.str.strip()
                print("✅ " + str(len(self.produtos_df)) + " produtos carregados")
            except PermissionError:
                print("❌ Erro de permissão ao acessar: " + caminho_produtos)
                print("💡 Dica: Feche o arquivo Excel se estiver aberto")
                return False
            except Exception as e:
                print("❌ Erro ao carregar produtos: " + str(e))
                return False
            
            # Listar orçamentos
            try:
                pasta = Path(caminho_orcamentos)
                self.arquivos = list(pasta.glob("*.xlsx"))
                print("✅ " + str(len(self.arquivos)) + " arquivos de orçamento encontrados")
                
                if len(self.arquivos) == 0:
                    print("⚠️ Nenhum arquivo .xlsx encontrado na pasta de orçamentos")
                    # Listar arquivos disponíveis
                    todos_arquivos = list(pasta.glob("*"))
                    if todos_arquivos:
                        print("📄 Arquivos disponíveis:")
                        for arquivo in todos_arquivos[:10]:  # Mostrar apenas os primeiros 10
                            print("   - " + arquivo.name)
                
                return len(self.arquivos) > 0
                
            except Exception as e:
                print("❌ Erro ao acessar pasta de orçamentos: " + str(e))
                return False
            
        except Exception as e:
            print("❌ Erro geral: " + str(e))
            return False
    
    def extrair_valor(self, valor):
        """Extrai valor numérico com tratamento robusto"""
        if pd.isna(valor):
            return 0.0
        
        valor_str = str(valor)
        
        # Remover símbolos de moeda
        valor_str = valor_str.replace('R$', '').replace('$', '').strip()
        
        # Tratar diferentes formatos
        if ',' in valor_str and '.' in valor_str:
            # Formato: 1.234.567,89
            valor_str = valor_str.replace('.', '').replace(',', '.')
        elif ',' in valor_str:
            # Formato: 1234,89
            valor_str = valor_str.replace(',', '.')
        
        try:
            match = re.search(r'[\d\.]+', valor_str)
            return float(match.group()) if match else 0.0
        except:
            return 0.0
    
    def calcular_compatibilidade(self, desc_edital, produto):
        """Calcula compatibilidade avançada"""
        # Preparar texto do produto
        campos_produto = ['MODELO', 'DESCRIÇÃO', 'DESCRICAO', 'DESCRIPTION']
        texto_produto = ""
        
        for campo in campos_produto:
            if campo in produto and pd.notna(produto[campo]):
                texto_produto += " " + str(produto[campo])
        
        if not texto_produto.strip():
            return 0.0, {}
        
        # 1. Similaridade textual base (50%)
        score_base = self.processador.calcular_similaridade(desc_edital, texto_produto)
        
        # 2. Match exato de modelo (35%)
        modelo = str(produto.get('MODELO', ''))
        score_modelo = 0.0
        if modelo and len(modelo) > 2:
            modelo_norm = self.processador.normalizar(modelo)
            edital_norm = self.processador.normalizar(desc_edital)
            
            if modelo_norm in edital_norm:
                score_modelo = 100.0
            elif any(palavra in edital_norm for palavra in modelo_norm.split() if len(palavra) > 2):
                score_modelo = 75.0
        
        # 3. Compatibilidade de especificações (15%)
        specs_edital = self.processador.extrair_especificacoes(desc_edital)
        specs_produto = self.processador.extrair_especificacoes(texto_produto)
        
        score_specs = 0.0
        if specs_edital and specs_produto:
            specs_comuns = set(specs_edital) & set(specs_produto)
            score_specs = (len(specs_comuns) / len(specs_edital)) * 100
        
        # Score final ponderado
        if score_modelo > 0:
            # Se há match de modelo, dar mais peso
            score_final = (score_modelo * 0.6) + (score_base * 0.25) + (score_specs * 0.15)
        else:
            # Sem match de modelo, focar na similaridade textual
            score_final = (score_base * 0.7) + (score_specs * 0.3)
        
        detalhes = {
            'base': round(score_base, 2),
            'modelo': round(score_modelo, 2),
            'specs': round(score_specs, 2),
            'specs_edital': specs_edital,
            'specs_produto': specs_produto,
            'texto_produto': texto_produto.strip()
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
                print("   ❌ Erro ao processar arquivo: " + str(e))
                continue
        
        print("\n✅ Processamento concluído!")
        print("📊 Resumo: " + str(total_items) + " itens analisados, " + str(total_matches) + " matches encontrados")
        return True
    
    def processar_item(self, item, arquivo):
        """Processa um item do edital"""
        # Extrair dados do item
        num_item = item.get('Número do Item', item.get('Item', 'N/A'))
        desc_edital = str(item.get('Item', item.get('Descrição', item.get('DESCRIÇÃO', ''))))
        unidade = item.get('Unidade de Fornecimento', item.get('Unidade', 'UN'))
        qtd = float(item.get('Quantidade Total', item.get('Quantidade', 0)))
        valor_ref = self.extrair_valor(item.get('Valor Unitário (R$)', item.get('Valor', 0)))
        
        if not desc_edital or valor_ref <= 0:
            return 0
        
        # Análise jurídica
        analise = self.analisador.analisar(desc_edital)
        
        # Buscar matches nos produtos
        matches_encontrados = []
        
        for _, produto in self.produtos_df.iterrows():
            score, detalhes = self.calcular_compatibilidade(desc_edital, produto)
            
            if score >= ConfigFinal.MIN_COMPATIBILIDADE:
                # Verificar preço
                campos_valor = ['VALOR', 'Valor', 'PREÇO', 'Preço', 'PRICE']
                valor_produto = 0.0
                
                for campo in campos_valor:
                    if campo in produto:
                        valor_produto = self.extrair_valor(produto[campo])
                        if valor_produto > 0:
                            break
                
                if valor_produto > 0:
                    valor_disputa = valor_produto * (1 + ConfigFinal.MARGEM_DISPUTA)
                    
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
        
        # Adicionar os melhores matches
        for match in matches_encontrados[:ConfigFinal.MAX_SUGESTOES]:
            self.adicionar_resultado(num_item, desc_edital, unidade, qtd, valor_ref, match, analise, arquivo)
        
        return len(matches_encontrados[:ConfigFinal.MAX_SUGESTOES])
    
    def adicionar_resultado(self, num_item, desc_edital, unidade, qtd, valor_ref, match, analise, arquivo):
        """Adiciona resultado à lista"""
        produto = match['produto']
        score = match['score']
        detalhes = match['detalhes']
        valor_produto = match['valor_produto']
        valor_disputa = match['valor_disputa']
        
        # Descrição técnica detalhada
        comparacao = "Score: " + str(round(score, 1)) + "%"
        
        if detalhes['modelo'] > 0:
            comparacao += " | Modelo: " + str(round(detalhes['modelo'], 1)) + "%"
        
        if detalhes['specs_edital']:
            comparacao += " | Specs: " + ', '.join(detalhes['specs_edital'][:3])
        
        # Avaliação de substituição
        if score >= 95:
            pode_substituir = "Excelente"
            confiabilidade = "Alta"
        elif score >= 85:
            pode_substituir = "Sim"
            confiabilidade = "Boa"
        elif score >= 75:
            pode_substituir = "Parcialmente"
            confiabilidade = "Média"
        else:
            pode_substituir = "Limitado"
            confiabilidade = "Baixa"
        
        # Economia estimada
        economia_unitaria = max(0, valor_ref - valor_disputa)
        economia_total = economia_unitaria * qtd
        
        resultado = {
            'Arquivo': arquivo,
            'Item': num_item,
            'Descrição Edital': desc_edital,
            'Unidade': unidade,
            'Quantidade': qtd,
            'Valor Ref. Unitário': valor_ref,
            'Valor Ref. Total': valor_ref * qtd,
            'Marca sugerida': produto.get('MARCA', produto.get('Marca', 'N/A')),
            'Produto Sugerido': produto.get('MODELO', produto.get('Modelo', 'N/A')),
            'Descrição Produto': detalhes['texto_produto'][:100] + "..." if len(detalhes['texto_produto']) > 100 else detalhes['texto_produto'],
            'Link/Código': str(produto.get('MARCA', 'N/A')) + "_" + str(produto.get('MODELO', 'N/A')),
            'Preço Fornecedor': valor_produto,
            'Preço com Margem 53%': valor_disputa,
            'Economia Unitária': economia_unitaria,
            'Economia Total': economia_total,
            'Comparação Técnica': comparacao,
            '% Compatibilidade': round(score, 2),
            'Confiabilidade': confiabilidade,
            'Pode Substituir?': pode_substituir,
            'Exige Impugnação?': 'Sim' if analise['exige_impugnacao'] else 'Não',
            'Risco Jurídico': analise['risco'],
            'Ação Recomendada': analise['acao_recomendada'],
            'Observação Jurídica': analise['observacao'],
            'Fornecedor': produto.get('FORNECEDOR', produto.get('Fornecedor', 'N/A'))
        }
        
        self.resultados.append(resultado)
    
    def gerar_relatorios(self):
        """Gera relatórios completos"""
        if not self.resultados:
            print("❌ Nenhum resultado para gerar relatórios")
            return False
        
        print("\n📊 Gerando relatórios...")
        
        df_final = pd.DataFrame(self.resultados)
        
        # Estatísticas
        total_items = df_final['Item'].nunique()
        matches_excelentes = len(df_final[df_final['% Compatibilidade'] >= 95])
        matches_bons = len(df_final[df_final['% Compatibilidade'] >= 85])
        economia_total = df_final['Economia Total'].sum()
        
        # Determinar pasta de saída
        if hasattr(self, 'arquivos') and self.arquivos:
            pasta_saida = self.arquivos[0].parent
        else:
            pasta_saida = Path(ConfigFinal.ORCAMENTOS_PATH)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        try:
            # 1. CSV Principal (sobrescrever)
            arquivo_csv = pasta_saida / "RESULTADO_MATCHING_INTELIGENTE.csv"
            df_final.to_csv(arquivo_csv, index=False, encoding='utf-8-sig')
            
            # 2. Excel Principal (sobrescrever)
            arquivo_excel = pasta_saida / "RELATORIO_MATCHING_COMPLETO.xlsx"
            df_final.to_excel(arquivo_excel, index=False)
            
            # 3. Arquivo com timestamp
            arquivo_timestamp = pasta_saida / ("MATCHING_FINAL_" + timestamp + ".csv")
            df_final.to_csv(arquivo_timestamp, index=False, encoding='utf-8-sig')
            
            # 4. Resumo executivo
            resumo = """# 📊 RELATÓRIO EXECUTIVO DE MATCHING

**Data**: """ + datetime.now().strftime('%d/%m/%Y %H:%M') + """
**Sistema**: Matching Final Corrigido
**Versão**: 1.0

## 📈 ESTATÍSTICAS GERAIS

- **Itens Analisados**: """ + str(total_items) + """
- **Matches Encontrados**: """ + str(len(df_final)) + """
- **Matches Excelentes (≥95%)**: """ + str(matches_excelentes) + """
- **Matches Bons (≥85%)**: """ + str(matches_bons) + """
- **Economia Total Estimada**: R$ """ + "{:,.2f}".format(economia_total) + """

## 🏆 TOP 10 MELHORES MATCHES

""" + df_final.nlargest(10, '% Compatibilidade')[['Item', 'Produto Sugerido', '% Compatibilidade', 'Economia Total']].to_string(index=False) + """

## ⚖️ ANÁLISE JURÍDICA

- **Risco Alto**: """ + str(len(df_final[df_final['Risco Jurídico'] == 'ALTO'])) + """ itens
- **Risco Médio**: """ + str(len(df_final[df_final['Risco Jurídico'] == 'MÉDIO'])) + """ itens  
- **Risco Baixo**: """ + str(len(df_final[df_final['Risco Jurídico'] == 'BAIXO'])) + """ itens

## 💡 RECOMENDAÇÕES

1. **Priorizar matches com compatibilidade ≥ 90%**
2. **Analisar itens de risco médio/alto antes da participação**
3. **Considerar impugnação para itens com direcionamento**
4. **Focar em itens com maior economia estimada**

---
*Relatório gerado automaticamente pelo Sistema Final de Matching*
"""
            
            arquivo_resumo = pasta_saida / ("RESUMO_EXECUTIVO_" + timestamp + ".md")
            with open(arquivo_resumo, 'w', encoding='utf-8') as f:
                f.write(resumo)
            
            print("✅ Relatórios gerados com sucesso!")
            print("📁 Pasta de saída: " + str(pasta_saida))
            print("📄 Arquivos gerados:")
            print("   • RESULTADO_MATCHING_INTELIGENTE.csv (principal)")
            print("   • RELATORIO_MATCHING_COMPLETO.xlsx (principal)")
            print("   • " + arquivo_timestamp.name + " (backup)")
            print("   • " + arquivo_resumo.name + " (resumo)")
            print("\n💰 Economia total estimada: R$ " + "{:,.2f}".format(economia_total))
            print("🎯 Taxa de sucesso: " + str(round((len(df_final) / total_items) * 100, 1)) + "%")
            
            return True
            
        except Exception as e:
            print("❌ Erro ao gerar relatórios: " + str(e))
            return False

def main():
    """Função principal"""
    try:
        # Executar sistema
        matcher = MatchingFinal()
        
        if matcher.processar_tudo():
            if matcher.gerar_relatorios():
                print("\n🎉 PROCESSO CONCLUÍDO COM SUCESSO!")
                print("📁 Verifique os arquivos gerados na pasta de orçamentos")
                print("✨ Sistema funcionando perfeitamente!")
            else:
                print("\n⚠️ Processamento concluído, mas houve erro na geração de relatórios")
        else:
            print("\n❌ Erro no processamento dos dados")
            print("💡 Verifique os caminhos dos arquivos e tente novamente")
    
    except KeyboardInterrupt:
        print("\n⏹️ Processo interrompido pelo usuário")
    except Exception as e:
        print("\n💥 Erro inesperado: " + str(e))
        print("📞 Contate o suporte técnico se o problema persistir")

if __name__ == "__main__":
    main()

