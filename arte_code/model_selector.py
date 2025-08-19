from __future__ import annotations

from typing import Dict, List


def get_model_chain_for_budget(priority: str = "free_tier") -> List[str]:
    chains: Dict[str, List[str]] = {
        "free_tier": [
            "gemini-2.5-flash-lite",
            "gemini-2.5-flash",
            "gemini-2.0-flash-lite",
            "gemini-2.0-flash",
            "gemini-1.5-flash",
        ],
        "balanced": [
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
        ],
        "quality": [
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.0-flash",
        ],
    }
    return chains.get(priority, chains["free_tier"]) 

