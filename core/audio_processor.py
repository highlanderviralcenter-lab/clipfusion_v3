"""
Processador de áudio para ClipFusion V3.
Extrai, limpa e prepara áudio para transcrição de alta precisão.
"""
import os
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Tuple
import numpy as np
import soundfile as sf

class AudioProcessor:
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate

    def extract_and_clean(
        self,
        video_path: str,
        apply_denoise: bool = True,
        apply_vad: bool = True,
        target_lufs: float = -14.0,
    ) -> str:
        """
        Extrai áudio do vídeo, aplica filtros FFmpeg (highpass, loudnorm, afftdn),
        denoising Python opcional e VAD Silero.
        Retorna path do WAV final pronto para Whisper.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Passo 1: Extração bruta com filtros FFmpeg essenciais
            raw_wav = tmpdir / "raw.wav"
            filters = (
                f"highpass=f=80,lowpass=f=8000,"
                f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11,"
                f"afftdn=nf=-25"
            )
            cmd = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", video_path,
                "-vn",
                "-af", filters,
                "-ar", str(self.sample_rate),
                "-ac", "1",
                "-c:a", "pcm_s16le",
                str(raw_wav),
            ]
            subprocess.run(cmd, check=True)

            # Passo 2: Carrega para numpy
            audio, sr = sf.read(str(raw_wav))
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            if sr != self.sample_rate:
                # resample se necessário
                import librosa
                audio = librosa.resample(audio, orig_sr=sr, target_sr=self.sample_rate)

            # Passo 3: Denoising avançado (noisereduce)
            if apply_denoise:
                try:
                    import noisereduce as nr
                    # Estima ruído dos primeiros 0.5s
                    noise_sample = audio[: int(self.sample_rate * 0.5)]
                    audio = nr.reduce_noise(y=audio, sr=self.sample_rate, y_noise=noise_sample, prop_decrease=0.85)
                except Exception as e:
                    print(f"[AudioProcessor] Denoising pulado: {e}")

            # Passo 4: VAD Silero para remover silêncios longos
            if apply_vad:
                audio = self._apply_silero_vad(audio)

            # Passo 5: Salva final
            final_wav = tmpdir / "clean.wav"
            sf.write(str(final_wav), audio, self.sample_rate)
            
            # Precisamos persistir fora do tempdir
            out_path = os.path.join(tempfile.gettempdir(), f"cf3_clean_{os.path.basename(video_path)}.wav")
            os.replace(str(final_wav), out_path)
            return out_path

    def _apply_silero_vad(self, audio: np.ndarray, threshold: float = 0.5) -> np.ndarray:
        """Aplica Silero VAD e mantém apenas trechos com fala."""
        try:
            import torch
            from silero_vad import load_silero_vad, get_speech_timestamps
            
            model = load_silero_vad()
            # Silero espera float32
            tensor = torch.from_numpy(audio.astype(np.float32))
            speech_timestamps = get_speech_timestamps(
                tensor, model, sampling_rate=self.sample_rate, threshold=threshold
            )
            if not speech_timestamps:
                return audio
            
            chunks = []
            for ts in speech_timestamps:
                start = ts["start"]
                end = ts["end"]
                chunks.append(audio[start:end])
            
            # Adiciona 0.3s de silêncio entre chunks para não grudar palavras
            padding = np.zeros(int(self.sample_rate * 0.3), dtype=audio.dtype)
            result = []
            for i, chunk in enumerate(chunks):
                result.append(chunk)
                if i < len(chunks) - 1:
                    result.append(padding)
            return np.concatenate(result)
        except Exception as e:
            print(f"[AudioProcessor] VAD pulado: {e}")
            return audio

    def get_duration(self, video_path: str) -> float:
        """Retorna duração em segundos."""
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", video_path],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            return float(result.stdout.strip())
        except Exception:
            return 0.0
