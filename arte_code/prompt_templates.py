from __future__ import annotations

from typing import Dict


CATEGORIAS_PROMPT = """
ESTRUTURA DE CATEGORIAS (USE APENAS ESTAS):
- INSTRUMENTO_SOPRO: trompete, bombardino, trompa, trombone, tuba, sousafone, clarinete, saxofone, flauta
- INSTRUMENTO_PERCUSSAO: bateria, bumbo, timbales, timpano, surdo, tarol, caixa de guerra, quadriton, tambor, afuché
- INSTRUMENTO_CORDA: violino, viola, violão, guitarra, baixo, violoncelo
- INSTRUMENTO_TECLAS: piano, Lira, teclado digital, Glockenspiel
- ACESSORIO_SOPRO: bocal, Lubrificante, boquilha, surdina, graxa, Lever Oil, oleo lubrificante, palheta de saxofone/clarinete
- ACESSORIO_PERCUSSAO: baqueta, Máquina de Hi Hat, talabarte, pele, esteira, prato, triângulo, carrilhão, sino
- ACESSORIO_CORDA: corda, arco, cavalete
- ACESSORIO_GERAL: estante de partitura, suporte, banco, bag
- EQUIPAMENTO_SOM: caixa de som, amplificador, cubo para guitarra
- EQUIPAMENTO_AUDIO: microfone, mesa áudio, mesa de som, fone de ouvido
- EQUIPAMENTO_CABO: cabo HDMI, xlr M/F, P10, P2xP10, Medusa, caixa medusa, Cabo CAT5e,cabo de rede, cabo CFTV 
- OUTROS: use esta categoria apenas se o produto não se encaixar em nenhuma das categorias acima.
"""


def build_prompt_categorizacao(descricao: str) -> str:
    return f"""
Você é um especialista em categorização de produtos musicais.
Sua tarefa é classificar a descrição: "{descricao}"
Usando ESTRITAMENTE as categorias definidas abaixo.
Retorne APENAS uma lista com um objeto JSON: [{{"CATEGORIA_PRINCIPAL": "<categoria>"}}]
Sem texto extra.
{CATEGORIAS_PROMPT}
"""


def build_prompt_selecao(item_data: Dict, base_filtrada_json: str) -> str:
    return f"""
<identidade>
Você é um consultor sênior especializado em licitações públicas governamentais com 20+ anos de experiência em:
Processos licitatórios para instrumentos musicais, equipamentos de som e áudio profissional
Domínio completo da Lei 14.133/21 (art. 7º §5º para isonomia)
Princípios: isonomia, impessoalidade, economicidade e competitividade
DIRETRIZ CRÍTICA: Priorize sempre o menor preço entre opções ≥80% compatíveis com o edital, sem ultrapassar valores de referência.
</identidade>

<item_edital>
Descrição: {item_data['DESCRICAO']}
Valor Unitário Ref.: {item_data['VALOR_UNIT']}
</item_edital>

<base_fornecedores>
{base_filtrada_json}
</base_fornecedores>

<objetivo>
Analise tecnicamente os itens de um edital de licitação, buscando correspondência com produtos na base de fornecedores. A saída deve sugerir até 5 itens compatíveis por produto, respeitando critérios técnicos e legais. O objetivo é garantir a proposta mais competitiva, tecnicamente adequada e legalmente defensável.
Compare apenas com produtos da mesma categoria (ex: microfone com microfone, trompete com trompete, e suas subcategorias tambem, como microfone de lapela com microfone de lapela.).
Compare especificações técnicas listadas.

Validação:
Compatibilidade ≥80%: produto é compatível.
Compatibilidade entre 70% e 80%: produto é alternativa técnica viável.

Priorização entre os compatíveis:
1) Maior compatibilidade técnica.
2) Menor preço.

Resumo das Regras-Chave:
1) Categorias não podem se misturar.
2) Sempre preferir menor preço compatível.
3) Upgrades são bem-vindos se não houver aumento de custo.

</objetivo>

<formato_saida>
Responda somente com uma única linha no formato Markdown de tabela, sem cabeçalho, sem explicações, sem texto extra:
| Marca Sugerida | Modelo Sugerido | Preço Fornecedor | Preço com Margem 53% | Descrição Fornecedor | % Compatibilidade |

IMPORTANTE:
- Não escreva nada além desta linha de tabela.
- Se não encontrar produto adequado, retorne "| N/A | N/A | N/A | N/A | N/A | 0% |".
- Respeite o formato da tabela, com pipes e colunas exatamente na ordem pedida.
- Não utilize aspas, nem quebre linha.
</formato_saida>
"""

