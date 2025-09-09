import pandas as pd
import requests
import json
from datetime import datetime
import os

class LicitacaoMonitor:
    def __init__(self):
        self.base_url = "https://compras.dados.gov.br"
        self.output_path = r"C:\Users\pietr\OneDrive\.vscode\arte_\DOWNLOADS\RESULTADO\arte_heavy_Arte.xlsx"
        self.master_path = r"C:\Users\pietr\OneDrive\.vscode\arte_\master_heavy.xlsx"
        
    def load_master_data(self):
        """Load master data from Excel and show columns"""
        df = pd.read_excel(self.master_path)
        print("Colunas disponíveis no arquivo:", df.columns.tolist())
        print("\nPrimeiras 5 linhas do arquivo:")
        print(df.head())
        return df
        
    def check_item_status(self, uasg, edital, item):
        """Check status of specific item"""
        try:
            url = f"{self.base_url}/pregoes/doc/pregao/{uasg}/{edital}"
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                return self.process_status(data, item)
            return "Aguardando Disputa"
        except Exception as e:
            print(f"Erro ao verificar status: {e}")
            return "Erro na verificação"
            
    def process_status(self, data, item_num):
        if 'items' not in data:
            return "Aguardando Disputa"
            
        for item in data['items']:
            if str(item.get('numero')) == str(item_num):
                if item.get('adjudicado'):
                    return "Adjudicada" if item.get('vencedor') == "ARTE" else "Perdida"
                return f"Rank {item.get('classificacao', 'N/A')}"
                
        return "Aguardando Disputa"
        
    def generate_report(self):
        """Generate monitoring report"""
        df = self.load_master_data()
        
        # Aguarde input do usuário para confirmar os nomes das colunas
        print("\nPor favor, informe os nomes corretos das colunas:")
        uasg_col = input("Nome da coluna UASG: ")
        edital_col = input("Nome da coluna Edital: ")
        item_col = input("Nome da coluna Item: ")
        
        results = []
        for _, row in df.iterrows():
            try:
                status = self.check_item_status(
                    row[uasg_col],
                    row[edital_col],
                    row[item_col]
                )
                results.append({
                    'UASG': row[uasg_col],
                    'EDITAL': row[edital_col],
                    'Item': row[item_col],
                    'Status': status
                })
            except Exception as e:
                print(f"Erro ao processar linha: {row}")
                print(f"Erro: {e}")
                
        output_df = pd.DataFrame(results)
        output_df.to_excel(self.output_path, index=False)

if __name__ == "__main__":
    try:
        monitor = LicitacaoMonitor()
        print("Iniciando monitoramento de licitações...")
        monitor.generate_report()
        print(f"Relatório gerado com sucesso em: {monitor.output_path}")
    except Exception as e:
        print(f"Erro durante execução: {e}")