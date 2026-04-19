"""
Módulo de segmentação para o ClipFusion V3.

A função `segment_by_pauses` divide a duração de um vídeo em segmentos
entre 18 e 35 segundos tentando maximizar a retenção.  Sem acesso a
informações de pausa, este fallback simplesmente cria segmentos de
duração variada entre estes limites.
"""
import subprocess
from typing import List, Tuple

def _get_duration(video_path: str) -> float:
    """Obtém a duração de um vídeo usando ffprobe.  Retorna 0 em caso de falha."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0

def segment_by_pauses(video_path: str, min_sec: int = 18, max_sec: int = 35) -> List[Tuple[float, float]]:
    """Divide o vídeo em segmentos de 18 a 35 segundos.

    Parameters
    ----------
    video_path: str
        Caminho para o vídeo.
    min_sec: int
        Duração mínima em segundos por segmento.
    max_sec: int
        Duração máxima em segundos por segmento.

    Returns
    -------
    List[Tuple[float, float]]
        Lista de tuplas (start, end) para cada segmento.
    """
    duration = _get_duration(video_path)
    if duration <= 0:
        return []
    segments = []
    start = 0.0
    toggle = True
    while start < duration:
        seg_len = max_sec if toggle else min_sec
        end = min(start + seg_len, duration)
        segments.append((start, end))
        start = end
        toggle = not toggle
    return segments
