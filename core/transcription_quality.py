"""
Avalia a qualidade de uma transcrição.

Esta função calcula uma pontuação simples baseada no tamanho do
texto e na proporção de letras por caractere.  A pontuação varia
entre 0 e 1.
"""
import re

def score_transcription(text: str) -> float:
    if not text:
        return 0.0
    letters = len(re.findall(r"[A-Za-zÀ-ÿ]", text))
    total = len(text)
    return min(1.0, letters / total) if total > 0 else 0.0
