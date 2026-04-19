"""
Fábrica de configurações de proteção para o ClipFusion V3.

Esta função retorna um dicionário de flags indicando quais técnicas
devem ser aplicadas de acordo com o nível escolhido.
"""
from typing import Dict

def build_plan(level: str) -> Dict[str, bool]:
    level = (level or "none").lower()
    plans = {
        "none": {},
        "basic": {
            "geometric": True,
            "color": True,
            "temporal": True,
            "metadata": True,
        },
        "anti_ia": {
            "geometric": True,
            "color": True,
            "temporal": True,
            "metadata": True,
            "noise": True,
            "chroma": True,
        },
        "maximum": {
            "geometric": True,
            "color": True,
            "temporal": True,
            "metadata": True,
            "noise": True,
            "chroma": True,
            "flip": True,
            "audio_advanced": True,
        },
    }
    return plans.get(level, plans["basic"])
