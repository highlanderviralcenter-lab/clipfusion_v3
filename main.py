"""
CLI completo do ClipFusion V3.
"""
import argparse
import json
from pathlib import Path

from ..core.pipeline import Pipeline
from ..infra.db import list_projects


def main():
    parser = argparse.ArgumentParser(description="ClipFusion V3 — Transcrição Precisa + Corte Inteligente")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # Transcrever
    p_trans = sub.add_parser("transcribe", help="Transcreve um vídeo com word-level timestamps")
    p_trans.add_argument("input")
    p_trans.add_argument("--model", default="large-v3", choices=["large-v3", "large-v2", "medium", "small"])
    p_trans.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    p_trans.set_defaults(func=cmd_transcribe)

    # Pipeline completo
    p_proc = sub.add_parser("process", help="Pipeline completo: transcreve, segmenta e renderiza")
    p_proc.add_argument("input")
    p_proc.add_argument("--platform", default="tiktok", choices=["tiktok", "reels", "shorts"])
    p_proc.add_argument("--protection", default="basic", choices=["none", "basic", "anti_ia", "maximum"])
    p_proc.add_argument("--model", default="large-v3")
    p_proc.add_argument("--device", default="cuda")
    p_proc.add_argument("--max-cuts", type=int, default=5)
    p_proc.add_argument("--output", "-o", default=None)
    p_proc.set_defaults(func=cmd_process)

    # Listar
    p_list = sub.add_parser("list", help="Lista projetos no banco")
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args()
    args.func(args)


def cmd_transcribe(args):
    from ..core.audio_processor import AudioProcessor
    from ..core.transcriber import WhisperTranscriber
    
    print("🔧 Extraindo áudio...")
    audio = AudioProcessor()
    audio_path = audio.extract_and_clean(args.input)
    
    print(f"🧠 Transcrevendo com {args.model}...")
    trans = WhisperTranscriber(model_size=args.model, device=args.device)
    result = trans.transcribe(audio_path)
    result = trans.post_process_ptbr(result)
    
    print(f"\n📝 TEXTO:\n{result.text}\n")
    print(f"📊 Estatísticas:")
    print(f"   Palavras: {len(result.words)}")
    print(f"   Segmentos: {len(result.segments)}")
    print(f"\n⏱️ Primeiras 20 palavras com timestamps:")
    for w in result.words[:20]:
        print(f"   {w.start:>6.2f}s → {w.end:>6.2f}s  {w.word}")


def cmd_process(args):
    print(f"🚀 Iniciando pipeline completo...")
    pipe = Pipeline(model_size=args.model, device=args.device, on_progress=lambda m, p: print(f"[{p:>3.0f}%] {m}"))
    outputs = pipe.run(
        video_path=args.input,
        platform=args.platform,
        protection=args.protection,
        max_cuts=args.max_cuts,
        output_dir=args.output,
    )
    print(f"\n✅ Concluído! Arquivos gerados:")
    for o in outputs:
        print(f"   {o}")


def cmd_list(args):
    for p in list_projects():
        print(f"{p['id']}\t{p['name']}\t{p['status']}\t{p['created_at']}")


if __name__ == "__main__":
    main()
