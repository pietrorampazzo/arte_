import os
import fitz  # PyMuPDF
import re
import pandas as pd

# Diretórios locais
input_dir = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\TESTE"
output_dir = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\ORCAMENTOS"

def extract_items_from_text(text):
    items = []
    
    # Limpar texto removendo quebras de linha desnecessárias
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r'\s+', ' ', text)
    
    # Pattern mais robusto para identificar o início de cada item
    item_pattern = re.compile(r'(\d+)\s*-\s*([^0-9]+?)(?=Descrição Detalhada:)', re.DOTALL | re.IGNORECASE)
    
    # Encontrar todos os blocos de itens
    item_matches = list(item_pattern.finditer(text))
    
    for i, match in enumerate(item_matches):
        item_num = match.group(1).strip()
        item_nome = match.group(2).strip()
        
        # Determinar o texto do item atual
        start_pos = match.start()
        if i + 1 < len(item_matches):
            end_pos = item_matches[i + 1].start()
        else:
            end_pos = len(text)
        
        item_text = text[start_pos:end_pos]
        
        # Extrair descrição detalhada
        descricao_match = re.search(r'Descrição Detalhada:\s*(.*?)(?=Tratamento Diferenciado:|Aplicabilidade Decreto|$)', 
                                  item_text, re.DOTALL | re.IGNORECASE)
        descricao = ""
        if descricao_match:
            descricao = descricao_match.group(1).strip()
            # Limpar a descrição
            descricao = re.sub(r'\s+', ' ', descricao)
            descricao = re.sub(r'[^\w\s:,.()/-]', '', descricao)
        
        # Construir item completo
        item_completo = f"{item_num} - {item_nome}"
        if descricao:
            item_completo += f" {descricao}"
        
        # Extrair quantidade total
        quantidade_match = re.search(r'Quantidade Total:\s*(\d+)', item_text, re.IGNORECASE)
        quantidade = quantidade_match.group(1) if quantidade_match else ""
        
        # Extrair valor unitário - procurar por diferentes padrões
        valor_patterns = [
            r'Valor Unitário[^:]*:\s*R?\$?\s*([\d.,]+)',
            r'Valor Total[^:]*:\s*R?\$?\s*([\d.,]+)',
            r'R\$\s*([\d.,]+)'
        ]
        
        valor_unitario = ""
        for pattern in valor_patterns:
            valor_match = re.search(pattern, item_text, re.IGNORECASE)
            if valor_match:
                valor_unitario = valor_match.group(1)
                # Normalizar formato do valor
                valor_unitario = valor_unitario.replace('.', '').replace(',', '.')
                try:
                    # Verificar se é um valor válido
                    float(valor_unitario)
                    break
                except ValueError:
                    continue
        
        # Extrair unidade de fornecimento
        unidade_match = re.search(r'Unidade de Fornecimento:\s*([^0-9\n]+?)(?=\s|$|\n)', 
                                item_text, re.IGNORECASE)
        unidade = unidade_match.group(1).strip() if unidade_match else ""
        
        # Extrair intervalo mínimo entre lances
        intervalo_patterns = [
            r'Intervalo Mínimo entre Lances[^:]*:\s*R?\$?\s*([\d.,]+)',
            r'Intervalo[^:]*:\s*R?\$?\s*([\d.,]+)'
        ]
        
        intervalo = ""
        for pattern in intervalo_patterns:
            intervalo_match = re.search(pattern, item_text, re.IGNORECASE)
            if intervalo_match:
                intervalo = intervalo_match.group(1)
                break
        
        # Extrair local de entrega
        local_patterns = [
            r'Local de Entrega[^:]*:\s*([^(\n]+?)(?:\s*\(|$|\n)',
            r'Belém/PA\s*\((\d+)\)',
            r'([A-Za-z]+/[A-Z]{2})'
        ]
        
        local = ""
        for pattern in local_patterns:
            local_match = re.search(pattern, item_text, re.IGNORECASE)
            if local_match:
                local = local_match.group(1).strip()
                if local and not local.isdigit():
                    break
        
        # Adicionar item à lista
        item_data = {
            "Item": item_completo,
            "Quantidade Total": int(quantidade) if quantidade.isdigit() else quantidade,
            "Valor Unitário (R$)": valor_unitario,
            "Unidade de Fornecimento": unidade,
            "Intervalo Mínimo entre Lances (R$)": intervalo,
            "Local de Entrega (Quantidade)": local
        }
        
        items.append(item_data)
        
        # Debug: imprimir informações do item extraído
        print(f"Item {item_num} extraído:")
        print(f"  Nome: {item_nome[:50]}...")
        print(f"  Descrição: {descricao[:50]}..." if descricao else "  Descrição: Não encontrada")
        print(f"  Quantidade: {quantidade}")
        print(f"  Valor: {valor_unitario}")
        print(f"  Unidade: {unidade}")
        print(f"  Local: {local}")
        print("-" * 50)
    
    return items

def process_pdf_file(pdf_path):
    """Processa um arquivo PDF e extrai os itens"""
    print(f"Processando: {pdf_path}")
    
    text = ""
    try:
        with fitz.open(pdf_path) as doc:
            for page_num, page in enumerate(doc):
                page_text = page.get_text()
                text += page_text
                print(f"  Página {page_num + 1}: {len(page_text)} caracteres")
    except Exception as e:
        print(f"Erro ao processar PDF {pdf_path}: {e}")
        return []
    
    if not text.strip():
        print(f"  Aviso: Nenhum texto extraído de {pdf_path}")
        return []
    
    return extract_items_from_text(text)

def clean_dataframe(df):
    """Limpa e valida os dados do DataFrame"""
    if df.empty:
        return df
    
    # Limpar valores vazios
    df = df.replace('', pd.NA)
    
    # Validar e limpar valores numéricos
    for col in ['Quantidade Total', 'Valor Unitário (R$)', 'Intervalo Mínimo entre Lances (R$)']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(' ', '').replace('nan', '')
    
    return df

def cot_logic(items):
    """Implementa a lógica de COT (Condições de Operação e Tratamento)"""
    for item in items:
        # Exemplo de lógica COT: ajustar valores com base em condições específicas
        if item["Quantidade Total"] > 100:
            item["Valor Unitário (R$)"] = str(float(item["Valor Unitário (R$)"]) * 0.9)  # 10% de desconto
        # Adicione mais regras conforme necessário

def main():
    """Função principal"""
    # Criar diretório de saída se não existir
    os.makedirs(output_dir, exist_ok=True)
    
    # Verificar se o diretório de entrada existe
    if not os.path.exists(input_dir):
        print(f"Erro: Diretório de entrada não encontrado: {input_dir}")
        return
    
    # Listar arquivos PDF
    pdf_files = [f for f in os.listdir(input_dir) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        print(f"Nenhum arquivo PDF encontrado em: {input_dir}")
        return
    
    print(f"Encontrados {len(pdf_files)} arquivos PDF para processar:")
    for pdf_file in pdf_files:
        print(f"  - {pdf_file}")
    print("-" * 60)
    
    # Processar cada arquivo PDF
    for file_name in pdf_files:
        try:
            pdf_path = os.path.join(input_dir, file_name)
            items = process_pdf_file(pdf_path)
            
            if items:
                # Aplicar lógica COT
                cot_logic(items)
                
                # Criar DataFrame
                df = pd.DataFrame(items)
                df = clean_dataframe(df)
                
                # Salvar como Excel
                xlsx_name = os.path.splitext(file_name)[0] + ".xlsx"
                output_path = os.path.join(output_dir, xlsx_name)
                
                # Salvar com formatação
                with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Itens')
                    
                    # Ajustar largura das colunas
                    worksheet = writer.sheets['Itens']
                    for column in worksheet.columns:
                        max_length = 0
                        column_letter = column[0].column_letter
                        
                        for cell in column:
                            try:
                                if len(str(cell.value)) > max_length:
                                    max_length = len(str(cell.value))
                            except:
                                pass
                        
                        adjusted_width = min(max_length + 2, 50)
                        worksheet.column_dimensions[column_letter].width = adjusted_width
                
                print(f"✅ Processado: {file_name} → {xlsx_name} ({len(items)} itens)")
                
            else:
                print(f"❌ Nenhum item encontrado em: {file_name}")
                
        except Exception as e:
            print(f"❌ Erro ao processar {file_name}: {e}")
    
    print(f"\nProcessamento concluído! Arquivos salvos em: {output_dir}")

if __name__ == "__main__":
    main()