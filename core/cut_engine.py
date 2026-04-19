"""
Engine de corte com 2-pass otimizado para Intel HD 520 (VA-API) + i5-6200U.
Passo 1: VA-API (decode hwupload + scale_vaapi para 9:16)
Passo 2: libx264 veryfast (legendas burn-in + proteções)
"""
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List

from .segment_engine import VideoSegment


def _detect_vaapi() -> bool:
    """Verifica se /dev/dri/renderD128 existe e i915 está carregado."""
    return os.path.exists("/dev/dri/renderD128") and os.path.isdir("/sys/module/i915")


def _to_srt_time(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hrs:02d}:{mins:02d}:{secs:06.3f}".replace(".", ",")


def _build_srt(text: str, start: float, end: float) -> str:
    """Gera SRT minimal para o trecho."""
    return f"1\n{_to_srt_time(start)} --> {_to_srt_time(end)}\n{text}\n\n"


def render_cut(
    video_path: str,
    segment: 'VideoSegment',  # ou tuple (start, end) se ainda usar o antigo
    plan: Dict[str, bool],
    platform: str,
    output_path: str,
) -> None:
    """
    Renderiza corte com pipeline 2-pass:
    1. VA-API: decode hwaccel + crop/scale para 1080x1920
    2. Software: burn-in de legendas + proteções + libx264 veryfast
    """
    # Casa se receber tuple antigo (start, end)
    if isinstance(segment, tuple):
        start, end = segment
        seg_text = ""
        seg_duration = end - start
    else:
        start = segment.start
        end = segment.end
        seg_text = segment.text
        seg_duration = end - start

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        mid_path = tmpdir / "pass1_vaapi.mp4"
        
        # ─── PASSO 1: VA-API (HD 520) ───
        # Aceleramcquim + scale para vertical (TikTok/Reels/Shorts)
        vaapi_available = _detect_vaapi()
        
        if vaapi_available:
            cmd_p1 = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-hwaccel", "vaapi",
                "-vaapi_device", "/dev/dri/renderD128",
                "-i", video_path,
                "-ss", str(start),
                "-t", str(seg_duration),
                # Filtros VA-API: converte para NV12, sobe para GPU, escala
                "-vf", "format=nv12|vaapi,hwupload,scale_vaapi=w=1080:h=1920",
                "-c:v", "h264_vaapi",
                "-qp", "24",           # qualidade VA-API (20-28)
                "-c:a", "copy",
                str(mid_path),
            ]
        else:
            # Fallback puro CPU se VA-API falhar (acho que nem)
            cmd_p1 = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-ss", str(start),
                "-i", video_path,
                "-t", str(seg_duration),
                "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                "-c:a", "copy",
                str(mid_path),
            ]
        
        subprocess.run(cmd_p1, check=True)
        
        # ─── PASSO 2: Software Overlay (i5-6200U) ───
        # Aplica legendas, proteções e re-encoda com libx264 veryfast
        
        # Monta filtros de proteção
        vf_parts = []
        
        # Básico: zoom 2% + crop para desviar hash
        if plan.get("geometric") or plan.get("basic"):
            vf_parts.append("zoompan=z='min(zoom+0.001,1.02)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'")
        
        # Cor: leve brilho/contraste
        if plan.get("color") or plan.get("basic"):
            vf_parts.append("eq=brightness=0.03:contrast=1.05:saturation=1.02")
        
        # Anti-IA: noise + chromashift
        if plan.get("noise") or plan.get("anti_ia"):
            vf_parts.append("noise=alls=4:allf=t+u")
        if plan.get("chroma") or plan.get("anti_ia"):
            vf_parts.append("chromashift=cbh=1.5:crv=1.5")
        
        # Máximo: flip horizontal (se solicitado explicitamente)
        if plan.get("flip") or plan.get("maximum"):
            vf_parts.append("hflip")
        
        # Legenda SRT burn-in
        if seg_text:
            srt_file = tmpdir / "subs.srt"
            with open(srt_file, "w", encoding="utf-8") as f:
                f.write(_build_srt(seg_text, 0.0, seg_duration))
            
            style = (
                "FontName=Arial,FontSize=26,"
                "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                "Outline=2,Shadow=0,Alignment=2,MarginV=50"
            )
            vf_parts.append(f"subtitles={srt_file}:force_style='{style}'")
        
        vf = ",".join(vf_parts) if vf_parts else "null"
        
        # Preset veryfast para não matar o i5-6200U (2 cores)
        # Se o vídeo for curto (<30s), pode usar faster
        preset = "veryfast"
        
        cmd_p2 = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(mid_path),
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", preset,
            "-crf", "22",          # qualidade final
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",  # áudio re-encode leve
            "-movflags", "+faststart",
            output_path,
        ]
        
        subprocess.run(cmd_p2, check=True)
        
        # Cleanup temporários automático pelo TemporaryDirectory


def batch_render(
    video_path: str,
    segments: List,
    plan: Dict[str, bool],
    platform: str,
    output_prefix: str,
) -> List[str]:
    """Renderiza múltiplos segmentos com reutilização de modelo."""
    outputs = []
    for idx, seg in enumerate(segments, 1):
        out = f"{output_prefix}_cut_{idx:02d}.mp4"
        render_cut(video_path, seg, plan, platform, out)
        outputs.append(out)
    return outputs
