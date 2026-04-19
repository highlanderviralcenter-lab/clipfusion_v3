"""
Pipeline completo do ClipFusion V3.
Orquestra: pré-processamento → transcrição → segmentação → scoring → renderização.
"""
import os
import json
from pathlib import Path
from typing import List, Optional, Callable

from infra.db import (
    create_project, save_transcription, save_candidate, save_cut,
    update_cut_status, update_cut_output
)
from .audio_processor import AudioProcessor
from .transcriber import WhisperTranscriber, TranscriptionResult
from .segment_engine import SegmentEngine, VideoSegment
from .cut_engine import render_cut
from .decision_engine import evaluate_decision
from ..anti_copy_modules.protection_factory import build_plan


class Pipeline:
    def __init__(
        self,
        model_size: str = "large-v3",
        device: str = "cuda",
        on_progress: Optional[Callable[[str, float], None]] = None,
    ):
        self.audio_proc = AudioProcessor()
        self.transcriber = WhisperTranscriber(model_size=model_size, device=device)
        self.segment_engine = SegmentEngine()
        self.on_progress = on_progress or (lambda msg, pct: print(f"[{pct:.0f}%] {msg}"))

    def run(
        self,
        video_path: str,
        platform: str = "tiktok",
        protection: str = "basic",
        max_cuts: int = 5,
        output_dir: Optional[str] = None,
    ) -> List[str]:
        """
        Executa pipeline completo e retorna lista de arquivos gerados.
        """
        video_path = str(Path(video_path).resolve())
        base_name = Path(video_path).stem
        out_dir = Path(output_dir or f"./clipfusion_output_{base_name}")
        out_dir.mkdir(parents=True, exist_ok=True)

        # 1. Projeto
        self.on_progress("Criando projeto...", 5)
        project_id = create_project(base_name, video_path, language="pt")

        # 2. Áudio limpo
        self.on_progress("Extraindo e limpando áudio...", 15)
        audio_path = self.audio_proc.extract_and_clean(video_path)
        duration = self.audio_proc.get_duration(video_path)

        # 3. Transcrição
        self.on_progress("Transcrevendo com word-level timestamps...", 35)
        raw_result = self.transcriber.transcribe(audio_path)
        result = self.transcriber.post_process_ptbr(raw_result)
        
        # Salva transcrição
        save_transcription(
            project_id=project_id,
            full_text=result.text,
            segments_json=json.dumps(result.to_dict(), ensure_ascii=False),
            quality_score=0.85 if result.words else 0.0,
        )

        # 4. Segmentação inteligente
        self.on_progress("Segmentando por conteúdo...", 55)
        segments = self.segment_engine.segment(result, platform=platform)
        
        # Limita e scoreia
        segments = segments[:max_cuts * 2]  # pega extras para filtrar
        
        # 5. Decision engine para rankear
        self.on_progress("Avaliando melhores cortes...", 70)
        candidates = []
        for seg in segments:
            score = evaluate_decision(
                local_score=seg.hook_score,
                external_score=seg.retention_score,
                platform_fit=seg.platform_fit.get(platform, 0.5),
                transcription_quality=0.85,
            )
            candidates.append((score, seg))
        
        candidates.sort(key=lambda x: x[0], reverse=True)
        top_candidates = candidates[:max_cuts]

        # 6. Renderização
        plan = build_plan(protection)
        outputs = []
        
        for idx, (score, seg) in enumerate(top_candidates, 1):
            progress = 75 + (idx / len(top_candidates)) * 25
            self.on_progress(f"Renderizando corte {idx}/{len(top_candidates)}...", progress)
            
            out_path = str(out_dir / f"{base_name}_cut_{idx:02d}_{platform}.mp4")
            
            # Salva candidate no banco
            candidate_id = save_candidate(
                project_id=project_id,
                transcript_id=project_id,  # simplificado
                start=seg.start,
                end=seg.end,
                text=seg.text,
                scores={
                    "hook_strength": seg.hook_score,
                    "retention_score": seg.retention_score,
                    "moment_strength": score,
                    "shareability": score * 0.9,
                    f"platform_fit_{platform}": seg.platform_fit.get(platform, 0.5),
                    "combined_score": score,
                }
            )
            
            cut_id = save_cut(project_id, candidate_id, out_path)
            update_cut_status(cut_id, "rendering")
            
            try:
                render_cut(video_path, seg, plan, platform, out_path)
                update_cut_status(cut_id, "done")
                update_cut_output(cut_id, out_path)
                outputs.append(out_path)
            except Exception as e:
                update_cut_status(cut_id, f"error: {e}")
                raise

        self.on_progress("Concluído!", 100)
        return outputs
