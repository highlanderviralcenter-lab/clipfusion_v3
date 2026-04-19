"""
Otimizador de plataformas para o ClipFusion V3.

Esta função calcula uma pontuação de ajuste da plataforma com base
em alguns parâmetros simples: duração e energia do conteúdo.  Para
cada plataforma, retornamos uma pontuação entre 0 e 100.
"""
def platform_fit_score(niche: str, duration: float, energy: float) -> dict:
    # Simples heurística: cortes curtos e alta energia vão melhor em TikTok; longos em Reels.
    scores = {}
    scores['tiktok'] = max(0, 100 - duration * 2 + energy * 10)
    scores['reels'] = max(0, 80 - duration + energy * 5)
    scores['shorts'] = max(0, 90 - duration * 1.5 + energy * 8)
    return scores
