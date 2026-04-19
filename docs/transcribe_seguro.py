import gc
import subprocess
import tempfile
import os
from faster_whisper import WhisperModel
import db
from pydub import AudioSegment  # instale com: pip install pydub

class TranscriberSeguro:
    def __init__(self, model_size="small", device="cpu", compute_type="int8"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model = None

    def _load_model(self):
        if self.model is None:
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=4
            )

    def _extrair_audio(self, video_path, output_wav):
        subprocess.run([
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1", output_wav
        ], capture_output=True, check=True)

    def _dividir_audio(self, wav_path, duracao_chunk=30):
        """Divide o áudio em chunks de duracao_chunk segundos"""
        audio = AudioSegment.from_wav(wav_path)
        chunks = []
        for i, start in enumerate(range(0, len(audio), duracao_chunk * 1000)):
            chunk = audio[start:start + duracao_chunk * 1000]
            chunk_path = f"{wav_path}_chunk_{i}.wav"
            chunk.export(chunk_path, format="wav")
            chunks.append(chunk_path)
        return chunks

    def transcribe(self, audio_path, language=None):
        self._load_model()
        tmp = tempfile.mktemp(suffix=".wav")
        try:
            self._extrair_audio(audio_path, tmp)
            # Divide em chunks de 30s
            chunks = self._dividir_audio(tmp, duracao_chunk=30)
            todos_segmentos = []
            idioma = language or "pt"
            for chunk_path in chunks:
                segmentos, info = self.model.transcribe(
                    chunk_path,
                    language=idioma,
                    beam_size=3,
                    best_of=3,
                    condition_on_previous_text=False,
                    vad_filter=True,
                    vad_parameters={
                        "threshold": 0.5,
                        "min_speech_duration_ms": 250,
                        "max_speech_duration_s": 30,
                        "min_silence_duration_ms": 500
                    }
                )
                for s in segmentos:
                    todos_segmentos.append({
                        "start": round(s.start, 2),
                        "end": round(s.end, 2),
                        "text": s.text
                    })
                os.remove(chunk_path)
                gc.collect()
            return {
                "language": idioma,
                "segments": todos_segmentos,
                "full_text": " ".join(s["text"] for s in todos_segmentos),
            }
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    def cleanup(self):
        del self.model
        self.model = None
        gc.collect()

def transcribe_project(project_id, video_path, model_size="small", language="pt"):
    transcriber = TranscriberSeguro(model_size=model_size)
    result = transcriber.transcribe(video_path, language=language)
    transcript_id = db.save_transcript(project_id, result["full_text"], result["segments"])
    transcriber.cleanup()
    return transcript_id, result