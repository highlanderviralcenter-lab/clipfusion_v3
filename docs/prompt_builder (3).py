"""ClipFusion — Prompt Builder para IA externa com janelas e reranking local."""

import json
import math
import re
from typing import Dict, Iterable, List, Optional, Tuple

from core.transcriber import fmt_time
from viral_engine.archetypes import ARCHETYPES

try:
    from viral_engine.viral_analyzer import ViralEngine
except Exception:
    ViralEngine = None


# Cache leve para permitir que parse_ai_response() reranque sem exigir
# mudanças imediatas na GUI.
_LAST_ANALYSIS_CONTEXT: Dict[str, object] = {
    "segments": [],
    "duration": 0.0,
    "windows": [],
}

HOOK_MARKERS = [
    "como",
    "por que",
    "ninguém",
    "segredo",
    "erro",
    "verdade",
    "olha",
    "escuta",
    "pare",
    "mas",
    "só que",
    "o problema",
    "o que ninguém",
    "isso aqui",
    "vou te mostrar",
    "presta atenção",
    "não faça",
    "antes de",
]

EMOTION_MARKERS = [
    "medo",
    "choque",
    "urgente",
    "perigo",
    "surpresa",
    "revelação",
    "resultado",
    "dinheiro",
    "erro",
    "venda",
    "cliente",
    "segredo",
    "impressionante",
    "ridículo",
    "verdade",
    "ninguém",
]

PLATFORMS = ("tiktok", "reels", "shorts")


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _slice_segments(segments: List[dict], start: float, end: float) -> List[dict]:
    return [s for s in segments if float(s.get("end", 0)) >= start and float(s.get("start", 0)) <= end]


def _window_text(segments: List[dict], start: float, end: float) -> str:
    sliced = _slice_segments(segments, start, end)
    return _normalize_space(" ".join(str(s.get("text", "")).strip() for s in sliced))


def _window_transcript_lines(segments: List[dict], start: float, end: float, max_chars: int = 1400) -> str:
    lines: List[str] = []
    total = 0
    for s in _slice_segments(segments, start, end):
        line = f"[{fmt_time(float(s.get('start', 0)))}] {str(s.get('text', '')).strip()}"
        total += len(line) + 1
        if total > max_chars:
            lines.append("...(janela truncada)")
            break
        lines.append(line)
    return "\n".join(lines)


def _duration_bonus(duration: float) -> float:
    if 22 <= duration <= 58:
        return 12.0
    if 15 <= duration <= 75:
        return 6.0
    if 12 <= duration <= 90:
        return 0.0
    return -10.0


def _hook_score(text: str) -> float:
    opener = _normalize_space(text).lower()
    first_words = " ".join(opener.split()[:16])

    score = 0.0
    score += sum(1.8 for marker in HOOK_MARKERS if marker in first_words)
    score += 3.0 if "?" in first_words else 0.0
    score += 2.0 if re.search(r"\b(3|5|7|10|90|100)\b", first_words) else 0.0
    score += 1.5 if re.search(r"\b(não|nunca|jamais|pare)\b", first_words) else 0.0
    return score


def _emotion_score(text: str) -> float:
    lower = _normalize_space(text).lower()
    return sum(1.0 for marker in EMOTION_MARKERS if marker in lower[:700])


def _density_score(text: str, duration: float) -> float:
    if duration <= 0:
        return -5.0
    density = len(text.split()) / duration
    if 1.6 <= density <= 3.7:
        return 6.0
    if 1.1 <= density <= 4.2:
        return 2.0
    return -3.0


def _viral_engine_score(text: str, duration: float) -> Dict[str, float]:
    base = {
        "viral_score": 0.0,
        "retention_score": 0.0,
        "shareability": 0.0,
        "commentability": 0.0,
    }
    if ViralEngine is None:
        return base

    try:
        engine = ViralEngine()
    except Exception:
        return base

    # Tenta vários nomes de método para maximizar compatibilidade.
    method_names = ["score_cut", "analyze_cut", "score_text", "analyze_text"]
    for name in method_names:
        fn = getattr(engine, name, None)
        if not callable(fn):
            continue
        try:
            payload = fn(text, duration)  # assinatura preferida
        except TypeError:
            try:
                payload = fn(text)
            except Exception:
                continue
        except Exception:
            continue

        if isinstance(payload, dict):
            for k in list(base.keys()):
                try:
                    if k in payload:
                        base[k] = float(payload.get(k, 0.0) or 0.0)
                except Exception:
                    pass
            return base

    return base


def _compute_local_metrics(text: str, duration: float) -> Dict[str, float]:
    ve = _viral_engine_score(text, duration)
    hook = _hook_score(text)
    emotion = _emotion_score(text)
    density = _density_score(text, duration)
    duration_adj = _duration_bonus(duration)

    local_score = (
        ve["viral_score"] * 0.40
        + ve["retention_score"] * 0.25
        + ve["shareability"] * 0.15
        + ve["commentability"] * 0.10
        + hook
        + emotion
        + density
        + duration_adj
    )

    return {
        "local_score": round(local_score, 2),
        "viral_score": round(float(ve["viral_score"]), 2),
        "retention_score": round(float(ve["retention_score"]), 2),
        "shareability": round(float(ve["shareability"]), 2),
        "commentability": round(float(ve["commentability"]), 2),
    }


def _build_windows(segments: List[dict], duration: float, window_size: int = 55, step: int = 30) -> List[dict]:
    if not segments:
        return []

    if duration <= 0:
        duration = float(segments[-1].get("end", 0.0) or 0.0)

    windows: List[dict] = []
    start = 0.0
    idx = 0

    while start < max(duration, 1):
        end = min(float(duration), start + window_size)
        text = _window_text(segments, start, end)
        if text:
            metrics = _compute_local_metrics(text, max(end - start, 0.1))
            windows.append(
                {
                    "id": f"W{idx:02d}",
                    "start": round(start, 2),
                    "end": round(end, 2),
                    "duration": round(end - start, 2),
                    "text": text,
                    "summary": _window_transcript_lines(segments, start, end, max_chars=1400),
                    **metrics,
                }
            )
        if end >= duration:
            break
        start += step
        idx += 1

    windows.sort(key=lambda w: (w["local_score"], -w["start"]), reverse=True)
    return windows


def _format_window_map(windows: List[dict], limit: int = 12) -> str:
    lines = []
    for w in windows[:limit]:
        lines.append(
            f"- {w['id']} | score {w['local_score']} | "
            f"{fmt_time(w['start'])}–{fmt_time(w['end'])} | "
            f"duração {int(round(w['duration']))}s"
        )
    return "\n".join(lines)


def _format_window_transcripts(windows: List[dict], limit: int = 8) -> str:
    blocks = []
    for w in windows[:limit]:
        blocks.append(
            f"### {w['id']} | score {w['local_score']} | "
            f"{fmt_time(w['start'])}–{fmt_time(w['end'])}\n{w['summary']}"
        )
    return "\n\n".join(blocks)


def build_analysis_prompt(segments: list, duration: float, context: str = "") -> str:
    """
    Gera um prompt mais robusto:
    - cria janelas espalhadas pelo vídeo todo
    - prioriza janelas fortes por score local
    - guarda contexto para reranking posterior em parse_ai_response()
    """
    windows = _build_windows(segments, duration)
    _LAST_ANALYSIS_CONTEXT["segments"] = list(segments or [])
    _LAST_ANALYSIS_CONTEXT["duration"] = float(duration or 0.0)
    _LAST_ANALYSIS_CONTEXT["windows"] = list(windows)

    arch_block = "\n".join(
        f"- {k}: {v['emocao']} — {v['descricao']}"
        for k, v in ARCHETYPES.items()
    )
    ctx = f"\n## CONTEXTO\n{context.strip()}\n" if (context or "").strip() else ""

    return f"""Você é especialista em engenharia de retenção e viralização de conteúdo curto.{ctx}
## DURAÇÃO TOTAL
{fmt_time(duration)}

## OBJETIVO
Encontrar de 3 a 8 cortes realmente fortes para vídeo curto vertical.
Você DEVE analisar o vídeo inteiro de forma distribuída, não só o começo.
Priorize:
- gancho forte nos primeiros 1–3s;
- promessa clara, conflito, surpresa, contraste, utilidade ou revelação;
- cortes entre 15s e 75s, preferencialmente 20s–60s;
- linguagem com potencial de comentário, compartilhamento e retenção.

## MAPA DE JANELAS PRIORITÁRIAS
{_format_window_map(windows, limit=12)}

## TRANSCRIÇÃO POR JANELAS PRIORITÁRIAS
{_format_window_transcripts(windows, limit=8)}

## ARQUÉTIPOS DISPONÍVEIS
{arch_block}

## PLATAFORMAS
- tiktok: vertical 9:16, ideal 30–60s, máx 180s
- reels: vertical 9:16, ideal 15–60s, máx 90s
- shorts: vertical 9:16, máx 60s

## TAREFA
Retorne somente os melhores cortes.
Você pode escolher trechos dentro das janelas acima ou combinar partes adjacentes,
mas os timestamps devem ser exatos.
Evite cortes redundantes, mornos ou que demoram para “entrar”.

## RESPOSTA — SOMENTE JSON, SEM MARKDOWN
{{
  "cortes": [
    {{
      "titulo": "título (máx 60 chars)",
      "start": 123.4,
      "end": 187.2,
      "archetype": "05_revelacao",
      "hook": "o que prende nos primeiros 3 segundos",
      "reason": "por que vai viralizar (2 frases)",
      "platforms": ["tiktok", "reels", "shorts"],
      "metadata": {{
        "titulo_post": "título para publicação",
        "descricao": "2–3 frases",
        "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"]
      }}
    }}
  ]
}}

Analise agora:"""


def _extract_json_block(text: str) -> dict:
    cleaned = re.sub(r"```json\s*|```\s*", "", (text or "").strip(), flags=re.I)
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        raise ValueError("Nenhum JSON encontrado.")
    return json.loads(match.group())


def _safe_float(value, default=0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _clean_platforms(value) -> List[str]:
    if isinstance(value, (list, tuple)):
        items = [str(v).strip().lower() for v in value if str(v).strip()]
    elif value:
        items = [str(value).strip().lower()]
    else:
        items = []

    filtered = [p for p in items if p in PLATFORMS]
    return filtered or list(PLATFORMS)


def _find_source_window(start: float, end: float, windows: List[dict]) -> str:
    best_id = ""
    best_overlap = -1.0
    for w in windows:
        overlap = max(0.0, min(end, w["end"]) - max(start, w["start"]))
        if overlap > best_overlap:
            best_overlap = overlap
            best_id = str(w["id"])
    return best_id


def _normalize_cut_payload(cut: dict, idx: int, duration_limit: float) -> Optional[dict]:
    start = _safe_float(cut.get("start", cut.get("inicio", 0)))
    end = _safe_float(cut.get("end", cut.get("fim", 0)))
    if end <= start:
        return None

    if duration_limit > 0:
        start = max(0.0, min(start, duration_limit))
        end = max(0.0, min(end, duration_limit))

    duration = end - start
    if duration < 12 or duration > 90:
        return None

    metadata = cut.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}

    return {
        "cut_index": idx,
        "title": cut.get("titulo") or cut.get("title") or f"Corte {idx + 1}",
        "start": round(start, 2),
        "end": round(end, 2),
        "archetype": cut.get("archetype", "01_despertar"),
        "hook": cut.get("hook", ""),
        "reason": cut.get("reason", ""),
        "platforms": _clean_platforms(cut.get("platforms")),
        "metadata": metadata,
    }


def _overlap_ratio(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    inter = max(0.0, min(a_end, b_end) - max(a_start, b_start))
    if inter <= 0:
        return 0.0
    a_len = max(a_end - a_start, 0.0001)
    b_len = max(b_end - b_start, 0.0001)
    return inter / min(a_len, b_len)


def _dedupe_cuts(cuts: List[dict]) -> List[dict]:
    chosen: List[dict] = []
    for cut in sorted(cuts, key=lambda x: x.get("local_score", 0.0), reverse=True):
        redundant = False
        for kept in chosen:
            if _overlap_ratio(cut["start"], cut["end"], kept["start"], kept["end"]) >= 0.72:
                redundant = True
                break
        if not redundant:
            chosen.append(cut)
    return chosen


def parse_ai_response(text: str) -> list:
    payload = _extract_json_block(text)
    raw_cuts = payload.get("cortes", []) or []

    segments: List[dict] = list(_LAST_ANALYSIS_CONTEXT.get("segments", []) or [])
    duration_limit = float(_LAST_ANALYSIS_CONTEXT.get("duration", 0.0) or 0.0)
    windows: List[dict] = list(_LAST_ANALYSIS_CONTEXT.get("windows", []) or [])

    parsed: List[dict] = []
    for idx, raw in enumerate(raw_cuts):
        if not isinstance(raw, dict):
            continue

        cut = _normalize_cut_payload(raw, idx, duration_limit)
        if not cut:
            continue

        cut_text = _window_text(segments, cut["start"], cut["end"]) if segments else ""
        metrics = _compute_local_metrics(cut_text, cut["end"] - cut["start"]) if cut_text else {
            "local_score": 0.0,
            "viral_score": 0.0,
            "retention_score": 0.0,
            "shareability": 0.0,
            "commentability": 0.0,
        }

        cut["text"] = cut_text
        cut["source_window"] = _find_source_window(cut["start"], cut["end"], windows) if windows else ""
        cut["selection_version"] = "v2_windows_rerank"
        cut.update(metrics)
        parsed.append(cut)

    parsed = _dedupe_cuts(parsed)
    parsed.sort(key=lambda x: (x.get("local_score", 0.0), -x.get("start", 0.0)), reverse=True)

    for i, cut in enumerate(parsed):
        cut["cut_index"] = i

    return parsed
