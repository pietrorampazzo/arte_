"""
IMPLEMENTAÇÃO URGENTE - MVP para Licitações
==========================================

Sistema para processar PDFs de editais e fazer matching com base de produtos
Baseado na estratégia do Google Notebooks, otimizado para seu hardware i5 + 16GB

PARA USAR HOJE MESMO:
1. pip install PyPDF2 pandas openpyxl
2. Ajuste os caminhos dos arquivos
3. Execute: python implementacao_urgente_mvp.py
"""

import PyPDF2
import pandas as pd
import re
from pathlib import Path
import json
from typing import List, Dict, Optional
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')

@dataclass
class ItemEditalExtraido:
    """Estrutura para item extraído do edital"""
    numero: int
    descricao_completa: str
    quantidade: int
    valor_unitario: float
    tipo_instrumento: str
    material: Optional[str]
    dimensoes: Optional[str]
    palavras_chave: List[str]

class ProcessadorLicitacaoUrgente:
    """
    Processador MVP para licitações - Implementação urgente
    Baseado na estratégia modular do Google Notebooks
    """
    
    def __init__(self):
        # Padrões regex otimizados para licitações de instrumentos musicais
        self.padroes = {
            # Padrão para identificar itens numerados
            'item_completo': r'(\d+)\s*[-–]\s*([^0-9]+?)(?=\d+\s*[-–]|$)',
            
            # Padrões para extrair informações específicas
            'quantidade': r'(?:quantidade|qtd|quant)[:.]?\s*(\d+(?:\.\d+)?)',
            'valor_unitario': r'(?:valor|preço)\s*(?:unitário|unit)[:.]?\s*r?\$?\s*(\d+(?:\.\d+)?(?:,\d{2})?)',
            'valor_total': r'(?:valor|preço)\s*(?:total|ref)[:.]?\s*r?\$?\s*(\d+(?:\.\d+)?(?:,\d{2})?)',
            
            # Instrumentos musicais específicos
            'instrumentos': r'\b(tambor|flauta|piano|guitarra|violão|bateria|pandeiro|triângulo|agogo|tamborim|zabumba|caixa|surdo|prato|clarinete|saxofone|trompete|trombone|amplificador|microfone|mesa|mixer|caixa\s+som)\b',
            
            # Materiais comuns
            'materiais': r'\b(madeira|metal|plástico|alumínio|aço|bronze|resina|couro|pele|nylon)\b',
            
            # Dimensões
            'dimensoes': r'(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*(?:[x×]\s*(\d+(?:\.\d+)?))?\s*(cm|mm|m|pol|polegadas?)',
            
            # Características técnicas
            'caracteristicas': r'(?:características?|componentes?)[:.]?\s*([^,.]+)',
        }
        
        # Dicionário de sinônimos para melhorar matching
        self.sinonimos = {
            'tambor': ['tambor', 'drum', 'percussão'],
            'flauta': ['flauta', 'flute', 'sopro'],
            'piano': ['piano', 'teclado', 'keyboard'],
            'guitarra': ['guitarra', 'guitar', 'violão'],
            'bateria': ['bateria', 'drums', 'kit'],
            'amplificador': ['amplificador', 'amp', 'amplifier'],
            'microfone': ['microfone', 'mic', 'microphone'],
        }
    
    def extrair_texto_pdf(self, caminho_pdf: str) -> str:
        """
        Extrai texto de PDF de forma robusta
        Trata erros comuns e diferentes encodings
        """
        try:
            with open(caminho_pdf, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                texto_completo = ""
                
                for i, page in enumerate(reader.pages):
                    try:
                        texto_pagina = page.extract_text()
                        if texto_pagina.strip():  # Só adiciona se não estiver vazio
                            texto_completo += f"\n--- PÁGINA {i+1} ---\n"
                            texto_completo += texto_pagina + "\n"
                    except Exception as e:
                        print(f"⚠️  Erro na página {i+1}: {e}")
                        continue
                
                return texto_completo
                
        except Exception as e:
            print(f"❌ Erro ao ler PDF {caminho_pdf}: {e}")
            return ""
    
    def normalizar_texto(self, texto: str) -> str:
        """Normaliza texto para melhor processamento"""
        # Remove quebras de linha excessivas
        texto = re.sub(r'\n+', ' ', texto)
        
        # Remove espaços múltiplos
        texto = re.sub(r'\s+', ' ', texto)
        
        # Remove caracteres especiais problemáticos
        texto = re.sub(r'[^\w\s\-–.,():/]', ' ', texto)
        
        return texto.strip()
    
    def extrair_itens_edital(self, texto_edital: str) -> List[ItemEditalExtraido]:
        """
        Extrai itens estruturados do texto do edital
        Implementa a estratégia de Information Extraction do Google Notebooks
        """
        texto_normalizado = self.normalizar_texto(texto_edital)
        itens_extraidos = []
        
        # Encontrar todos os itens numerados
        matches_itens = re.finditer(self.padroes['item_completo'], texto_normalizado, re.MULTILINE | re.DOTALL)
        
        for match in matches_itens:
            try:
                numero = int(match.group(1))
                descricao = match.group(2).strip()
                
                # Extrair informações específicas da descrição
                item = ItemEditalExtraido(
                    numero=numero,
                    descricao_completa=descricao,
                    quantidade=self._extrair_quantidade(descricao),
                    valor_unitario=self._extrair_valor_unitario(descricao),
                    tipo_instrumento=self._extrair_tipo_instrumento(descricao),
                    material=self._extrair_material(descricao),
                    dimensoes=self._extrair_dimensoes(descricao),
                    palavras_chave=self._extrair_palavras_chave(descricao)
                )
                
                itens_extraidos.append(item)
                
            except Exception as e:
                print(f"⚠️  Erro ao processar item {match.group(1)}: {e}")
                continue
        
        print(f"✅ Extraídos {len(itens_extraidos)} itens do edital")
        return itens_extraidos
    
    def _extrair_quantidade(self, texto: str) -> int:
        """Extrai quantidade do texto"""
        match = re.search(self.padroes['quantidade'], texto, re.IGNORECASE)
        if match:
            try:
                return int(float(match.group(1)))
            except:
                pass
        return 1  # Default
    
    def _extrair_valor_unitario(self, texto: str) -> float:
        """Extrai valor unitário do texto"""
        # Tentar valor unitário primeiro
        match = re.search(self.padroes['valor_unitario'], texto, re.IGNORECASE)
        if not match:
            # Se não encontrar, tentar valor total
            match = re.search(self.padroes['valor_total'], texto, re.IGNORECASE)
        
        if match:
            try:
                valor_str = match.group(1).replace('.', '').replace(',', '.')
                return float(valor_str)
            except:
                pass
        return 0.0
    
    def _extrair_tipo_instrumento(self, texto: str) -> str:
        """Extrai tipo de instrumento do texto"""
        matches = re.findall(self.padroes['instrumentos'], texto, re.IGNORECASE)
        if matches:
            # Retorna o primeiro instrumento encontrado
            return matches[0].lower()
        return 'indefinido'
    
    def _extrair_material(self, texto: str) -> Optional[str]:
        """Extrai material do texto"""
        matches = re.findall(self.padroes['materiais'], texto, re.IGNORECASE)
        if matches:
            return ', '.join(set(match.lower() for match in matches))
        return None
    
    def _extrair_dimensoes(self, texto: str) -> Optional[str]:
        """Extrai dimensões do texto"""
        match = re.search(self.padroes['dimensoes'], texto, re.IGNORECASE)
        if match:
            dimensoes = [match.group(1), match.group(2)]
            if match.group(3):
                dimensoes.append(match.group(3))
            unidade = match.group(4)
            return f"{' x '.join(dimensoes)} {unidade}"
        return None
    
    def _extrair_palavras_chave(self, texto: str) -> List[str]:
        """Extrai palavras-chave relevantes do texto"""
        palavras = []
        
        # Instrumentos
        instrumentos = re.findall(self.padroes['instrumentos'], texto, re.IGNORECASE)
        palavras.extend([inst.lower() for inst in instrumentos])
        
        # Materiais
        materiais = re.findall(self.padroes['materiais'], texto, re.IGNORECASE)
        palavras.extend([mat.lower() for mat in materiais])
        
        # Características específicas
        caracteristicas = re.findall(self.padroes['caracteristicas'], texto, re.IGNORECASE)
        for carac in caracteristicas:
            # Extrair palavras importantes da característica
            palavras_carac = re.findall(r'\b\w{4,}\b', carac.lower())
            palavras.extend(palavras_carac[:3])  # Máximo 3 palavras por característica
        
        return list(set(palavras))  # Remove duplicatas
    
    def fazer_matching_inteligente(self, itens_edital: List[ItemEditalExtraido], 
                                 base_produtos: pd.DataFrame) -> pd.DataFrame:
        """
        Faz matching inteligente entre itens do edital e produtos da base
        Implementa múltiplas estratégias de matching
        """
        resultados = []
        
        for item in itens_edital:
            print(f"🔍 Processando item {item.numero}: {item.tipo_instrumento}")
            
            # Estratégia 1: Match direto por tipo de instrumento
            candidatos = self._buscar_por_tipo_instrumento(item, base_produtos)
            
            # Estratégia 2: Match por palavras-chave se não encontrou
            if candidatos.empty:
                candidatos = self._buscar_por_palavras_chave(item, base_produtos)
            
            # Estratégia 3: Match por similaridade textual se ainda não encontrou
            if candidatos.empty:
                candidatos = self._buscar_por_similaridade(item, base_produtos)
            
            # Selecionar melhor candidato
            if not candidatos.empty:
                melhor_produto = self._selecionar_melhor_produto(item, candidatos)
                
                resultado = {
                    'Numero_Item': item.numero,
                    'Descricao_Edital': item.descricao_completa[:100] + '...' if len(item.descricao_completa) > 100 else item.descricao_completa,
                    'Tipo_Instrumento': item.tipo_instrumento,
                    'Quantidade': item.quantidade,
                    'Valor_Unitario_Edital': item.valor_unitario,
                    'Produto_Sugerido': melhor_produto['Item'],
                    'Marca': melhor_produto['Marca'],
                    'Descricao_Produto': melhor_produto['Descrição'][:100] + '...' if len(str(melhor_produto['Descrição'])) > 100 else melhor_produto['Descrição'],
                    'Preco_Produto': melhor_produto['Valor'],
                    'Estado_Fornecedor': melhor_produto.get('Estado', 'N/A'),
                    'Score_Compatibilidade': self._calcular_score_compatibilidade(item, melhor_produto),
                    'Estrategia_Match': self._identificar_estrategia_usada(item, melhor_produto),
                    'Economia_Estimada': max(0, (item.valor_unitario * item.quantidade) - (melhor_produto['Valor'] * 1.5 * item.quantidade)),
                    'Observacoes': self._gerar_observacoes(item, melhor_produto)
                }
            else:
                resultado = {
                    'Numero_Item': item.numero,
                    'Descricao_Edital': item.descricao_completa[:100] + '...' if len(item.descricao_completa) > 100 else item.descricao_completa,
                    'Tipo_Instrumento': item.tipo_instrumento,
                    'Quantidade': item.quantidade,
                    'Valor_Unitario_Edital': item.valor_unitario,
                    'Produto_Sugerido': 'NÃO ENCONTRADO',
                    'Marca': 'N/A',
                    'Descricao_Produto': 'Nenhum produto compatível encontrado',
                    'Preco_Produto': 0,
                    'Estado_Fornecedor': 'N/A',
                    'Score_Compatibilidade': 0,
                    'Estrategia_Match': 'NENHUMA',
                    'Economia_Estimada': 0,
                    'Observacoes': f'Busca realizada por: {item.tipo_instrumento}, palavras-chave: {", ".join(item.palavras_chave[:3])}'
                }
            
            resultados.append(resultado)
        
        return pd.DataFrame(resultados)
    
    def _buscar_por_tipo_instrumento(self, item: ItemEditalExtraido, base: pd.DataFrame) -> pd.DataFrame:
        """Busca produtos por tipo de instrumento"""
        if item.tipo_instrumento == 'indefinido':
            return pd.DataFrame()
        
        # Buscar por tipo exato
        mask = base['Descrição'].str.contains(item.tipo_instrumento, case=False, na=False)
        
        # Buscar por sinônimos se não encontrou
        if not mask.any() and item.tipo_instrumento in self.sinonimos:
            for sinonimo in self.sinonimos[item.tipo_instrumento]:
                mask_sinonimo = base['Descrição'].str.contains(sinonimo, case=False, na=False)
                mask = mask | mask_sinonimo
        
        return base[mask]
    
    def _buscar_por_palavras_chave(self, item: ItemEditalExtraido, base: pd.DataFrame) -> pd.DataFrame:
        """Busca produtos por palavras-chave"""
        if not item.palavras_chave:
            return pd.DataFrame()
        
        mask = pd.Series([False] * len(base))
        
        for palavra in item.palavras_chave:
            if len(palavra) >= 4:  # Só palavras com 4+ caracteres
                mask_palavra = base['Descrição'].str.contains(palavra, case=False, na=False)
                mask = mask | mask_palavra
        
        return base[mask]
    
    def _buscar_por_similaridade(self, item: ItemEditalExtraido, base: pd.DataFrame) -> pd.DataFrame:
        """Busca produtos por similaridade textual básica"""
        # Implementação simples de similaridade
        palavras_item = set(re.findall(r'\b\w{4,}\b', item.descricao_completa.lower()))
        
        scores = []
        for _, produto in base.iterrows():
            palavras_produto = set(re.findall(r'\b\w{4,}\b', str(produto['Descrição']).lower()))
            
            if palavras_item and palavras_produto:
                intersecao = palavras_item.intersection(palavras_produto)
                uniao = palavras_item.union(palavras_produto)
                score = len(intersecao) / len(uniao) if uniao else 0
            else:
                score = 0
            
            scores.append(score)
        
        # Retornar produtos com score > 0.1
        base_com_score = base.copy()
        base_com_score['score_similaridade'] = scores
        
        return base_com_score[base_com_score['score_similaridade'] > 0.1]
    
    def _selecionar_melhor_produto(self, item: ItemEditalExtraido, candidatos: pd.DataFrame) -> pd.Series:
        """Seleciona o melhor produto entre os candidatos"""
        if len(candidatos) == 1:
            return candidatos.iloc[0]
        
        # Critérios de seleção (em ordem de prioridade):
        # 1. Menor preço
        # 2. Marca conhecida
        # 3. Primeiro encontrado
        
        candidatos_ordenados = candidatos.sort_values('Valor', ascending=True)
        return candidatos_ordenados.iloc[0]
    
    def _calcular_score_compatibilidade(self, item: ItemEditalExtraido, produto: pd.Series) -> float:
        """Calcula score de compatibilidade (0-100)"""
        score = 0
        
        # Tipo de instrumento (40 pontos)
        if item.tipo_instrumento != 'indefinido':
            if item.tipo_instrumento.lower() in str(produto['Descrição']).lower():
                score += 40
        
        # Palavras-chave (30 pontos)
        palavras_produto = str(produto['Descrição']).lower()
        palavras_encontradas = sum(1 for palavra in item.palavras_chave if palavra in palavras_produto)
        if item.palavras_chave:
            score += (palavras_encontradas / len(item.palavras_chave)) * 30
        
        # Material (20 pontos)
        if item.material:
            if item.material.lower() in palavras_produto:
                score += 20
        
        # Preço razoável (10 pontos)
        if item.valor_unitario > 0 and produto['Valor'] > 0:
            ratio = produto['Valor'] / item.valor_unitario
            if 0.5 <= ratio <= 2.0:  # Preço dentro de uma faixa razoável
                score += 10
        
        return round(score, 1)
    
    def _identificar_estrategia_usada(self, item: ItemEditalExtraido, produto: pd.Series) -> str:
        """Identifica qual estratégia de matching foi usada"""
        descricao_produto = str(produto['Descrição']).lower()
        
        if item.tipo_instrumento != 'indefinido' and item.tipo_instrumento in descricao_produto:
            return 'TIPO_INSTRUMENTO'
        
        for palavra in item.palavras_chave:
            if palavra in descricao_produto:
                return 'PALAVRAS_CHAVE'
        
        return 'SIMILARIDADE_TEXTUAL'
    
    def _gerar_observacoes(self, item: ItemEditalExtraido, produto: pd.Series) -> str:
        """Gera observações sobre o matching"""
        observacoes = []
        
        # Compatibilidade de tipo
        if item.tipo_instrumento != 'indefinido':
            if item.tipo_instrumento.lower() in str(produto['Descrição']).lower():
                observacoes.append(f"Tipo compatível: {item.tipo_instrumento}")
            else:
                observacoes.append(f"Tipo diferente (edital: {item.tipo_instrumento})")
        
        # Material
        if item.material:
            observacoes.append(f"Material edital: {item.material}")
        
        # Dimensões
        if item.dimensoes:
            observacoes.append(f"Dimensões edital: {item.dimensoes}")
        
        # Análise de preço
        if item.valor_unitario > 0 and produto['Valor'] > 0:
            diferenca_percentual = ((produto['Valor'] - item.valor_unitario) / item.valor_unitario) * 100
            if diferenca_percentual > 0:
                observacoes.append(f"Produto {diferenca_percentual:.1f}% mais caro")
            else:
                observacoes.append(f"Produto {abs(diferenca_percentual):.1f}% mais barato")
        
        return " | ".join(observacoes) if observacoes else "Sem observações específicas"

def processar_licitacao_urgente(caminho_edital_pdf: str, 
                              caminho_base_excel: str, 
                              caminho_saida_excel: str) -> pd.DataFrame:
    """
    FUNÇÃO PRINCIPAL - USE ESTA PARA PROCESSAR HOJE MESMO
    
    Args:
        caminho_edital_pdf: Caminho para o PDF do edital
        caminho_base_excel: Caminho para o Excel com base de produtos
        caminho_saida_excel: Caminho onde salvar o resultado
    
    Returns:
        DataFrame com os resultados do matching
    """
    
    print("🚀 INICIANDO PROCESSAMENTO URGENTE DE LICITAÇÃO")
    print("=" * 60)
    
    # Inicializar processador
    processador = ProcessadorLicitacaoUrgente()
    
    # 1. Extrair texto do edital
    print("📄 Extraindo texto do edital...")
    texto_edital = processador.extrair_texto_pdf(caminho_edital_pdf)
    
    if not texto_edital.strip():
        print("❌ Erro: Não foi possível extrair texto do PDF")
        return pd.DataFrame()
    
    print(f"✅ Texto extraído: {len(texto_edital)} caracteres")
    
    # 2. Extrair itens estruturados
    print("\n🔍 Extraindo itens do edital...")
    itens_edital = processador.extrair_itens_edital(texto_edital)
    
    if not itens_edital:
        print("❌ Erro: Nenhum item encontrado no edital")
        return pd.DataFrame()
    
    # 3. Carregar base de produtos
    print(f"\n📊 Carregando base de produtos...")
    try:
        base_produtos = pd.read_excel(caminho_base_excel)
        print(f"✅ Base carregada: {len(base_produtos)} produtos")
    except Exception as e:
        print(f"❌ Erro ao carregar base de produtos: {e}")
        return pd.DataFrame()
    
    # 4. Fazer matching
    print(f"\n🎯 Fazendo matching inteligente...")
    resultado = processador.fazer_matching_inteligente(itens_edital, base_produtos)
    
    # 5. Salvar resultado
    print(f"\n💾 Salvando resultado...")
    try:
        resultado.to_excel(caminho_saida_excel, index=False)
        print(f"✅ Resultado salvo em: {caminho_saida_excel}")
    except Exception as e:
        print(f"❌ Erro ao salvar resultado: {e}")
    
    # 6. Mostrar resumo
    print(f"\n📊 RESUMO DOS RESULTADOS:")
    print("=" * 60)
    
    total_itens = len(resultado)
    matches_encontrados = len(resultado[resultado['Produto_Sugerido'] != 'NÃO ENCONTRADO'])
    economia_total = resultado['Economia_Estimada'].sum()
    
    print(f"📋 Total de itens processados: {total_itens}")
    print(f"✅ Matches encontrados: {matches_encontrados}")
    print(f"📈 Taxa de sucesso: {(matches_encontrados/total_itens)*100:.1f}%")
    print(f"💰 Economia total estimada: R$ {economia_total:,.2f}")
    
    # Mostrar alguns matches encontrados
    matches = resultado[resultado['Produto_Sugerido'] != 'NÃO ENCONTRADO']
    if not matches.empty:
        print(f"\n🎯 MELHORES MATCHES:")
        for _, row in matches.head(3).iterrows():
            print(f"   Item {row['Numero_Item']}: {row['Tipo_Instrumento']} → {row['Produto_Sugerido']} ({row['Marca']})")
            print(f"      Score: {row['Score_Compatibilidade']}% | Estratégia: {row['Estrategia_Match']}")
    
    print("\n" + "=" * 60)
    print("🎉 PROCESSAMENTO CONCLUÍDO COM SUCESSO!")
    
    return resultado

# EXEMPLO DE USO IMEDIATO
if __name__ == "__main__":
    print("SISTEMA MVP DE MATCHING PARA LICITAÇÕES")
    print("Baseado na estratégia do Google Notebooks")
    print("Otimizado para i5 + 16GB RAM")
    print()
    
    # AJUSTE ESTES CAMINHOS PARA SEUS ARQUIVOS
    edital_pdf = "edital_exemplo.pdf"  # ← COLOQUE O CAMINHO DO SEU EDITAL
    base_excel = "data_base.xlsx"      # ← COLOQUE O CAMINHO DA SUA BASE
    saida_excel = "resultado_urgente.xlsx"  # ← ONDE SALVAR O RESULTADO
    
    # VERIFICAR SE OS ARQUIVOS EXISTEM
    if not Path(edital_pdf).exists():
        print(f"❌ Arquivo não encontrado: {edital_pdf}")
        print("   Ajuste o caminho na variável 'edital_pdf'")
    elif not Path(base_excel).exists():
        print(f"❌ Arquivo não encontrado: {base_excel}")
        print("   Ajuste o caminho na variável 'base_excel'")
    else:
        # PROCESSAR
        resultado = processar_licitacao_urgente(edital_pdf, base_excel, saida_excel)
        
        if not resultado.empty:
            print(f"\n✅ Sucesso! Verifique o arquivo: {saida_excel}")
        else:
            print(f"\n❌ Erro no processamento. Verifique os arquivos de entrada.")

