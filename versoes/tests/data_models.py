# data_models.py
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum

class CategoriaInstrumento(Enum):
    PERCUSSAO = "percussão"
    SOPRO = "sopro"
    CORDAS = "cordas"
    ELETRONICO = "eletrônico"

@dataclass
class ItemEdital:
    numero: int
    descricao_completa: str
    categoria: CategoriaInstrumento
    tipo_especifico: str
    material: Optional[str]
    dimensoes: Optional[str]
    quantidade: int
    valor_unitario: float
    especificacoes_tecnicas: List[str]
    marca_preferencial: Optional[str]
    
    def __post_init__(self):
        self.validate()
    
    def validate(self):
        if self.quantidade <= 0:
            raise ValueError("Quantidade deve ser positiva")
        if self.valor_unitario <= 0:
            raise ValueError("Valor unitário deve ser positivo")

@dataclass
class ProdutoDisponivel:
    codigo: str
    nome: str
    marca: str
    categoria: CategoriaInstrumento
    tipo_especifico: str
    descricao_tecnica: str
    material: Optional[str]
    dimensoes: Optional[str]
    preco: float
    disponibilidade: bool
    fornecedor: str
    
    def compativel_com(self, item_edital: ItemEdital) -> float:
        """Calcula score de compatibilidade (0-1)"""
        score = 0.0
        
        # Categoria (peso 40%)
        if self.categoria == item_edital.categoria:
            score += 0.4
        
        # Tipo específico (peso 30%)
        if self.tipo_especifico.lower() in item_edital.tipo_especifico.lower():
            score += 0.3
        
        # Material (peso 20%)
        if self.material and item_edital.material:
            if self.material.lower() in item_edital.material.lower():
                score += 0.2
        
        # Dimensões (peso 10%)
        if self.dimensoes and item_edital.dimensoes:
            if self.dimensoes == item_edital.dimensoes:
                score += 0.1
        
        return score