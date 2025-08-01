import os
import shutil
import re
import zipfile
from pathlib import Path
import fitz  # PyMuPDF
import pandas as pd

# === Funções do extract_pdf.py ===

def descompactar_arquivos(pasta_origem):
    pasta = Path(pasta_origem)
    if not pasta.exists():
        print(f"Erro: A pasta '{pasta_origem}' não existe!")
        return
    arquivos_zip = list(pasta.glob("*.zip"))
    if not arquivos_zip:
        print("Nenhum arquivo ZIP encontrado na pasta!")
        return
    print(f"Encontrados {len(arquivos_zip)} arquivo(s) ZIP para descompactar...")
    for arquivo_zip in arquivos_zip:
        try:
            print(f"\nDescompactando: {arquivo_zip.name}")
            nome_pasta_destino = arquivo_zip.stem
            pasta_destino = pasta / nome_pasta_destino
            pasta_destino.mkdir(exist_ok=True)
            with zipfile.ZipFile(arquivo_zip, 'r') as zip_ref:
                zip_ref.extractall(pasta_destino)
            print(f"✓ Descompactado em: {pasta_destino}")
            arquivo_zip.unlink()
            print(f"✓ Arquivo ZIP removido: {arquivo_zip.name}")
        except zipfile.BadZipFile:
            print(f"✗ Erro: '{arquivo_zip.name}' não é um arquivo ZIP válido!")
        except PermissionError:
            print(f"✗ Erro: Sem permissão para acessar '{arquivo_zip.name}'!")
        except Exception as e:
            print(f"✗ Erro ao descompactar '{arquivo_zip.name}': {str(e)}")
            print("  → Arquivo ZIP mantido devido ao erro")
    print(f"\nProcesso concluído!")

def extrair_e_copiar_pdfs(pasta_origem, pasta_destino):
    pasta_origem = Path(pasta_origem)
    pasta_destino = Path(pasta_destino)
    pasta_destino.mkdir(parents=True, exist_ok=True)
    padrao_relacao = re.compile(r"RelacaoItens\d+\.pdf", re.IGNORECASE)
    copiados = 0
    print("📁 Iniciando varredura das subpastas...")
    for subpasta in pasta_origem.iterdir():
        if subpasta.is_dir():
            nome_pasta = subpasta.name
            print(f"🔍 Verificando pasta: {nome_pasta}")
            for arquivo in subpasta.glob("*.pdf"):
                if padrao_relacao.fullmatch(arquivo.name):
                    novo_nome = f"{nome_pasta}.pdf"
                    destino_final = pasta_destino / novo_nome
                    shutil.copy2(arquivo, destino_final)
                    print(f"✅ {arquivo.name} copiado e renomeado para {novo_nome}")
                    copiados += 1
                    break  # Considera apenas o primeiro encontrado por pasta
    print(f"\n🎉 Processo concluído: {copiados} arquivo(s) movido(s) para {pasta_destino}")

# === Funções do pdf_to_xlsx.py ===

def extract_items_from_text(text):
    items = []
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r'\s+', ' ', text)
    item_pattern = re.compile(r'(\d+)\s*-\s*([^0-9]+?)(?=Descrição Detalhada:)', re.DOTALL | re.IGNORECASE)
    item_matches = list(item_pattern.finditer(text))
    for i, match in enumerate(item_matches):
        item_num = match.group(1).strip()  # Número do item
        item_nome = match.group(2).strip()
        start_pos = match.start()
        if i + 1 < len(item_matches):
            end_pos = item_matches[i + 1].start()
        else:
            end_pos = len(text)
        item_text = text[start_pos:end_pos]
        descricao_match = re.search(r'Descrição Detalhada:\s*(.*?)(?=Tratamento Diferenciado:|Aplicabilidade Decreto|$)', 
                                  item_text, re.DOTALL | re.IGNORECASE)
        descricao = ""
        if descricao_match:
            descricao = descricao_match.group(1).strip()
            descricao = re.sub(r'\s+', ' ', descricao)
            descricao = re.sub(r'[^\w\s:,.()/-]', '', descricao)
        item_completo = f"{item_nome}"
        if descricao:
            item_completo += f" {descricao}"
        quantidade_match = re.search(r'Quantidade Total:\s*(\d+)', item_text, re.IGNORECASE)
        quantidade = quantidade_match.group(1) if quantidade_match else ""
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
                valor_unitario = valor_unitario.replace('.', '').replace(',', '.')
                try:
                    float(valor_unitario)
                    break
                except ValueError:
                    continue
        unidade_match = re.search(r'Unidade de Fornecimento:\s*([^0-9\n]+?)(?=\s|$|\n)', 
                                item_text, re.IGNORECASE)
        unidade = unidade_match.group(1).strip() if unidade_match else ""
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
        item_data = {
            "Número do Item": item_num,  # Adiciona o número do item como uma nova coluna
            "Descrição": item_completo,
            "Quantidade Total": int(quantidade) if quantidade.isdigit() else quantidade,
            "Valor Unitário (R$)": valor_unitario,
            "Unidade de Fornecimento": unidade,
            "Intervalo Mínimo entre Lances (R$)": intervalo,
            "Local de Entrega (Quantidade)": local
        }
        items.append(item_data)
        
    return items

def process_pdf_file(pdf_path):
    print(f"Processando: {pdf_path}")
    text = ""
    try:
        with fitz.open(pdf_path) as doc:
            for page_num, page in enumerate(doc):
                page_text = page.get_text()
                text += page_text
    except Exception as e:
        print(f"Erro ao processar PDF {pdf_path}: {e}")
        return []
    if not text.strip():
        print(f"  Aviso: Nenhum texto extraído de {pdf_path}")
        return []
    return extract_items_from_text(text)

def clean_dataframe(df):
    if df.empty:
        return df
    df = df.replace('', pd.NA)
    for col in ['Quantidade Total', 'Valor Unitário (R$)', 'Intervalo Mínimo entre Lances (R$)']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(' ', '').replace('nan', '')
    return df

def cot_logic(items):
    for item in items:
        if isinstance(item["Quantidade Total"], int) and item["Quantidade Total"] > 100:
            try:
                item["Valor Unitário (R$)"] = str(float(item["Valor Unitário (R$)"]) * 0.9)
            except Exception:
                pass

def pdfs_para_xlsx(input_dir, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    if not os.path.exists(input_dir):
        print(f"Erro: Diretório de entrada não encontrado: {input_dir}")
        return
    pdf_files = [f for f in os.listdir(input_dir) if f.lower().endswith('.pdf')]
    if not pdf_files:
        print(f"Nenhum arquivo PDF encontrado em: {input_dir}")
        return
    print(f"Encontrados {len(pdf_files)} arquivos PDF para processar:")
    for pdf_file in pdf_files:
        print(f"  - {pdf_file}")
    print("-" * 60)
    for file_name in pdf_files:
        try:
            pdf_path = os.path.join(input_dir, file_name)
            items = process_pdf_file(pdf_path)
            if items:
                cot_logic(items)
                df = pd.DataFrame(items)
                df = clean_dataframe(df)
                xlsx_name = os.path.splitext(file_name)[0] + ".xlsx"
                output_path = os.path.join(output_dir, xlsx_name)
                with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Itens')
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

# === Configuração dos diretórios ===

PASTA_ORIGEM = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\DOWNLOADS"
PASTA_DESTINO_PDF = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\DOWNLOADS"
PASTA_XLSX = r"C:\Users\pietr\OneDrive\Área de Trabalho\ARTE\01_EDITAIS\ORCAMENTOS"

if __name__ == "__main__":
    print("=== DESCOMPACTADOR DE ARQUIVOS ZIP ===")
    descompactar_arquivos(PASTA_ORIGEM)
    print("\n=== EXTRAÇÃO E CÓPIA DE PDFs ===")
    extrair_e_copiar_pdfs(PASTA_ORIGEM, PASTA_DESTINO_PDF)
    print("\n=== CONVERSÃO DE PDF PARA XLSX ===")
    pdfs_para_xlsx(PASTA_DESTINO_PDF, PASTA_XLSX)