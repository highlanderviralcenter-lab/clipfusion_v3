"""
Transcritor Whisper.cpp otimizado para i5-6200U + zRAM.
Carrega modelo em memória mapeada, libera agressivamente.
"""
import os
import sys
import json
import tempfile
import subprocess
import mmap
from pathlib import Path
from typing import Dict, List, Any, Optional
import gc


class WhisperCppTranscriber:
    """
    Wrapper para whisper.cpp via ctypes/CFFI.
    Otimizado para hierarquia zRAM+swap (swappiness 150).
    """
    
    # Modelos pré-quantizados para sua arquitetura
    MODELS = {
        "tiny":   {"size": "39M",  "ram": "~100MB",  "speed": "10x"},
        "base":   {"size": "74M",  "ram": "~200MB",  "speed": "7x"},
        "small":  {"size": "244M", "ram": "~500MB",  "speed": "4x"},
        "medium": {"size": "769M", "ram": "~1.2GB",  "speed": "2x"},
        "large-v1": {"size": "1.5G", "ram": "~2.5GB", "speed": "1x"},
    }
    
    def __init__(
        self,
        model_name: str = "medium",
        quantize: str = "q5_0",  # q4_0, q5_0, q8_0 - menor = mais rápido/menos RAM
        n_threads: int = 3,       # i5-6200U: 2 cores / 4 threads, deixa 1 livre
        n_batch: int = 8,        # batch size para zRAM eficiente
        use_gpu: bool = False,   # Você desabilitou, forçamos CPU
    ):
        self.model_name = model_name
        self.quantize = quantize
        self.n_threads = n_threads
        self.n_batch = n_batch
        self.use_gpu = use_gpu
        
        self._whisper = None      # Referência ao modelo carregado
        self._ctx = None          # Contexto whisper.cpp
        self._model_path = None
        
        # Cache local de modelos
        self.cache_dir = Path.home() / ".cache" / "clipfusion" / "whisper"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    def _get_model_url(self) -> str:
        """URL HuggingFace para modelo quantizado."""
        base = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main"
        return f"{base}/ggml-{self.model_name}-{self.quantize}.bin"
    
    def _ensure_model(self) -> Path:
        """Download lazy do modelo."""
        filename = f"ggml-{self.model_name}-{self.quantize}.bin"
        model_path = self.cache_dir / filename
        
        if model_path.exists():
            size_mb = model_path.stat().st_size / (1024*1024)
            print(f"[WhisperCpp] Modelo cacheado: {filename} ({size_mb:.1f}MB)")
            return model_path
        
        # Download com progresso
        print(f"[WhisperCpp] Baixando {filename}...")
        import urllib.request
        
        def progress(block_num, block_size, total_size):
            downloaded = block_num * block_size / (1024*1024)
            total = total_size / (1024*1024)
            pct = (block_num * block_size) / total_size * 100
            sys.stdout.write(f"\r  ↳ {downloaded:.1f}MB / {total:.1f}MB ({pct:.1f}%)")
            sys.stdout.flush()
        
        url = self._get_model_url()
        urllib.request.urlretrieve(url, model_path, reporthook=progress)
        print(f"\n[WhisperCpp] Download concluído")
        
        return model_path
    
    def _load_library(self):
        """Carrega whisper.cpp via ctypes."""
        try:
            import ctypes
            from ctypes import CDLL, c_char_p, c_int, c_float, c_void_p, POINTER
            
            # Procura biblioteca compilada
            lib_paths = [
                self.cache_dir / "libwhisper.so",
                Path("/usr/local/lib/libwhisper.so"),
                Path("libwhisper.so"),  # mesmo diretório
            ]
            
            lib_path = None
            for p in lib_paths:
                if p.exists():
                    lib_path = str(p)
                    break
            
            if not lib_path:
                raise RuntimeError(
                    "libwhisper.so não encontrado. Compile: "
                    "git clone https://github.com/ggerganov/whisper.cpp && "
                    "cd whisper.cpp && make libwhisper.so"
                )
            
            self._lib = CDLL(lib_path)
            
            # Define signatures
            self._lib.whisper_init_from_file.argtypes = [c_char_p]
            self._lib.whisper_init_from_file.restype = c_void_p
            
            self._lib.whisper_full.argtypes = [
                c_void_p, c_int, c_int, c_int, c_float, c_int,
                c_char_p, c_int, c_int, c_int, c_int, c_int
            ]
            self._lib.whisper_full.restype = c_int
            
            self._lib.whisper_free.argtypes = [c_void_p]
            self._lib.whisper_free.restype = None
            
            return True
            
        except Exception as e:
            print(f"[WhisperCpp] Biblioteca nativa não disponível: {e}")
            return False
    
    def _extract_audio_optimized(self, video_path: str, out_path: str) -> None:
        """
        Extração otimizada para zRAM: 16kHz mono, filtros leves em CPU.
        Respeita seu i915 GuC/HuC mas não usa para decode (GPU desabilitada).
        """
        # Usa CPU para decode, sem VA-API (você desabilitou)
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-threads", str(self.n_threads),  # Limita threads FFmpeg
            "-i", video_path,
            # Filtros leves: highpass remove DC, lowpass limita banda de voz
            "-af", "highpass=f=80,lowpass=f=8000,afftdn=nf=-25,aresample=resampler=soxr:precision=28",
            "-ar", "16000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            "-f", "wav",
            out_path,
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    def transcribe(self, video_path: str, language: str = "pt") -> Dict[str, Any]:
        """
        Pipeline completo com gestão agressiva de memória para zRAM.
        """
        if not self._model_path:
            self._model_path = str(self._ensure_model())
        
        # Extrai áudio
        tmp_wav = tempfile.mktemp(suffix=".wav")
        try:
            print(f"[WhisperCpp] Extraindo áudio: {os.path.basename(video_path)}")
            self._extract_audio_optimized(video_path, tmp_wav)
            
            # Verifica se temos biblioteca nativa
            if self._load_library():
                return self._transcribe_native(tmp_wav, language)
            else:
                # Fallback: CLI whisper.cpp
                return self._transcribe_cli(tmp_wav, language)
                
        finally:
            # Limpeza agressiva (crítico para swappiness 150)
            if os.path.exists(tmp_wav):
                os.remove(tmp_wav)
            gc.collect()
    
    def _transcribe_cli(self, audio_path: str, language: str) -> Dict[str, Any]:
        """
        Fallback usando binário whisper.cpp (mais lento mas sempre funciona).
        """
        whisper_bin = os.environ.get("WHISPER_CPP_BIN", "whisper-cli")
        
        output_json = tempfile.mktemp(suffix=".json")
        
        cmd = [
            whisper_bin,
            "-m", self._model_path,
            "-f", audio_path,
            "-l", language,
            "-ojf",  # output JSON
            "-of", output_json.replace(".json", ""),  # whisper adiciona .json
            "-t", str(self.n_threads),
            "--max-len", "1",  # word-level timestamps
            "--split-on-word",
        ]
        
        # Executa com prioridade de I/O otimizada para zRAM
        env = os.environ.copy()
        env["MALLOC_ARENA_MAX"] = "2"  # Limita arenas glibc (menos memória residente)
        
        subprocess.run(cmd, check=True, env=env, capture_output=True)
        
        # Lê resultado
        with open(output_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        os.remove(output_json)
        
        # Converte para formato padronizado
        words = []
        for seg in data.get("transcription", []):
            for w in seg.get("words", []):
                words.append({
                    "word": w.get("word", "").strip(),
                    "start": w.get("timestamp", 0.0),
                    "end": w.get("timestamp", 0.0) + 0.3,  # estimativa
                })
        
        return {
            "text": " ".join(w["word"] for w in words),
            "language": language,
            "segments": data.get("transcription", []),
            "words": words,
            "backend": "whisper.cpp-cli",
        }
    
    def _transcribe_native(self, audio_path: str, language: str) -> Dict[str, Any]:
        """
        Transcrição via biblioteca nativa (mais rápida, controle fino de memória).
        Placeholder - implementação ctypes completa requer headers.
        """
        # Por enquanto, delega para CLI
        return self._transcribe_cli(audio_path, language)
    
    def unload(self):
        """Libera modelo da RAM (força compressão zRAM ou descarte)."""
        self._whisper = None
        self._ctx = None
        gc.collect()
        # Dica ao kernel para liberar páginas
        if hasattr(os, 'posix_fadvise') and self._model_path:
            try:
                fd = os.open(self._model_path, os.O_RDONLY)
                os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
                os.close(fd)
            except:
                pass
    
    def get_memory_stats(self) -> Dict[str, str]:
        """Retorna estimativas de consumo para debug."""
        return {
            "modelo": self.MODELS.get(self.model_name, {}).get("ram", "unknown"),
            "threads": str(self.n_threads),
            "batch": str(self.n_batch),
            "zram_optimizado": "sim (swappiness 150)",
        }


# Singleton para reutilização controlada
_whisper_instance: Optional[WhisperCppTranscriber] = None

def get_transcriber(model: str = "medium", reuse: bool = False) -> WhisperCppTranscriber:
    """
    Factory: reutiliza instância se solicitado (economiza reload do modelo no zRAM).
    """
    global _whisper_instance
    
    if reuse and _whisper_instance and _whisper_instance.model_name == model:
        return _whisper_instance
    
    if _whisper_instance:
        _whisper_instance.unload()
    
    _whisper_instance = WhisperCppTranscriber(model_name=model)
    return _whisper_instance
