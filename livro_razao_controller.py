"""
Controlador do Livro Razão de Editais Processados

Este módulo gerencia um sistema de controle para evitar processamento duplicado
de editais, mantendo um registro de todos os editais já processados.

Autor: arte_comercial
Data: 2025
"""

import os
import pandas as pd
from datetime import datetime

class LivroRazaoController:
    """Controla o livro razão de editais processados"""
    
    def __init__(self, file_path):
        self.file_path = file_path
        self.processed_editais = set()
        self.load_livro_razao()
    
    def load_livro_razao(self):
        """Carrega o livro razão existente"""
        try:
            if os.path.exists(self.file_path):
                df = pd.read_excel(self.file_path)
                if 'ID_Edital' in df.columns:
                    self.processed_editais = set(df['ID_Edital'].astype(str))
                print(f"📚 Livro razão carregado: {len(self.processed_editais)} editais processados")
            else:
                self.create_livro_razao()
        except Exception as e:
            print(f"❌ Erro ao carregar livro razão: {e}")
            self.create_livro_razao()
    
    def create_livro_razao(self):
        """Cria um novo livro razão"""
        df = pd.DataFrame(columns=[
            'ID_Edital', 'UASG', 'Numero_Edital', 'Comprador', 'Data_Disputa',
            'Data_Processamento', 'Status', 'Itens_Interessantes', 'Percentual_Interesse',
            'Arquivo_Download', 'Card_Trello_ID'
        ])
        df.to_excel(self.file_path, index=False)
        print(f"📚 Novo livro razão criado: {self.file_path}")
    
    def is_edital_processed(self, uasg, edital):
        """Verifica se um edital já foi processado"""
        edital_id = f"{uasg}_{edital}"
        return edital_id in self.processed_editais
    
    def register_edital(self, uasg, edital, comprador, dia_disputa, status, 
                       itens_interessantes=0, percentual_interesse=0, 
                       arquivo_download="", card_trello_id=""):
        """Registra um edital no livro razão"""
        edital_id = f"{uasg}_{edital}"
        self.processed_editais.add(edital_id)
        
        try:
            df = pd.read_excel(self.file_path)
            new_row = {
                'ID_Edital': edital_id,
                'UASG': uasg,
                'Numero_Edital': edital,
                'Comprador': comprador,
                'Data_Disputa': dia_disputa,
                'Data_Processamento': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'Status': status,
                'Itens_Interessantes': itens_interessantes,
                'Percentual_Interesse': percentual_interesse,
                'Arquivo_Download': arquivo_download,
                'Card_Trello_ID': card_trello_id
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            df.to_excel(self.file_path, index=False)
            print(f"✅ Edital registrado no livro razão: {edital_id}")
        except Exception as e:
            print(f"❌ Erro ao registrar edital: {e}")
    
    def get_statistics(self):
        """Retorna estatísticas do livro razão"""
        try:
            df = pd.read_excel(self.file_path)
            if df.empty:
                return {
                    'total': 0,
                    'qualificados': 0,
                    'rejeitados': 0,
                    'nao_interessantes': 0
                }
            
            stats = {
                'total': len(df),
                'qualificados': len(df[df['Status'] == 'QUALIFICADO']),
                'rejeitados': len(df[df['Status'] == 'REJEITADO']),
                'nao_interessantes': len(df[df['Status'] == 'NAO_INTERESSANTE'])
            }
            return stats
        except Exception as e:
            print(f"❌ Erro ao obter estatísticas: {e}")
            return {'total': 0, 'qualificados': 0, 'rejeitados': 0, 'nao_interessantes': 0}
