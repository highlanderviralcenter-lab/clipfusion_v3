"""
Engine de decisão para a Regra de Ouro.

Avalia um candidato com base em diferentes métricas: score local,
score externo, ajuste à plataforma e qualidade da transcrição.
As ponderações seguem a fórmula: 0.5*local + 0.3*external + 0.1*platform_fit + 0.1*transcription_quality.
"""

def evaluate_decision(local_score: float, external_score: float, platform_fit: float, transcription_quality: float) -> float:
    return 0.5 * local_score + 0.3 * external_score + 0.1 * platform_fit + 0.1 * transcription_quality
