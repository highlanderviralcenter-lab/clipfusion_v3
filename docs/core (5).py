"""ClipFusion — Anti-Copyright Engine Core."""
import hashlib, shutil, subprocess, tempfile, os
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Callable, Dict


class ProtectionLevel(Enum):
    NONE    = "none"
    BASIC   = "basic"
    ANTI_AI = "anti_ai"
    MAXIMUM = "maximum"


@dataclass
class ProtectionConfig:
    level:          ProtectionLevel
    geometric:      bool = False
    color:          bool = False
    noise:          bool = False
    chroma:         bool = False
    frequency:      bool = False
    temporal:       bool = False
    ai_evasion:     bool = False
    audio_basic:    bool = False
    audio_advanced: bool = False
    network:        bool = False
    metadata:       bool = False

    @classmethod
    def from_level(cls, level: ProtectionLevel) -> "ProtectionConfig":
        return {
            ProtectionLevel.NONE: cls(level=level),
            ProtectionLevel.BASIC: cls(
                level=level, geometric=True, color=True,
                temporal=True, audio_basic=True, metadata=True),
            ProtectionLevel.ANTI_AI: cls(
                level=level, geometric=True, color=True, noise=True, chroma=True,
                temporal=True, ai_evasion=True, audio_basic=True, network=True, metadata=True),
            ProtectionLevel.MAXIMUM: cls(
                level=level, geometric=True, color=True, noise=True, chroma=True,
                frequency=True, temporal=True, ai_evasion=True,
                audio_basic=True, audio_advanced=True, network=True, metadata=True),
        }.get(level, cls(level=ProtectionLevel.NONE))


LEVEL_LABELS = {
    "none":    "🟢 NENHUM — arquivo original intacto",
    "basic":   "🟡 BÁSICO — zoom, cor, metadados, áudio",
    "anti_ai": "🟠 ANTI-IA — + noise, chroma, anti-detecção IA",
    "maximum": "🔴 MÁXIMO — todas as técnicas avançadas",
}


class AntiCopyrightEngine:
    def __init__(self, project_id: str, cut_index: int = 0,
                 config: Optional[ProtectionConfig] = None,
                 log: Optional[Callable] = None):
        self.project_id = project_id
        self.cut_index  = cut_index
        self.config     = config or ProtectionConfig.from_level(ProtectionLevel.BASIC)
        self.log        = log or print
        self.seed       = int(hashlib.md5(
            f"{project_id}_{cut_index}".encode()).hexdigest()[:8], 16)
        self.report: Dict = {
            "project_id": project_id, "cut_index": cut_index,
            "level": self.config.level.value, "seed": self.seed,
            "techniques_applied": [],
        }

    def process(self, input_path: str, output_path: str) -> Dict:
        if self.config.level == ProtectionLevel.NONE:
            shutil.copy2(input_path, output_path)
            return self.report
        tmp = tempfile.mkdtemp()
        try:
            current = input_path
            vf = self._collect_video_filters()
            if vf:
                out1 = os.path.join(tmp, "v1.mp4")
                self._run_vf(current, out1, vf)
                current = out1
            if self.config.audio_basic or self.config.audio_advanced:
                out2 = os.path.join(tmp, "v2.mp4")
                from anti_copy_modules.audio_advanced import AudioProcessor
                ok = AudioProcessor(self.seed).process(
                    current, out2,
                    basic=self.config.audio_basic, advanced=self.config.audio_advanced,
                    log=self.log)
                if ok:
                    current = out2
                    self.report["techniques_applied"].append("audio")
            if self.config.metadata:
                out3 = os.path.join(tmp, "v3.mp4")
                from anti_copy_modules.fingerprint_evasion import FingerprintEvasion
                meta = FingerprintEvasion(self.seed).metadata_inject_args(self.project_id)
                r = subprocess.run(
                    ["ffmpeg", "-y", "-i", current,
                     "-map_metadata", "-1", *meta, "-c", "copy", out3],
                    capture_output=True, text=True)
                if r.returncode == 0:
                    current = out3
                    self.report["techniques_applied"].append("metadata")
            shutil.copy2(current, output_path)
            self.log(f"ACE ✅ {len(self.report['techniques_applied'])} técnicas [{self.config.level.value}]")
        except Exception as e:
            self.log(f"ACE ⚠️ erro: {e}")
            shutil.copy2(input_path, output_path)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        return self.report

    def _collect_video_filters(self) -> list:
        filters = []
        is_max  = self.config.level == ProtectionLevel.MAXIMUM
        is_anti = self.config.level in (ProtectionLevel.ANTI_AI, ProtectionLevel.MAXIMUM)
        if self.config.geometric:
            from anti_copy_modules.geometric_transforms import GeometricTransforms
            filters += GeometricTransforms(self.seed).ffmpeg_filters(is_anti, is_max)
            self.report["techniques_applied"].append("geometric")
        if self.config.color:
            from anti_copy_modules.fingerprint_evasion import FingerprintEvasion
            filters += FingerprintEvasion(self.seed).color_filters()
            self.report["techniques_applied"].append("color")
        if self.config.noise:
            from anti_copy_modules.fingerprint_evasion import FingerprintEvasion
            filters += FingerprintEvasion(self.seed).noise_filters()
            self.report["techniques_applied"].append("noise")
        if self.config.chroma:
            from anti_copy_modules.fingerprint_evasion import FingerprintEvasion
            filters += FingerprintEvasion(self.seed).chroma_filters()
            self.report["techniques_applied"].append("chroma")
        if self.config.frequency:
            from anti_copy_modules.fingerprint_evasion import FingerprintEvasion
            filters += FingerprintEvasion(self.seed).frequency_filters()
            self.report["techniques_applied"].append("frequency")
        if self.config.temporal:
            from anti_copy_modules.temporal_obfuscation import TemporalObfuscation
            filters += TemporalObfuscation(self.seed).ffmpeg_filters()
            self.report["techniques_applied"].append("temporal")
        if self.config.ai_evasion:
            from anti_copy_modules.ai_evasion import AIEvasion
            filters += AIEvasion(self.seed).ffmpeg_filters()
            self.report["techniques_applied"].append("ai_evasion")
        return filters

    def _run_vf(self, inp: str, out: str, filters: list):
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", inp, "-vf", ",".join(filters),
             "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-c:a", "copy", out],
            capture_output=True, text=True)
        if r.returncode != 0:
            shutil.copy2(inp, out)
