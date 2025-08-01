# mvp_licitacao.py - Versão rápida para produção imediata
import re
import pandas as pd
from pathlib import Path
import PyPDF2

class ProcessadorLicitacaoMVP:
    def __init__(self):
        self.padroes = {
            'item': r'(\d+)\s*[-–]\s*([^0-9]+?)(?=\d+\s*[-–]|$)',
            'quantidade': r'(?:quantidade|qtd)[:.]?\s*(\d+)',
            'valor': r'r?\$?\s*(\d+(?:\.\d+)?(?:,\d{2})?)',
            'instrumento': r'(tambor|flauta|piano|guitarra|violão|bateria|pandeiro|triângulo)',
            'material': r'(madeira|metal|plástico|alumínio|aço|bronze)',
        }
    
    def extrair_texto_pdf(self, caminho_pdf):
        """Extrai texto de PDF de forma robusta"""
        try:
            with open(caminho_pdf, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                texto = ""
                for page in reader.pages:
                    texto += page.extract_text() + "\n"
                return texto
        except Exception as e:
            print(f"Erro ao ler PDF {caminho_pdf}: {e}")
            return ""
    
    def processar_edital(self, caminho_pdf):
        """Processa edital e extrai itens estruturados"""
        texto = self.extrair_texto_pdf(caminho_pdf)
        itens = []
        
        # Encontrar todos os itens
        matches_itens = re.finditer(self.padroes['item'], texto, re.MULTILINE | re.DOTALL)
        
        for match in matches_itens:
            numero = int(match.group(1))
            descricao = match.group(2).strip()
            
            # Extrair detalhes do item
            item = {
                'numero': numero,
                'descricao': descricao,
                'quantidade': self._extrair_quantidade(descricao),
                'valor_unitario': self._extrair_valor(descricao),
                'tipo_instrumento': self._extrair_instrumento(descricao),
                'material': self._extrair_material(descricao),
            }
            
            itens.append(item)
        
        return itens
    
    def _extrair_quantidade(self, texto):
        match = re.search(self.padroes['quantidade'], texto, re.IGNORECASE)
        return int(match.group(1)) if match else 1
    
    def _extrair_valor(self, texto):
        match = re.search(self.padroes['valor'], texto, re.IGNORECASE)
        if match:
            valor_str = match.group(1).replace('.', '').replace(',', '.')
            return float(valor_str)
        return 0.0
    
    def _extrair_instrumento(self, texto):
        match = re.search(self.padroes['instrumento'], texto, re.IGNORECASE)
        return match.group(1).lower() if match else 'indefinido'
    
    def _extrair_material(self, texto):
        match = re.search(self.padroes['material'], texto, re.IGNORECASE)
        return match.group(1).lower() if match else None

# Uso imediato
def processar_licitacao_rapido(edital_pdf, base_produtos_excel):
    """Função para usar HOJE mesmo"""
    
    # 1. Extrair dados do edital
    processador = ProcessadorLicitacaoMVP()
    itens_edital = processador.processar_edital(edital_pdf)
    
    # 2. Carregar base de produtos
    base_produtos = pd.read_excel(base_produtos_excel)
    
    # 3. Fazer matching básico mas eficaz
    resultados = []
    
    for item in itens_edital:
        # Buscar produtos compatíveis
        produtos_compativeis = base_produtos[
            base_produtos['Descrição'].str.contains(
                item['tipo_instrumento'], 
                case=False, 
                na=False
            )
        ]
        
        if not produtos_compativeis.empty:
            melhor_produto = produtos_compativeis.iloc[0]
            
            resultado = {
                'Item_Edital': item['numero'],
                'Descricao_Edital': item['descricao'],
                'Produto_Sugerido': melhor_produto['Item'],
                'Marca': melhor_produto['Marca'],
                'Preco_Produto': melhor_produto['Valor'],
                'Compatibilidade': 'Alta' if item['tipo_instrumento'] in melhor_produto['Descrição'].lower() else 'Média',
                'Observacao': f"Match por tipo: {item['tipo_instrumento']}"
            }
        else:
            resultado = {
                'Item_Edital': item['numero'],
                'Descricao_Edital': item['descricao'],
                'Produto_Sugerido': 'Não encontrado',
                'Marca': 'N/A',
                'Preco_Produto': 0,
                'Compatibilidade': 'Nenhuma',
                'Observacao': f"Nenhum produto encontrado para: {item['tipo_instrumento']}"
            }
        
        resultados.append(resultado)
    
    return pd.DataFrame(resultados)