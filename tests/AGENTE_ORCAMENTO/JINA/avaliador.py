import pandas as pd
import json
from datetime import datetime

class AvaliadorResultados:
    def __init__(self):
        self.resultados = []
        self.arquivo_log = f"avaliacao_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    def registrar_resultado(self, consulta, produto_esperado, resultados_obtidos):
        """Registra os resultados de uma busca para avaliação posterior"""
        registro = {
            'data': datetime.now().isoformat(),
            'consulta': consulta,
            'produto_esperado': produto_esperado,
            'resultados': []
        }
        
        for i, resultado in enumerate(resultados_obtidos):
            registro['resultados'].append({
                'posicao': i+1,
                'id_produto': resultado['produto']['id_produto'],
                'score_final': resultado['score_final'],
                'produto': resultado['produto']['DESCRICAO'],
                'qualidade': resultado.get('qualidade', '')
            })
        
        self.resultados.append(registro)
        self.salvar_resultados()
    
    def calcular_metricas(self):
        """Calcula métricas de precisão com base nos resultados registrados"""
        if not self.resultados:
            return {}
        
        total_consultas = len(self.resultados)
        acertos_top1 = 0
        acertos_top3 = 0
        acertos_top5 = 0
        
        for registro in self.resultados:
            produto_esperado = registro['produto_esperado']
            resultados = registro['resultados']
            
            # Verifica se o produto esperado está nos resultados
            for resultado in resultados:
                if resultado['id_produto'] == produto_esperado:
                    if resultado['posicao'] == 1:
                        acertos_top1 += 1
                    if resultado['posicao'] <= 3:
                        acertos_top3 += 1
                    if resultado['posicao'] <= 5:
                        acertos_top5 += 1
                    break
        
        return {
            'total_consultas': total_consultas,
            'precisao_top1': acertos_top1 / total_consultas,
            'precisao_top3': acertos_top3 / total_consultas,
            'precisao_top5': acertos_top5 / total_consultas
        }
    
    def salvar_resultados(self):
        """Salva os resultados em um arquivo CSV para análise posterior"""
        dados = []
        for registro in self.resultados:
            for resultado in registro['resultados']:
                dados.append({
                    'data': registro['data'],
                    'consulta': registro['consulta'],
                    'produto_esperado': registro['produto_esperado'],
                    'posicao': resultado['posicao'],
                    'id_produto': resultado['id_produto'],
                    'score_final': resultado['score_final'],
                    'qualidade': resultado['qualidade'],
                    'produto': resultado['produto']
                })
        
        df = pd.DataFrame(dados)
        df.to_csv(self.arquivo_log, index=False)
        return self.arquivo_log

    def gerar_relatorio(self):
        """Gera um relatório resumido de performance"""
        metricas = self.calcular_metricas()
        relatorio = f"""
        RELATÓRIO DE AVALIAÇÃO - {datetime.now().strftime('%d/%m/%Y %H:%M')}
        =============================================
        Total de consultas avaliadas: {metricas['total_consultas']}
        Precisão Top 1: {metricas['precisao_top1']*100:.2f}%
        Precisão Top 3: {metricas['precisao_top3']*100:.2f}%
        Precisão Top 5: {metricas['precisao_top5']*100:.2f}%
        
        Arquivo completo de logs: {self.arquivo_log}
        """
        return relatorio

# Exemplo de uso:
# avaliador = AvaliadorResultados()
# avaliador.registrar_resultado("Trompete profissional", 123, resultados)
# print(avaliador.gerar_relatorio())