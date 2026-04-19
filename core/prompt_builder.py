"""
Construtor de prompts para o ClipFusion V3.

Combina a detecção de idioma com uma amostragem de cobertura do
transcrito para formar um prompt informativo para a IA externa.
Inclui tratamento robusto da resposta para suportar tanto objetos
quanto arrays JSON.
"""
import json
import re
from typing import Any, Dict, List

def _detect_lang(text: str) -> str:
    """Detecção rudimentar de idioma baseado em caracteres."""
    if re.search(r"[\u0400-\u04FF]", text):
        return "ru"
    if re.search(r"[\u30A0-\u30FF]", text):
        return "ja"
    if re.search(r"[A-Za-z]", text):
        return "en"
    return "pt"

def _coverage_sample(text: str, length: int = 200) -> str:
    """Extrai uma amostra representativa do texto."""
    return text[:length] + ("..." if len(text) > length else "")

def lang_block(lang: str) -> str:
    return f"Idioma detectado: {lang.upper()}"

def coverage(text: str) -> str:
    return _coverage_sample(text)

def parse_ai_response(response: str) -> Any:
    """Analisa a resposta da IA tentando decodificar JSON."""
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        # tenta encontrar o primeiro bloco JSON no texto
        m = re.search(r"\{.*\}", response, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        # tenta array JSON
        m = re.search(r"\[.*\]", response, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        return response

