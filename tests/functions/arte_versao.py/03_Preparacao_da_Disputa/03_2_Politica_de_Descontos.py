# Estratégia: Simula políticas de desconto para pregões.
# Funcionamento: Calcula preços com diferentes níveis de desconto.
# Integração: Fornece estratégias para o bot de disputa.

def simulate_discounts(initial_price, discount_levels=[5, 10, 15]):
    return [initial_price * (1 - discount / 100) for discount in discount_levels]