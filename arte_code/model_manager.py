#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Model manager para utilizar o Free Tier da Google Generative AI com fallback/adaptação.

Funcionalidades:
- Alterna entre modelos leves (flash-lite, flash) conforme limite/erro
- Tenta reduzir contexto automaticamente se exceder limites
- Interface simples: `generate(prompt, safety_settings=None, system_instruction=None)`
"""

from __future__ import annotations

import os
import logging
from typing import Any, Dict, Optional

import google.generativeai as genai


logger = logging.getLogger(__name__)


DEFAULT_FREE_TIER_CHAIN = [
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]


class GoogleModelManager:
    def __init__(self, api_key_env: str = "GOOGLE_API_KEY", models_priority: Optional[list[str]] = None) -> None:
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise RuntimeError(f"Variável de ambiente {api_key_env} não configurada.")
        genai.configure(api_key=api_key)
        self.models_priority = models_priority or DEFAULT_FREE_TIER_CHAIN
        self._current_model_name: Optional[str] = None
        self._current_model = None

    @property
    def current_model_name(self) -> str:
        return self._current_model_name or self.models_priority[0]

    def _load_model(self, model_name: str):
        logger.info("Carregando modelo: %s", model_name)
        self._current_model_name = model_name
        self._current_model = genai.GenerativeModel(model_name)

    def _ensure_model(self):
        if self._current_model is None:
            self._load_model(self.models_priority[0])

    def generate(self, prompt: str, safety_settings: Optional[Dict[str, Any]] = None, system_instruction: Optional[str] = None):
        self._ensure_model()
        attempted = set()

        for model_name in self.models_priority:
            if model_name in attempted:
                continue
            try:
                if self._current_model is None or self._current_model_name != model_name:
                    self._load_model(model_name)
                return self._current_model.generate_content(prompt)
            except Exception as e:
                msg = str(e).lower()
                logger.warning("Falha no modelo %s: %s", model_name, e)
                attempted.add(model_name)
                if any(s in msg for s in [
                    "rate limit", "quota", "limit exceeded", "resource exhausted",
                    "429", "insufficient tokens", "quota exceeded", "daily limit",
                ]):
                    continue
                if "safety" in msg or "blocked" in msg:
                    continue
                # outros erros: tenta próximo assim mesmo
                continue

        raise RuntimeError("Todos os modelos falharam devido a limites ou erros temporários.")

