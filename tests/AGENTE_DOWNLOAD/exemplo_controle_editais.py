"""
Exemplo Simplificado do Sistema de Controle de Editais

Este script demonstra como funciona o sistema de controle de editais processados
sem a necessidade de executar a automação completa do WaveCode.

Autor: arte_comercial
Data: 2025
"""

import os
import pandas as pd
from datetime import datetime
from livro_razao_controller import LivroRazaoController

# Configurações
BASE_DIR = r"G:\Meu Drive\arte_comercial"
LIVRO_RAZAO_PATH = os.path.join(BASE_DIR, "livro_razao_editais.xlsx")

def exemplo_controle_editais():
    """Demonstra o funcionamento do sistema de controle"""
    
    print("🎯 EXEMPLO DO SISTEMA DE CONTROLE DE EDITAIS")
    print("=" * 50)
    
    # 1. Inicializar o controlador do livro razão
    print("\n1. Inicializando o livro razão...")
    livro_razao = LivroRazaoController(LIVRO_RAZAO_PATH)
    
    # 2. Simular alguns editais para teste
    editais_teste = [
        {
            'uasg': '123456',
            'edital': '001',
            'comprador': 'Escola de Música Municipal',
            'dia_disputa': '15/01/2025 - 14:00',
            'status': 'QUALIFICADO',
            'itens_interessantes': 5,
            'percentual_interesse': 25.0,
            'arquivo_download': 'U_123456_E_001_C_Escola_Musica_Municipal_15-01-2025_14h00m.zip',
            'card_trello_id': 'card_001'
        },
        {
            'uasg': '789012',
            'edital': '002',
            'comprador': 'Prefeitura Municipal',
            'dia_disputa': '20/01/2025 - 10:00',
            'status': 'NAO_INTERESSANTE',
            'itens_interessantes': 0,
            'percentual_interesse': 0.0,
            'arquivo_download': '',
            'card_trello_id': ''
        },
        {
            'uasg': '345678',
            'edital': '003',
            'comprador': 'Conservatório de Música',
            'dia_disputa': '25/01/2025 - 16:00',
            'status': 'QUALIFICADO',
            'itens_interessantes': 8,
            'percentual_interesse': 40.0,
            'arquivo_download': 'U_345678_E_003_C_Conservatorio_Musica_25-01-2025_16h00m.zip',
            'card_trello_id': 'card_002'
        }
    ]
    
    # 3. Registrar os editais de teste
    print("\n2. Registrando editais de teste...")
    for edital in editais_teste:
        livro_razao.register_edital(
            uasg=edital['uasg'],
            edital=edital['edital'],
            comprador=edital['comprador'],
            dia_disputa=edital['dia_disputa'],
            status=edital['status'],
            itens_interessantes=edital['itens_interessantes'],
            percentual_interesse=edital['percentual_interesse'],
            arquivo_download=edital['arquivo_download'],
            card_trello_id=edital['card_trello_id']
        )
    
    # 4. Demonstrar verificação de editais já processados
    print("\n3. Verificando editais já processados...")
    editais_para_verificar = [
        ('123456', '001'),  # Já processado
        ('789012', '002'),  # Já processado
        ('345678', '003'),  # Já processado
        ('999999', '999'),  # Novo edital
        ('111111', '111'),  # Novo edital
    ]
    
    for uasg, edital in editais_para_verificar:
        if livro_razao.is_edital_processed(uasg, edital):
            print(f"   ⏭️ Edital {uasg}_{edital} - JÁ PROCESSADO")
        else:
            print(f"   🆕 Edital {uasg}_{edital} - NOVO (pode processar)")
    
    # 5. Mostrar estatísticas
    print("\n4. Estatísticas do livro razão:")
    stats = livro_razao.get_statistics()
    print(f"   📊 Total de editais: {stats['total']}")
    print(f"   ✅ Qualificados: {stats['qualificados']}")
    print(f"   ❌ Rejeitados: {stats['rejeitados']}")
    print(f"   🚫 Não interessantes: {stats['nao_interessantes']}")
    
    # 6. Simular processamento de novos editais
    print("\n5. Simulando processamento de novos editais...")
    novos_editais = [
        ('999999', '999', 'Universidade Federal de Música'),
        ('111111', '111', 'Colégio Técnico de Artes'),
    ]
    
    for uasg, edital, comprador in novos_editais:
        if not livro_razao.is_edital_processed(uasg, edital):
            print(f"   🔍 Processando novo edital: {uasg}_{edital}")
            
            # Simular análise (neste exemplo, todos são qualificados)
            status = 'QUALIFICADO'
            itens_interessantes = 3
            percentual_interesse = 15.0
            
            livro_razao.register_edital(
                uasg=uasg,
                edital=edital,
                comprador=comprador,
                dia_disputa='30/01/2025 - 09:00',
                status=status,
                itens_interessantes=itens_interessantes,
                percentual_interesse=percentual_interesse,
                arquivo_download=f'U_{uasg}_E_{edital}_C_{comprador.replace(" ", "_")}.zip',
                card_trello_id=f'card_{uasg}_{edital}'
            )
            print(f"   ✅ Edital {uasg}_{edital} registrado como {status}")
        else:
            print(f"   ⏭️ Edital {uasg}_{edital} já foi processado anteriormente")
    
    # 7. Estatísticas finais
    print("\n6. Estatísticas finais:")
    stats_final = livro_razao.get_statistics()
    print(f"   📊 Total de editais: {stats_final['total']}")
    print(f"   ✅ Qualificados: {stats_final['qualificados']}")
    print(f"   ❌ Rejeitados: {stats_final['rejeitados']}")
    print(f"   🚫 Não interessantes: {stats_final['nao_interessantes']}")
    
    print(f"\n📚 Livro razão salvo em: {LIVRO_RAZAO_PATH}")
    print("\n🎉 Exemplo concluído!")

def mostrar_estrutura_livro_razao():
    """Mostra a estrutura do livro razão"""
    print("\n📋 ESTRUTURA DO LIVRO RAZÃO")
    print("=" * 30)
    
    colunas = [
        'ID_Edital',
        'UASG', 
        'Numero_Edital',
        'Comprador',
        'Data_Disputa',
        'Data_Processamento',
        'Status',
        'Itens_Interessantes',
        'Percentual_Interesse',
        'Arquivo_Download',
        'Card_Trello_ID'
    ]
    
    print("Colunas do livro razão:")
    for i, coluna in enumerate(colunas, 1):
        print(f"   {i:2d}. {coluna}")
    
    print("\nStatus possíveis:")
    print("   ✅ QUALIFICADO - Edital com itens interessantes")
    print("   ❌ REJEITADO - Edital baixado mas sem itens interessantes")
    print("   🚫 NAO_INTERESSANTE - Edital não baixado (análise preliminar)")

def explicar_beneficios():
    """Explica os benefícios do sistema"""
    print("\n🎯 BENEFÍCIOS DO SISTEMA DE CONTROLE")
    print("=" * 40)
    
    beneficios = [
        "🚫 Evita downloads duplicados",
        "⚡ Reduz tempo de processamento",
        "💰 Economia de recursos (bandwidth, armazenamento)",
        "🎯 Foca apenas em editais relevantes",
        "📊 Rastreabilidade completa",
        "🔄 Processamento incremental",
        "📈 Escalabilidade",
        "🔍 Auditoria e controle"
    ]
    
    for beneficio in beneficios:
        print(f"   {beneficio}")

if __name__ == "__main__":
    # Executar o exemplo
    exemplo_controle_editais()
    
    # Mostrar informações adicionais
    mostrar_estrutura_livro_razao()
    explicar_beneficios()
    
    print("\n" + "=" * 50)
    print("💡 Para usar o sistema completo, execute:")
    print("   python arte_orquestra_controlado.py")
    print("=" * 50)
