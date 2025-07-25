"""
Exemplos Práticos de Uso das APIs Governamentais
Demonstra casos de uso reais para integração com licitações
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
from government_apis_integration import GovernmentAPIManager, APICredentials
from api_auth_manager import APIClientWithAuth, AuthConfig, RateLimitConfig

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LicitacaoAnalyzer:
    """Analisador de licitações usando múltiplas APIs governamentais"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.api_manager = GovernmentAPIManager(config)
        self.resultados_cache = {}
    
    async def analise_completa_licitacao(self, 
                                       uasg: str,
                                       numero_licitacao: str,
                                       data_inicio: Optional[str] = None) -> Dict[str, Any]:
        """
        Realiza análise completa de uma licitação específica
        
        Args:
            uasg: Código UASG da unidade
            numero_licitacao: Número da licitação
            data_inicio: Data de início para busca (formato YYYY-MM-DD)
        
        Returns:
            Dicionário com análise completa
        """
        
        print(f"🔍 Iniciando análise completa da licitação UASG {uasg} - Nº {numero_licitacao}")
        
        resultado = {
            'licitacao_info': {},
            'fornecedores_participantes': [],
            'fornecedores_validados': [],
            'contratos_relacionados': [],
            'historico_uasg': {},
            'capacitacao_responsaveis': {},
            'documentos_validados': [],
            'analise_riscos': {},
            'recomendacoes': [],
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            # 1. Busca dados da licitação específica
            print("📋 Buscando dados da licitação...")
            licitacoes_data = await self.api_manager.buscar_licitacoes_completas(
                uasg=uasg,
                data_inicio=data_inicio or (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'),
                data_fim=datetime.now().strftime('%Y-%m-%d')
            )
            
            # Filtra licitação específica
            licitacao_alvo = None
            for licitacao in licitacoes_data.get('licitacoes', []):
                if (licitacao.get('numero') == numero_licitacao or 
                    str(licitacao.get('id')) == numero_licitacao):
                    licitacao_alvo = licitacao
                    break
            
            if not licitacao_alvo:
                print(f"⚠️ Licitação {numero_licitacao} não encontrada para UASG {uasg}")
                return resultado
            
            resultado['licitacao_info'] = licitacao_alvo
            print(f"✅ Licitação encontrada: {licitacao_alvo.get('objeto', 'N/A')}")
            
            # 2. Analisa histórico da UASG
            print("📊 Analisando histórico da UASG...")
            resultado['historico_uasg'] = await self._analisar_historico_uasg(uasg)
            
            # 3. Valida fornecedores participantes
            print("🏢 Validando fornecedores...")
            fornecedores = self._extrair_fornecedores_licitacao(licitacao_alvo)
            resultado['fornecedores_participantes'] = fornecedores
            
            if fornecedores:
                resultado['fornecedores_validados'] = await self._validar_fornecedores(fornecedores)
            
            # 4. Busca contratos relacionados
            print("📄 Buscando contratos relacionados...")
            resultado['contratos_relacionados'] = licitacoes_data.get('contratos_relacionados', [])
            
            # 5. Verifica capacitação dos responsáveis
            print("🎓 Verificando capacitação dos responsáveis...")
            responsaveis = self._extrair_responsaveis_licitacao(licitacao_alvo)
            if responsaveis:
                resultado['capacitacao_responsaveis'] = await self.api_manager.obter_capacitacao_responsaveis(responsaveis)
            
            # 6. Valida documentos (se disponíveis)
            print("📋 Validando documentos...")
            documentos = self._extrair_documentos_licitacao(licitacao_alvo)
            if documentos:
                resultado['documentos_validados'] = await self.api_manager.validar_documentos_licitacao(documentos)
            
            # 7. Análise de riscos
            print("⚠️ Realizando análise de riscos...")
            resultado['analise_riscos'] = self._analisar_riscos(resultado)
            
            # 8. Gera recomendações
            print("💡 Gerando recomendações...")
            resultado['recomendacoes'] = self._gerar_recomendacoes(resultado)
            
            print("✅ Análise completa finalizada!")
            return resultado
            
        except Exception as e:
            logger.error(f"Erro na análise completa: {e}")
            resultado['erro'] = str(e)
            return resultado
    
    async def _analisar_historico_uasg(self, uasg: str) -> Dict[str, Any]:
        """Analisa histórico de licitações da UASG"""
        try:
            # Busca licitações dos últimos 2 anos
            data_inicio = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')
            
            historico_data = await self.api_manager.buscar_licitacoes_completas(
                uasg=uasg,
                data_inicio=data_inicio
            )
            
            licitacoes = historico_data.get('licitacoes', [])
            contratos = historico_data.get('contratos_relacionados', [])
            
            # Análise estatística
            analise = {
                'total_licitacoes': len(licitacoes),
                'total_contratos': len(contratos),
                'valor_total_contratado': sum(float(c.get('valor', 0)) for c in contratos if c.get('valor')),
                'modalidades_utilizadas': list(set(l.get('modalidade') for l in licitacoes if l.get('modalidade'))),
                'fornecedores_recorrentes': self._identificar_fornecedores_recorrentes(contratos),
                'media_prazo_execucao': self._calcular_media_prazo_execucao(contratos),
                'taxa_sucesso': self._calcular_taxa_sucesso(licitacoes)
            }
            
            return analise
            
        except Exception as e:
            logger.error(f"Erro na análise de histórico: {e}")
            return {'erro': str(e)}
    
    def _extrair_fornecedores_licitacao(self, licitacao: Dict) -> List[Dict]:
        """Extrai fornecedores da licitação"""
        fornecedores = []
        
        # Busca em diferentes campos possíveis
        if 'participantes' in licitacao:
            for participante in licitacao['participantes']:
                if participante.get('cnpj'):
                    fornecedores.append({
                        'cnpj': participante['cnpj'],
                        'razao_social': participante.get('razao_social'),
                        'situacao': participante.get('situacao')
                    })
        
        if 'vencedor' in licitacao and licitacao['vencedor'].get('cnpj'):
            fornecedores.append({
                'cnpj': licitacao['vencedor']['cnpj'],
                'razao_social': licitacao['vencedor'].get('razao_social'),
                'situacao': 'vencedor'
            })
        
        return fornecedores
    
    async def _validar_fornecedores(self, fornecedores: List[Dict]) -> List[Dict]:
        """Valida fornecedores usando SERPRO DataValid"""
        validados = []
        
        if 'serpro_datavalid' in self.api_manager.clients:
            async with self.api_manager.clients['serpro_datavalid'] as client:
                for fornecedor in fornecedores:
                    cnpj = fornecedor.get('cnpj')
                    if cnpj:
                        try:
                            validacao = await client.consultar_cnpj(cnpj)
                            validados.append({
                                'cnpj': cnpj,
                                'razao_social': fornecedor.get('razao_social'),
                                'situacao_original': fornecedor.get('situacao'),
                                'validacao_serpro': validacao.data if validacao.success else None,
                                'valido': validacao.success,
                                'erro_validacao': validacao.error if not validacao.success else None
                            })
                        except Exception as e:
                            logger.error(f"Erro na validação do CNPJ {cnpj}: {e}")
                            validados.append({
                                'cnpj': cnpj,
                                'erro_validacao': str(e),
                                'valido': False
                            })
        
        return validados
    
    def _extrair_responsaveis_licitacao(self, licitacao: Dict) -> List[str]:
        """Extrai CPFs dos responsáveis pela licitação"""
        responsaveis = []
        
        # Busca em diferentes campos
        if 'responsavel_tecnico' in licitacao:
            cpf = licitacao['responsavel_tecnico'].get('cpf')
            if cpf:
                responsaveis.append(cpf)
        
        if 'pregoeiro' in licitacao:
            cpf = licitacao['pregoeiro'].get('cpf')
            if cpf:
                responsaveis.append(cpf)
        
        return list(set(responsaveis))  # Remove duplicatas
    
    def _extrair_documentos_licitacao(self, licitacao: Dict) -> List[Dict]:
        """Extrai documentos da licitação para validação"""
        documentos = []
        
        if 'anexos' in licitacao:
            for i, anexo in enumerate(licitacao['anexos']):
                if anexo.get('qr_code'):
                    documentos.append({
                        'id': f"anexo_{i}",
                        'nome': anexo.get('nome'),
                        'qr_code': anexo['qr_code']
                    })
        
        return documentos
    
    def _identificar_fornecedores_recorrentes(self, contratos: List[Dict]) -> Dict[str, int]:
        """Identifica fornecedores que aparecem com frequência"""
        contagem = {}
        
        for contrato in contratos:
            cnpj = contrato.get('cnpj_contratada')
            if cnpj:
                contagem[cnpj] = contagem.get(cnpj, 0) + 1
        
        # Retorna apenas os que aparecem mais de uma vez
        return {cnpj: count for cnpj, count in contagem.items() if count > 1}
    
    def _calcular_media_prazo_execucao(self, contratos: List[Dict]) -> Optional[float]:
        """Calcula média de prazo de execução dos contratos"""
        prazos = []
        
        for contrato in contratos:
            if contrato.get('data_inicio') and contrato.get('data_fim'):
                try:
                    inicio = datetime.fromisoformat(contrato['data_inicio'].replace('Z', '+00:00'))
                    fim = datetime.fromisoformat(contrato['data_fim'].replace('Z', '+00:00'))
                    prazo_dias = (fim - inicio).days
                    if prazo_dias > 0:
                        prazos.append(prazo_dias)
                except:
                    continue
        
        return sum(prazos) / len(prazos) if prazos else None
    
    def _calcular_taxa_sucesso(self, licitacoes: List[Dict]) -> float:
        """Calcula taxa de sucesso das licitações"""
        if not licitacoes:
            return 0.0
        
        sucessos = sum(1 for l in licitacoes if l.get('situacao') in ['homologada', 'adjudicada', 'concluida'])
        return (sucessos / len(licitacoes)) * 100
    
    def _analisar_riscos(self, resultado: Dict) -> Dict[str, Any]:
        """Realiza análise de riscos baseada nos dados coletados"""
        riscos = {
            'nivel_risco_geral': 'baixo',
            'fatores_risco': [],
            'pontuacao_risco': 0
        }
        
        # Análise de fornecedores
        fornecedores_invalidos = sum(1 for f in resultado.get('fornecedores_validados', []) if not f.get('valido'))
        if fornecedores_invalidos > 0:
            riscos['fatores_risco'].append(f"{fornecedores_invalidos} fornecedor(es) com dados inválidos")
            riscos['pontuacao_risco'] += fornecedores_invalidos * 10
        
        # Análise de histórico
        historico = resultado.get('historico_uasg', {})
        taxa_sucesso = historico.get('taxa_sucesso', 100)
        if taxa_sucesso < 70:
            riscos['fatores_risco'].append(f"Taxa de sucesso baixa da UASG: {taxa_sucesso:.1f}%")
            riscos['pontuacao_risco'] += 20
        
        # Análise de capacitação
        capacitacoes = resultado.get('capacitacao_responsaveis', {})
        responsaveis_sem_capacitacao = sum(1 for cpf, dados in capacitacoes.items() if 'erro' in dados)
        if responsaveis_sem_capacitacao > 0:
            riscos['fatores_risco'].append(f"{responsaveis_sem_capacitacao} responsável(is) sem dados de capacitação")
            riscos['pontuacao_risco'] += responsaveis_sem_capacitacao * 5
        
        # Determina nível de risco
        if riscos['pontuacao_risco'] >= 30:
            riscos['nivel_risco_geral'] = 'alto'
        elif riscos['pontuacao_risco'] >= 15:
            riscos['nivel_risco_geral'] = 'médio'
        
        return riscos
    
    def _gerar_recomendacoes(self, resultado: Dict) -> List[str]:
        """Gera recomendações baseadas na análise"""
        recomendacoes = []
        
        # Recomendações baseadas em riscos
        analise_riscos = resultado.get('analise_riscos', {})
        if analise_riscos.get('nivel_risco_geral') == 'alto':
            recomendacoes.append("⚠️ ATENÇÃO: Licitação apresenta alto risco. Revisar cuidadosamente antes de participar.")
        
        # Recomendações sobre fornecedores
        fornecedores_validados = resultado.get('fornecedores_validados', [])
        fornecedores_invalidos = [f for f in fornecedores_validados if not f.get('valido')]
        if fornecedores_invalidos:
            recomendacoes.append(f"🔍 Verificar situação de {len(fornecedores_invalidos)} fornecedor(es) com dados inconsistentes.")
        
        # Recomendações sobre histórico
        historico = resultado.get('historico_uasg', {})
        if historico.get('total_licitacoes', 0) < 5:
            recomendacoes.append("📊 UASG com pouco histórico de licitações. Avaliar capacidade de execução.")
        
        # Recomendações sobre capacitação
        capacitacoes = resultado.get('capacitacao_responsaveis', {})
        if capacitacoes:
            responsaveis_capacitados = sum(1 for dados in capacitacoes.values() if 'erro' not in dados)
            if responsaveis_capacitados > 0:
                recomendacoes.append(f"✅ {responsaveis_capacitados} responsável(is) com capacitação verificada.")
        
        # Recomendações gerais
        if not recomendacoes:
            recomendacoes.append("✅ Licitação apresenta baixo risco. Prosseguir com análise técnica detalhada.")
        
        return recomendacoes

async def exemplo_analise_licitacao():
    """Exemplo prático de análise de licitação"""
    
    # Configuração (substitua pelas suas credenciais)
    config = {
        "compras_publicas": {
            "api_key": "sua_api_key_aqui",
            "token": "seu_token_aqui"
        },
        "enap": {
            "api_key": "sua_enap_api_key"
        },
        "serpro": {
            "datavalid": {
                "client_id": "seu_client_id",
                "client_secret": "seu_client_secret"
            }
        }
    }
    
    # Inicializa analisador
    analyzer = LicitacaoAnalyzer(config)
    
    # Exemplo de análise
    resultado = await analyzer.analise_completa_licitacao(
        uasg="123456",  # Substitua por UASG real
        numero_licitacao="001/2025",  # Substitua por número real
        data_inicio="2024-01-01"
    )
    
    # Exibe resultados
    print("" + "="*60)
    print("📊 RELATÓRIO DE ANÁLISE DE LICITAÇÃO")
    print("="*60)
    
    licitacao_info = resultado.get('licitacao_info', {})
    print(f"🏛️ UASG: {licitacao_info.get('uasg', 'N/A')}")
    print(f"📋 Objeto: {licitacao_info.get('objeto', 'N/A')}")
    print(f"💰 Valor Estimado: R$ {licitacao_info.get('valor_estimado', 'N/A')}")
    
    # Análise de riscos
    riscos = resultado.get('analise_riscos', {})
    print(f"⚠️ NÍVEL DE RISCO: {riscos.get('nivel_risco_geral', 'N/A').upper()}")
    print(f"📊 Pontuação de Risco: {riscos.get('pontuacao_risco', 0)}")
    
    # Fatores de risco
    if riscos.get('fatores_risco'):
        print("🚨 FATORES DE RISCO:")
        for fator in riscos['fatores_risco']:
            print(f"  • {fator}")
    
    # Recomendações
    recomendacoes = resultado.get('recomendacoes', [])
    if recomendacoes:
        print("💡 RECOMENDAÇÕES:")
        for rec in recomendacoes:
            print(f"  • {rec}")
    
    # Estatísticas do histórico
    historico = resultado.get('historico_uasg', {})
    if historico:
        print(f"📈 HISTÓRICO DA UASG:")
        print(f"  • Total de licitações: {historico.get('total_licitacoes', 0)}")
        print(f"  • Taxa de sucesso: {historico.get('taxa_sucesso', 0):.1f}%")
        print(f"  • Valor total contratado: R$ {historico.get('valor_total_contratado', 0):,.2f}")
    
    # Salva relatório
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"analise_licitacao_{licitacao_info.get('uasg', 'unknown')}_{timestamp}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"💾 Relatório salvo em: {filename}")
    
    return resultado

async def exemplo_monitoramento_continuo():
    """Exemplo de monitoramento contínuo de licitações"""
    
    print("🔄 Iniciando monitoramento contínuo de licitações...")
    
    # Lista de UASGs para monitorar
    uasgs_monitoradas = ["123456", "789012", "345678"]  # Substitua por UASGs reais
    
    config = {
        "compras_publicas": {
            "api_key": "sua_api_key_aqui",
            "token": "seu_token_aqui"
        }
    }
    
    analyzer = LicitacaoAnalyzer(config)
    
    # Monitora cada UASG
    for uasg in uasgs_monitoradas:
        print(f"📡 Monitorando UASG {uasg}...")
        
        try:
            # Busca licitações dos últimos 30 dias
            data_inicio = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            
            licitacoes_data = await analyzer.api_manager.buscar_licitacoes_completas(
                uasg=uasg,
                data_inicio=data_inicio
            )
            
            licitacoes = licitacoes_data.get('licitacoes', [])
            print(f"  ✅ Encontradas {len(licitacoes)} licitações")
            
            # Analisa licitações em aberto
            licitacoes_abertas = [l for l in licitacoes if l.get('situacao') in ['aberta', 'publicada']]
            
            if licitacoes_abertas:
                print(f"  🔔 {len(licitacoes_abertas)} licitação(ões) em aberto:")
                
                for licitacao in licitacoes_abertas[:3]:  # Mostra apenas as 3 primeiras
                    print(f"    • {licitacao.get('numero', 'N/A')}: {licitacao.get('objeto', 'N/A')[:50]}...")
                    
                    # Análise rápida de risco
                    if licitacao.get('valor_estimado'):
                        valor = float(licitacao['valor_estimado'])
                        if valor > 1000000:  # Mais de 1 milhão
                            print(f"      💰 ALTO VALOR: R$ {valor:,.2f}")
            
        except Exception as e:
            print(f"  ❌ Erro no monitoramento da UASG {uasg}: {e}")
    
    print("✅ Monitoramento concluído!")

async def exemplo_relatorio_fornecedores():
    """Exemplo de relatório de fornecedores"""
    
    print("📊 Gerando relatório de fornecedores...")
    
    config = {
        "compras_publicas": {
            "api_key": "sua_api_key_aqui",
            "token": "seu_token_aqui"
        },
        "serpro": {
            "datavalid": {
                "client_id": "seu_client_id",
                "client_secret": "seu_client_secret"
            }
        }
    }
    
    analyzer = LicitacaoAnalyzer(config)
    
    # Busca contratos dos últimos 6 meses
    data_inicio = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
    
    contratos_data = await analyzer.api_manager.buscar_licitacoes_completas(
        data_inicio=data_inicio
    )
    
    contratos = contratos_data.get('contratos_relacionados', [])
    print(f"📄 Analisando {len(contratos)} contratos...")
    
    # Agrupa por fornecedor
    fornecedores_stats = {}
    
    for contrato in contratos:
        cnpj = contrato.get('cnpj_contratada')
        if cnpj:
            if cnpj not in fornecedores_stats:
                fornecedores_stats[cnpj] = {
                    'razao_social': contrato.get('razao_social_contratada', 'N/A'),
                    'total_contratos': 0,
                    'valor_total': 0,
                    'uasgs_atendidas': set()
                }
            
            fornecedores_stats[cnpj]['total_contratos'] += 1
            fornecedores_stats[cnpj]['valor_total'] += float(contrato.get('valor', 0))
            fornecedores_stats[cnpj]['uasgs_atendidas'].add(contrato.get('uasg'))
    
    # Ordena por valor total
    top_fornecedores = sorted(
        fornecedores_stats.items(),
        key=lambda x: x[1]['valor_total'],
        reverse=True
    )[:10]
    
    print("🏆 TOP 10 FORNECEDORES (por valor contratado):")
    print("-" * 80)
    
    for i, (cnpj, stats) in enumerate(top_fornecedores, 1):
        print(f"{i:2d}. {stats['razao_social'][:40]:<40}")
        print(f"     CNPJ: {cnpj}")
        print(f"     Contratos: {stats['total_contratos']:3d} | Valor: R$ {stats['valor_total']:>12,.2f}")
        print(f"     UASGs atendidas: {len(stats['uasgs_atendidas'])}")
        print()
    
    # Salva relatório em CSV
    df_data = []
    for cnpj, stats in fornecedores_stats.items():
        df_data.append({
            'CNPJ': cnpj,
            'Razão Social': stats['razao_social'],
            'Total Contratos': stats['total_contratos'],
            'Valor Total': stats['valor_total'],
            'UASGs Atendidas': len(stats['uasgs_atendidas'])
        })
    
    df = pd.DataFrame(df_data)
    filename = f"relatorio_fornecedores_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    
    print(f"💾 Relatório salvo em: {filename}")

if __name__ == "__main__":
    print("🚀 Exemplos Práticos de APIs Governamentais")
    print("=" * 50)
    
    # Executa exemplos
    asyncio.run(exemplo_analise_licitacao())
    print("" + "="*50)
    asyncio.run(exemplo_monitoramento_continuo())
    print("" + "="*50)
    asyncio.run(exemplo_relatorio_fornecedores())