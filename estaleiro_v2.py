import requests
import time
from datetime import datetime

class TesteSistemaComprovacao:
    def __init__(self):
        self.base_url = "https://dadosabertos.compras.gov.br"
        self.session = requests.Session()
        
        # Licitações dos cards para teste
        self.licitacoes_cards = [
            {'uasg': '987833', 'numero': '90031', 'tipo': 'Pregão SRP', 'data': '2025-07-28'},
            {'uasg': '153128', 'numero': '90020', 'tipo': 'Dispensa', 'data': '2025-07-09'},
            {'uasg': '158720', 'numero': '90089', 'tipo': 'Pregão SRP', 'data': '2025-07-30'},
            {'uasg': '160422', 'numero': '90005', 'tipo': 'Pregão SRP', 'data': '2025-08-11'},
            {'uasg': '102333', 'numero': '90025', 'tipo': 'Dispensa', 'data': '2025-07-09'},
            {'uasg': '786200', 'numero': '90026', 'tipo': 'Dispensa', 'data': '2025-08-01'},
            {'uasg': '153177', 'numero': '90014', 'tipo': 'Pregão SRP', 'data': '2025-08-07'}
        ]
    
    def testar_todos_endpoints(self):
        """
        Testa todos os endpoints para cada licitação dos cards
        """
        resultados = []
        
        for licitacao in self.licitacoes_cards:
            print(f"\n🔍 Testando UASG {licitacao['uasg']} - {licitacao['numero']}")
            
            resultado = {
                'uasg': licitacao['uasg'],
                'numero': licitacao['numero'],
                'tipo': licitacao['tipo'],
                'encontrado_em': [],
                'total_hits': 0
            }
            
            # Teste 1: Sistema Legado - Pregões
            if self._testar_endpoint_pregoes(licitacao['uasg'], licitacao['numero']):
                resultado['encontrado_em'].append('modulo-legado/3_consultarPregoes')
                resultado['total_hits'] += 1
                print(f"  ✅ Encontrado em: modulo-legado/3_consultarPregoes")
            
            # Teste 2: Sistema Legado - Licitações
            if self._testar_endpoint_licitacoes(licitacao['uasg'], licitacao['numero']):
                resultado['encontrado_em'].append('modulo-legado/1_consultarLicitacao')
                resultado['total_hits'] += 1
                print(f"  ✅ Encontrado em: modulo-legado/1_consultarLicitacao")
            
            # Teste 3: Compras Sem Licitação (Para Dispensas)
            if licitacao['tipo'] == 'Dispensa':
                if self._testar_endpoint_dispensas(licitacao['uasg'], licitacao['numero']):
                    resultado['encontrado_em'].append('modulo-legado/5_consultarComprasSemLicitacao')
                    resultado['total_hits'] += 1
                    print(f"  ✅ Encontrado em: modulo-legado/5_consultarComprasSemLicitacao")
            
            # Teste 4: PNCP
            if self._testar_endpoint_pncp(licitacao['uasg'], licitacao['numero']):
                resultado['encontrado_em'].append('modulo-contratacoes/1_consultarContratacoes')
                resultado['total_hits'] += 1
                print(f"  ✅ Encontrado em: modulo-contratacoes/1_consultarContratacoes")
            
            if resultado['total_hits'] == 0:
                print(f"  ❌ Não encontrado em nenhum endpoint")
            
            resultados.append(resultado)
            time.sleep(1)  # Rate limiting
        
        return resultados
    
    def _testar_endpoint_pregoes(self, uasg, numero):
        """Testa endpoint de pregões"""
        endpoint = f"{self.base_url}/modulo-legado/3_consultarPregoes"
        params = {
            'co_uasg': uasg,
            'numero': numero,
            'dt_data_edital_inicial': '2025-06-01',
            'dt_data_edital_final': '2025-09-15'
        }
        
        try:
            response = self.session.get(endpoint, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                return len(data.get('resultado', [])) > 0
        except:
            pass
        return False
    
    def _testar_endpoint_licitacoes(self, uasg, numero):
        """Testa endpoint de licitações gerais"""
        endpoint = f"{self.base_url}/modulo-legado/1_consultarLicitacao"
        params = {
            'uasg': uasg,
            'numero_aviso': numero,
            'data_publicacao_inicial': '2025-06-01',
            'data_publicacao_final': '2025-09-15'
        }
        
        try:
            response = self.session.get(endpoint, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                return len(data.get('resultado', [])) > 0
        except:
            pass
        return False
    
    def _testar_endpoint_dispensas(self, uasg, numero):
        """Testa endpoint de compras sem licitação (dispensas)"""
        endpoint = f"{self.base_url}/modulo-legado/5_consultarComprasSemLicitacao"
        params = {
            'uasg': uasg,
            'numero_aviso': numero,
            'data_publicacao_inicial': '2025-06-01',
            'data_publicacao_final': '2025-09-15'
        }
        
        try:
            response = self.session.get(endpoint, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                return len(data.get('resultado', [])) > 0
        except:
            pass
        return False
    
    def _testar_endpoint_pncp(self, uasg, numero):
        """Testa endpoint PNCP"""
        endpoint = f"{self.base_url}/modulo-contratacoes/1_consultarContratacoes"
        params = {
            'unidadeOrgaoCodigoSiorg': uasg,
            'numeroCompraPncp': numero,
            'dataPublicacaoPncpInicial': '2025-06-01',
            'dataPublicacaoPncpFinal': '2025-09-15'
        }
        
        try:
            response = self.session.get(endpoint, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                return len(data.get('resultado', [])) > 0
        except:
            pass
        return False

# EXECUTAR TESTE DE COMPROVAÇÃO
teste = TesteSistemaComprovacao()
resultados = teste.testar_todos_endpoints()

# Relatório Final
print(f"\n📊 RELATÓRIO DE COMPROVAÇÃO:")
print(f"Total de licitações testadas: {len(resultados)}")

encontradas = [r for r in resultados if r['total_hits'] > 0]
print(f"Licitações encontradas: {len(encontradas)} ({len(encontradas)/len(resultados)*100:.1f}%)")

for resultado in encontradas:
    print(f"  ✅ UASG {resultado['uasg']} - {resultado['numero']}: {', '.join(resultado['encontrado_em'])}")