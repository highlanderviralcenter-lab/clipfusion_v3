"""
Ponto de entrada da linha de comando para o ClipFusion V3.

Este módulo utiliza argparse para expor comandos de processamento,
transcrição, segmentação e execução da fila.  É um wrapper simples
para as chamadas nos módulos de core.
"""
import argparse
import json
from pathlib import Path

from ..infra.db import create_project, enqueue_job, list_projects
from ..core.transcriber import WhisperTranscriber
from ..core.segment import segment_by_pauses
from ..core.decision_engine import evaluate_decision
from ..core.transcription_quality import score_transcription
from ..anti_copy_modules.protection_factory import build_plan
from ..core.cut_engine import render_cut


def cmd_transcribe(args):
    transcriber = WhisperTranscriber()
    result = transcriber.transcribe(args.input)
    print(result.get("text", ""))

def cmd_segment(args):
    segments = segment_by_pauses(args.input)
    for s, e in segments:
        print(f"{s:.2f}\t{e:.2f}")

def cmd_process(args):
    project_id = create_project(Path(args.input).stem, args.input)
    print(f"Projeto criado com ID {project_id}")
    # Transcreve
    transcriber = WhisperTranscriber()
    result = transcriber.transcribe(args.input)
    text = result.get("text", "")
    # Segmenta
    segments = segment_by_pauses(args.input)
    # Para cada segmento, renderiza um corte simples
    plan = build_plan(args.protection)
    for idx, (s, e) in enumerate(segments[:2]):
        out_path = f"{Path(args.input).stem}_cut_{idx+1}.mp4"
        render_cut(args.input, s, e, text, plan, args.platform, out_path)
        print(f"Corte gerado: {out_path}")

def cmd_list(args):
    for p in list_projects():
        print(f"{p['id']}\t{p['name']}\t{p['status']}")

def main():
    parser = argparse.ArgumentParser(description="ClipFusion V3 CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_trans = sub.add_parser("transcribe", help="Transcreve um vídeo")
    p_trans.add_argument("input")
    p_trans.set_defaults(func=cmd_transcribe)
    p_seg = sub.add_parser("segment", help="Segmenta um vídeo")
    p_seg.add_argument("input")
    p_seg.set_defaults(func=cmd_segment)
    p_proc = sub.add_parser("process", help="Processa um vídeo completo")
    p_proc.add_argument("input")
    p_proc.add_argument("--protection", default="none", help="none|basic|anti_ia|maximum")
    p_proc.add_argument("--platform", default="tiktok", help="tiktok|reels|shorts")
    p_proc.set_defaults(func=cmd_process)
    p_list = sub.add_parser("list", help="Lista projetos")
    p_list.set_defaults(func=cmd_list)
    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
