import random
import hashlib
import os
import subprocess
import tempfile
import shutil
from dataclasses import dataclass
from typing import Dict, Optional
from enum import Enum

class ProtectionLevel(Enum):
    NONE = "none"
    BASIC = "basic"
    ANTI_AI = "anti_ai"
    MAXIMUM = "maximum"

@dataclass
class ProtectionConfig:
    level: ProtectionLevel
    geometric: bool = False
    color: bool = False
    temporal: bool = False
    audio_basic: bool = False
    audio_advanced: bool = False
    ai_evasion: bool = False
    network: bool = False
    metadata: bool = False
    noise: bool = False
    chroma: bool = False
    flip: bool = False

    @classmethod
    def from_level(cls, level: ProtectionLevel):
        configs = {
            ProtectionLevel.NONE: cls(level=level),
            ProtectionLevel.BASIC: cls(level=level, geometric=True, color=True, temporal=True, audio_basic=True, metadata=True),
            ProtectionLevel.ANTI_AI: cls(level=level, geometric=True, color=True, temporal=True, audio_basic=True, ai_evasion=True, network=True, metadata=True, noise=True, chroma=True),
            ProtectionLevel.MAXIMUM: cls(level=level, geometric=True, color=True, temporal=True, audio_basic=True, audio_advanced=True, ai_evasion=True, network=True, metadata=True, noise=True, chroma=True, flip=True),
        }
        return configs.get(level, cls(level=ProtectionLevel.BASIC))

LEVEL_LABELS = {
    "none": "🟢 NENHUM (Original)",
    "basic": "🟡 BÁSICO (7 Camadas)",
    "anti_ia": "🟠 ANTI-IA",
    "maximum": "🔴 MÁXIMO"
}

class AntiCopyrightEngine:
    def __init__(self, project_id: str, cut_index: int = 0, config: Optional[ProtectionConfig] = None, log=print):
        self.project_id = project_id
        self.cut_index = cut_index
        self.seed = int(hashlib.md5(f"{project_id}_{cut_index}".encode()).hexdigest()[:8], 16)
        self.config = config or ProtectionConfig.from_level(ProtectionLevel.BASIC)
        self.log = log
        self.report = {"project_id": project_id, "cut_index": cut_index, "protection_level": self.config.level.value, "techniques_applied": [], "estimates": {}}

    def process(self, input_path: str, output_path: str) -> Dict:
        if self.config.level == ProtectionLevel.NONE:
            shutil.copy2(input_path, output_path)
            self.report["techniques_applied"].append("none")
            return self.report

        tmpdir = tempfile.mkdtemp()
        try:
            current = input_path

            # Camada 1: Zoom
            if self.config.geometric:
                out = os.path.join(tmpdir, "geo.mp4")
                scale = 1.0 + random.uniform(0.01, 0.03)
                subprocess.run(["ffmpeg", "-y", "-i", current, "-vf", f"scale={scale}*iw:-2,crop=iw/{scale}:ih/{scale}:(iw-ow)/2:(ih-oh)/2", "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-c:a", "copy", out], capture_output=True)
                current = out
                self.report["techniques_applied"].append("zoom_1-3%")

            # Camada 2: Color
            if self.config.color:
                out = os.path.join(tmpdir, "color.mp4")
                bright = random.uniform(0.01, 0.03)
                subprocess.run(["ffmpeg", "-y", "-i", current, "-vf", f"eq=brightness={bright}:contrast=1.03:saturation=1.02", "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-c:a", "copy", out], capture_output=True)
                current = out
                self.report["techniques_applied"].append("colorimetria")

            # Camada 3: Metadata
            if self.config.metadata:
                out = os.path.join(tmpdir, "meta.mp4")
                subprocess.run(["ffmpeg", "-y", "-i", current, "-map_metadata", "-1", "-c:v", "copy", "-c:a", "copy", out], capture_output=True)
                current = out
                self.report["techniques_applied"].append("strip_metadata")

            # Camada 4: Audio
            if self.config.audio_basic:
                out = os.path.join(tmpdir, "audio.mp4")
                pitch = random.uniform(0.99, 1.01)
                subprocess.run(["ffmpeg", "-y", "-i", current, "-af", f"asetrate=44100*{pitch},atempo={1/pitch}", "-c:v", "copy", out], capture_output=True)
                current = out
                self.report["techniques_applied"].append("audio_pitch")

            # Camada 5: Noise (anti-IA)
            if self.config.noise:
                out = os.path.join(tmpdir, "noise.mp4")
                subprocess.run(["ffmpeg", "-y", "-i", current, "-vf", "noise=alls=2:allf=t+u", "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-c:a", "copy", out], capture_output=True)
                current = out
                self.report["techniques_applied"].append("ruido_anti_ia")

            # Camada 6: Temporal
            if self.config.temporal:
                out = os.path.join(tmpdir, "temp.mp4")
                factor = random.uniform(0.98, 1.02)
                subprocess.run(["ffmpeg", "-y", "-i", current, "-vf", f"setpts={factor}*PTS", "-af", f"atempo={1/factor}", "-c:v", "libx264", "-preset", "fast", "-crf", "18", out], capture_output=True)
                current = out
                self.report["techniques_applied"].append("ghost_mode")

            # Camada 7: Flip
            if self.config.flip:
                out = os.path.join(tmpdir, "flip.mp4")
                subprocess.run(["ffmpeg", "-y", "-i", current, "-vf", "hflip", "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-c:a", "copy", out], capture_output=True)
                current = out
                self.report["techniques_applied"].append("flip_horizontal")

            shutil.copy2(current, output_path)

        except Exception as e:
            self.log(f"Erro: {e}")
            shutil.copy2(input_path, output_path)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        self.report["estimates"] = {"level": "Máxima" if len(self.report["techniques_applied"]) > 5 else "Alta" if len(self.report["techniques_applied"]) > 3 else "Básica", "confidence": f"{min(len(self.report['techniques_applied']) * 15, 98)}%"}
        return self.report
