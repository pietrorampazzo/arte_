#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚀 RATE LIMITER OTIMIZADO - BATCHES INTELIGENTES
Versão: Estado da Arte - Janeiro 2025

FUNCIONALIDADES:
✅ Rate limiting inteligente para Google Gemini
✅ Batches adaptativos baseados em tokens
✅ Estimativa precisa de tokens
✅ Recuperação automática de erros
✅ Logging detalhado para monitoramento

LIMITES GOOGLE GEMINI 2.0 FLASH-LITE:
- RPM: 30 solicitações por minuto
- TPM: 1.000.000 tokens por minuto  
- RPD: 200 solicitações por dia

ESTRATÉGIA DE BATCHES:
- Batch padrão: 20 itens (~5.000 tokens)
- Batch adaptativo: Ajusta baseado no TPM disponível
- Fallback: Reduz batch em caso de erro

Autor: Sistema Otimizado
"""

import time
import logging
from datetime import datetime, timedelta
import pandas as pd
import json
import re

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RateLimiterOtimizado:
    """Rate limiter inteligente para APIs com batches adaptativos"""
    
    def __init__(self, rpm=30, tpm=1_000_000, rpd=200, batch_size_default=200):
        # Limites da API
        self.rpm = rpm
        self.tpm = tpm
        self.rpd = rpd
        
        # Configuração de batches
        self.batch_size_default = batch_size_default
        self.batch_size_current = batch_size_default
        self.batch_size_min = 5
        self.batch_size_max = 50
        
        # Histórico de solicitações
        self.requests_in_minute = []
        self.tokens_in_minute = []
        self.requests_in_day = []
        
        # Controle de tempo
        self.day_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self.last_request_time = None
        
        # Estatísticas
        self.total_requests = 0
        self.total_tokens = 0
        self.total_errors = 0
        
        logger.info("Rate Limiter inicializado: RPM=%d, TPM=%d, RPD=%d, Batch=%d", 
                   rpm, tpm, rpd, batch_size_default)
    
    def estimate_tokens_precise(self, texts):
        """
        Estimativa precisa de tokens baseada em análise de texto
        
        MÉTODO MELHORADO:
        - Conta palavras, números, pontuação
        - Considera tokens especiais (JSON, formatação)
        - Margem de segurança de 20%
        """
        if not texts:
            return 0
        
        total_tokens = 0
        
        for text in texts:
            if not text or pd.isna(text):
                continue
            
            text_str = str(text)
            
            # Contagem básica: 1 token ≈ 4 caracteres (conservador)
            base_tokens = len(text_str) // 3.5  # Mais preciso que //4
            
            # Ajustes para diferentes tipos de conteúdo
            
            # Texto técnico (mais tokens por palavra)
            if any(term in text_str.upper() for term in ['ESPECIFICAÇÕES', 'TÉCNICO', 'INSTRUMENTO']):
                base_tokens *= 1.2
            
            # JSON/estruturado (tokens extras para formatação)
            if '{' in text_str or '[' in text_str:
                base_tokens *= 1.3
            
            # Números e medidas (tokens extras)
            numbers = len(re.findall(r'\d+', text_str))
            base_tokens += numbers * 0.5
            
            # Pontuação complexa
            punctuation = len(re.findall(r'[,;:.!?()[\]{}"]', text_str))
            base_tokens += punctuation * 0.2
            
            total_tokens += base_tokens
        
        # Margem de segurança de 20%
        total_tokens = int(total_tokens * 1.2)
        
        # Mínimo de 10 tokens por texto não vazio
        total_tokens = max(total_tokens, len([t for t in texts if t and not pd.isna(t)]) * 10)
        
        return total_tokens
    
    def calculate_optimal_batch_size(self, available_tpm, avg_tokens_per_item=250):
        """Calcula tamanho ótimo do batch baseado no TPM disponível"""
        
        # Calcular quantos itens cabem no TPM disponível
        max_items_by_tpm = available_tpm // avg_tokens_per_item
        
        # Limitar pelos constraints
        optimal_size = min(
            max_items_by_tpm,
            self.batch_size_max,
            max(self.batch_size_min, max_items_by_tpm)
        )
        
        return int(optimal_size)
    
    def update_batch_size_adaptive(self, success=True, tokens_used=0):
        """Atualiza tamanho do batch adaptativamente baseado no sucesso"""
        
        if success:
            # Sucesso: pode tentar aumentar o batch (gradualmente)
            if self.batch_size_current < self.batch_size_max:
                self.batch_size_current = min(
                    self.batch_size_current + 2,
                    self.batch_size_max
                )
                logger.debug("Batch size aumentado para: %d", self.batch_size_current)
        else:
            # Erro: reduzir batch para ser mais conservador
            self.batch_size_current = max(
                self.batch_size_current // 2,
                self.batch_size_min
            )
            logger.warning("Batch size reduzido para: %d devido a erro", self.batch_size_current)
    
    def get_current_limits_status(self):
        """Retorna status atual dos limites"""
        now = datetime.now()
        
        # Limpar histórico antigo
        self._clean_old_records(now)
        
        # Calcular uso atual
        current_rpm = len(self.requests_in_minute)
        current_tpm = sum(tokens for _, tokens in self.tokens_in_minute)
        current_rpd = len(self.requests_in_day)
        
        # Calcular disponibilidade
        available_rpm = self.rpm - current_rpm
        available_tpm = self.tpm - current_tpm
        available_rpd = self.rpd - current_rpd
        
        return {
            'rpm': {'current': current_rpm, 'limit': self.rpm, 'available': available_rpm},
            'tpm': {'current': current_tpm, 'limit': self.tpm, 'available': available_tpm},
            'rpd': {'current': current_rpd, 'limit': self.rpd, 'available': available_rpd},
            'batch_size': self.batch_size_current
        }
    
    def _clean_old_records(self, now):
        """Remove registros antigos do histórico"""
        
        # Atualizar janela de um dia
        if now >= self.day_start + timedelta(days=1):
            self.day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            self.requests_in_day = []
            logger.info("Janela diária reiniciada. RPD resetado.")
        
        # Limpar registros de mais de 1 minuto
        minute_ago = now - timedelta(minutes=1)
        self.requests_in_minute = [t for t in self.requests_in_minute if t > minute_ago]
        self.tokens_in_minute = [(t, tokens) for t, tokens in self.tokens_in_minute if t > minute_ago]
    
    def can_make_request(self, texts):
        """
        Verifica se pode fazer solicitação com os textos fornecidos
        
        RETORNA:
        - True: Pode fazer a solicitação
        - False: Deve aguardar
        - int: Segundos para aguardar
        """
        now = datetime.now()
        self._clean_old_records(now)
        
        # Estimar tokens necessários
        tokens_needed = self.estimate_tokens_precise(texts)
        
        # Verificar limites
        status = self.get_current_limits_status()
        
        # Verificar RPD (limite mais restritivo)
        if status['rpd']['available'] <= 0:
            logger.error("Limite diário atingido: %d/%d RPD", status['rpd']['current'], self.rpd)
            return False
        
        # Verificar RPM
        if status['rpm']['available'] <= 0:
            wait_time = 60 - (now - self.requests_in_minute[0]).total_seconds()
            logger.info("Limite RPM atingido. Aguardando %.1f segundos.", wait_time)
            return int(wait_time) + 1
        
        # Verificar TPM
        if tokens_needed > status['tpm']['available']:
            if self.tokens_in_minute:
                wait_time = 60 - (now - self.tokens_in_minute[0][0]).total_seconds()
                logger.info("Limite TPM atingido. Tokens necessários: %d, disponíveis: %d. Aguardando %.1f segundos.", 
                           tokens_needed, status['tpm']['available'], wait_time)
                return int(wait_time) + 1
            else:
                # Tokens necessários excedem limite total
                logger.error("Batch muito grande: %d tokens > %d TPM", tokens_needed, self.tpm)
                return False
        
        return True
    
    def wait_if_needed(self, texts):
        """Aguarda se necessário antes de fazer a solicitação"""
        
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            can_proceed = self.can_make_request(texts)
            
            if can_proceed is True:
                return True
            elif can_proceed is False:
                logger.error("Não é possível fazer a solicitação (limite diário ou batch muito grande)")
                return False
            else:
                # can_proceed é o tempo de espera
                wait_time = can_proceed
                logger.info("Aguardando %d segundos antes da próxima tentativa...", wait_time)
                time.sleep(wait_time)
                retry_count += 1
        
        logger.error("Máximo de tentativas atingido")
        return False
    
    def record_request(self, texts, success=True):
        """Registra uma solicitação realizada"""
        now = datetime.now()
        tokens_used = self.estimate_tokens_precise(texts)
        
        if success:
            # Registrar solicitação bem-sucedida
            self.requests_in_minute.append(now)
            self.tokens_in_minute.append((now, tokens_used))
            self.requests_in_day.append(now)
            
            # Atualizar estatísticas
            self.total_requests += 1
            self.total_tokens += tokens_used
            
            # Atualizar batch size adaptativamente
            self.update_batch_size_adaptive(success=True, tokens_used=tokens_used)
            
            logger.debug("Solicitação registrada: %d tokens, RPM: %d/%d, TPM: %d/%d, RPD: %d/%d", 
                        tokens_used, len(self.requests_in_minute), self.rpm,
                        sum(t for _, t in self.tokens_in_minute), self.tpm,
                        len(self.requests_in_day), self.rpd)
        else:
            # Registrar erro
            self.total_errors += 1
            self.update_batch_size_adaptive(success=False)
            logger.warning("Erro registrado. Total de erros: %d", self.total_errors)
        
        self.last_request_time = now
    
    def get_statistics(self):
        """Retorna estatísticas de uso"""
        status = self.get_current_limits_status()
        
        return {
            'total_requests': self.total_requests,
            'total_tokens': self.total_tokens,
            'total_errors': self.total_errors,
            'current_status': status,
            'batch_size_current': self.batch_size_current,
            'success_rate': (self.total_requests / max(self.total_requests + self.total_errors, 1)) * 100
        }
    
    def suggest_batch_size(self, total_items, avg_tokens_per_item=250):
        """Sugere tamanho de batch ótimo para processar todos os itens"""
        status = self.get_current_limits_status()
        
        # Calcular baseado no TPM disponível
        optimal_by_tpm = self.calculate_optimal_batch_size(
            status['tpm']['available'], avg_tokens_per_item
        )
        
        # Calcular baseado no RPD disponível
        remaining_requests = status['rpd']['available']
        optimal_by_rpd = total_items // max(remaining_requests, 1)
        
        # Usar o mais conservador
        suggested_size = min(optimal_by_tpm, optimal_by_rpd, self.batch_size_max)
        suggested_size = max(suggested_size, self.batch_size_min)
        
        logger.info("Batch sugerido: %d (TPM: %d, RPD: %d, atual: %d)", 
                   suggested_size, optimal_by_tpm, optimal_by_rpd, self.batch_size_current)
        
        return int(suggested_size)

# Função utilitária para importação
def create_rate_limiter():
    """Cria instância do rate limiter com configurações padrão"""
    return RateLimiterOtimizado()

# Teste básico
if __name__ == "__main__":
    import pandas as pd
    
    print("🚀 Testando Rate Limiter Otimizado")
    
    # Criar rate limiter
    limiter = RateLimiterOtimizado()
    
    # Simular textos
    textos_teste = [
        "Trompete em Bb com 3 pistos, acabamento dourado",
        "Caixa de som ativa 15 polegadas 400W RMS",
        "Baqueta de madeira para bateria, ponta de nylon"
    ]
    
    # Testar estimativa de tokens
    tokens = limiter.estimate_tokens_precise(textos_teste)
    print(f"Tokens estimados: {tokens}")
    
    # Testar verificação de limites
    can_proceed = limiter.can_make_request(textos_teste)
    print(f"Pode prosseguir: {can_proceed}")
    
    # Simular solicitação
    if can_proceed is True:
        limiter.record_request(textos_teste, success=True)
        print("Solicitação registrada com sucesso")
    
    # Mostrar estatísticas
    stats = limiter.get_statistics()
    print(f"Estatísticas: {json.dumps(stats, indent=2, default=str)}")
    
    print("✅ Teste concluído")

