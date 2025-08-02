import time
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self, rpm=30, tpm=1_000_000, rpd=200):
        self.rpm = rpm
        self.tpm = tpm
        self.rpd = rpd
        self.requests_in_minute = []
        self.tokens_in_minute = []
        self.requests_in_day = []
        self.day_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    def estimate_tokens(self, texts):
        """Estima tokens para uma lista de textos (1 token ≈ 4 caracteres)"""
        return sum(len(text) // 4 + 1 for text in texts if text)

    def can_make_request(self, texts):
        """Verifica se a solicitação em batch pode ser feita"""
        now = datetime.now()
        tokens = self.estimate_tokens(texts)

        # Atualizar janela de um dia
        if now >= self.day_start + timedelta(days=1):
            self.day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            self.requests_in_day = []
            logger.info("Janela diária reiniciada.")

        # Verificar limite diário (RPD)
        if len(self.requests_in_day) >= self.rpd:
            logger.error("Limite diário de %d solicitações atingido.", self.rpd)
            return False

        # Atualizar janela de um minuto
        self.requests_in_minute = [t for t in self.requests_in_minute if now - t < timedelta(minutes=1)]
        self.tokens_in_minute = [t for t in self.tokens_in_minute if now - t[0] < timedelta(minutes=1)]

        # Verificar limite por minuto (RPM e TPM)
        if len(self.requests_in_minute) >= self.rpm:
            wait_time = 60 - (now - self.requests_in_minute[0]).total_seconds()
            logger.info("Limite de RPM atingido. Aguardando %.2f segundos.", wait_time)
            time.sleep(wait_time)
            self.requests_in_minute = []
            self.tokens_in_minute = []

        total_tokens = sum(t[1] for t in self.tokens_in_minute)
        if total_tokens + tokens > self.tpm:
            wait_time = 60 - (now - self.tokens_in_minute[0][0]).total_seconds()
            logger.info("Limite de TPM atingido. Aguardando %.2f segundos.", wait_time)
            time.sleep(wait_time)
            self.tokens_in_minute = []

        return True

    def record_request(self, texts):
        """Registra uma solicitação em batch bem-sucedida"""
        now = datetime.now()
        tokens = self.estimate_tokens(texts)
        self.requests_in_minute.append(now)
        self.tokens_in_minute.append((now, tokens))
        self.requests_in_day.append(now)
        logger.debug("Solicitação em batch registrada: %d RPM, %d TPM, %d RPD", 
                     len(self.requests_in_minute), sum(t[1] for t in self.tokens_in_minute), len(self.requests_in_day))