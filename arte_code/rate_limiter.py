#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rate limiter otimizado para uso com Google Gemini (ou APIs similares).

Baseado na versão em `tests/AGENTE_ORCAMENTO/JINA/rate_limiter_otimizado.py`,
adaptado para uso como módulo reutilizável dentro de `arte_code`.
"""

from __future__ import annotations

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Union
import re


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class RateLimiterOtimizado:
    """Rate limiter inteligente para APIs com batches adaptativos"""

    def __init__(self, rpm: int = 30, tpm: int = 1_000_000, rpd: int = 200, batch_size_default: int = 200) -> None:
        self.rpm = rpm
        self.tpm = tpm
        self.rpd = rpd

        self.batch_size_default = batch_size_default
        self.batch_size_current = batch_size_default
        self.batch_size_min = 5
        self.batch_size_max = 50

        self.requests_in_minute: List[datetime] = []
        self.tokens_in_minute: List[Tuple[datetime, int]] = []
        self.requests_in_day: List[datetime] = []

        self.day_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self.last_request_time: datetime | None = None

        self.total_requests = 0
        self.total_tokens = 0
        self.total_errors = 0

        logger.info(
            "Rate Limiter inicializado: RPM=%d, TPM=%d, RPD=%d, Batch=%d",
            rpm,
            tpm,
            rpd,
            batch_size_default,
        )

    def estimate_tokens_precise(self, texts: List[str]) -> int:
        if not texts:
            return 0

        total_tokens = 0
        for text in texts:
            if not text:
                continue
            text_str = str(text)

            base_tokens = int(len(text_str) / 3.5)

            if any(term in text_str.upper() for term in ["ESPECIFICAÇÕES", "TÉCNICO", "INSTRUMENTO", "EDITAL", "FORNECEDOR"]):
                base_tokens = int(base_tokens * 1.2)

            if '{' in text_str or '[' in text_str:
                base_tokens = int(base_tokens * 1.3)

            numbers = len(re.findall(r"\d+", text_str))
            base_tokens += int(numbers * 0.5)

            punctuation = len(re.findall(r"[,;:.!?()[\]{}\"]", text_str))
            base_tokens += int(punctuation * 0.2)

            total_tokens += base_tokens

        total_tokens = int(total_tokens * 1.2)
        total_tokens = max(total_tokens, len([t for t in texts if t]) * 10)
        return total_tokens

    def _clean_old_records(self, now: datetime) -> None:
        if now >= self.day_start + timedelta(days=1):
            self.day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            self.requests_in_day = []

        minute_ago = now - timedelta(minutes=1)
        self.requests_in_minute = [t for t in self.requests_in_minute if t > minute_ago]
        self.tokens_in_minute = [(t, tokens) for t, tokens in self.tokens_in_minute if t > minute_ago]

    def get_current_limits_status(self) -> Dict[str, Dict[str, int]]:
        now = datetime.now()
        self._clean_old_records(now)

        current_rpm = len(self.requests_in_minute)
        current_tpm = sum(tokens for _, tokens in self.tokens_in_minute)
        current_rpd = len(self.requests_in_day)

        available_rpm = self.rpm - current_rpm
        available_tpm = self.tpm - current_tpm
        available_rpd = self.rpd - current_rpd

        return {
            'rpm': {'current': current_rpm, 'limit': self.rpm, 'available': available_rpm},
            'tpm': {'current': current_tpm, 'limit': self.tpm, 'available': available_tpm},
            'rpd': {'current': current_rpd, 'limit': self.rpd, 'available': available_rpd},
            'batch_size': self.batch_size_current,
        }

    def can_make_request(self, texts: List[str]) -> Union[bool, int]:
        now = datetime.now()
        self._clean_old_records(now)

        tokens_needed = self.estimate_tokens_precise(texts)
        status = self.get_current_limits_status()

        if status['rpd']['available'] <= 0:
            return False

        if status['rpm']['available'] <= 0:
            wait_time = 60 - (now - self.requests_in_minute[0]).total_seconds()
            return int(wait_time) + 1

        if tokens_needed > status['tpm']['available']:
            if self.tokens_in_minute:
                wait_time = 60 - (now - self.tokens_in_minute[0][0]).total_seconds()
                return int(wait_time) + 1
            else:
                return False

        return True

    def wait_if_needed(self, texts: List[str]) -> bool:
        max_retries = 3
        retry_count = 0
        while retry_count < max_retries:
            can_proceed = self.can_make_request(texts)
            if can_proceed is True:
                return True
            elif can_proceed is False:
                return False
            else:
                time.sleep(int(can_proceed))
                retry_count += 1
        return False

    def record_request(self, texts: List[str], success: bool = True) -> None:
        now = datetime.now()
        tokens_used = self.estimate_tokens_precise(texts)

        if success:
            self.requests_in_minute.append(now)
            self.tokens_in_minute.append((now, tokens_used))
            self.requests_in_day.append(now)
            self.total_requests += 1
            self.total_tokens += tokens_used
        else:
            self.total_errors += 1
        self.last_request_time = now


def create_rate_limiter() -> RateLimiterOtimizado:
    return RateLimiterOtimizado()

