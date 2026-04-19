"""
Gerenciador de memória para BTRFS flat + zRAM (i5-6200U otimizado).
Sem subvolumes, mas com compressão zstd ativa no filesystem.
"""
import os
import gc
import sys
import psutil
from typing import Dict, Any


class MemoryManager:
    """
    Adapta alocações baseado em:
    - zRAM disponível (comprimido)
    - BTRFS compress ratio (se exposto)
    - RAM física livre
    """
    
    def __init__(self):
        self.swappiness = self._read_sysctl("vm.swappiness", 60)
        self.zram_enabled = os.path.exists("/sys/block/zram0")
        self.btrfs_mount = self._find_btrfs_root()
        self.last_pressure = 0.0
        
    def _read_sysctl(self, key: str, default: int) -> int:
        try:
            with open(f"/proc/sys/{key.replace('.', '/')}", "r") as f:
                return int(f.read().strip())
        except:
            return default
    
    def _find_btrfs_root(self) -> str:
        """Encontra onde está montado o BTRFS (flat, sem subvol)."""
        try:
            with open("/proc/mounts", "r") as f:
                for line in f:
                    parts = line.split()
                    if parts[2] == "btrfs" and parts[1] == "/":
                        return parts[1]
        except:
            pass
        return "/"
    
    def get_stats(self) -> Dict[str, Any]:
        """Snapshot atual da hierarquia de memória + BTRFS."""
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        # zRAM stats
        zram_stats = {}
        if self.zram_enabled:
            try:
                with open("/sys/block/zram0/mm_stat", "r") as f:
                    vals = f.read().strip().split()
                    if len(vals) >= 2:
                        orig = int(vals[0]) / (1024**2)
                        comp = int(vals[1]) / (1024**2)
                        zram_stats = {
                            "data_original_mb": orig,
                            "data_compressed_mb": comp,
                            "ratio": orig / max(comp, 1),
                        }
            except:
                pass
        
        # BTRFS compression ratio (se disponível via btrfs fi df)
        btrfs_ratio = None
        try:
            import subprocess
            result = subprocess.run(
                ["btrfs", "filesystem", "df", "-c", self.btrfs_mount],
                capture_output=True, text=True, timeout=2
            )
            # Procura linha com "Compression ratio"
            for line in result.stdout.split("\n"):
                if "Compression ratio" in line:
                    # Exemplo: "Compression ratio: 2.15"
                    parts = line.split(":")
                    if len(parts) == 2:
                        btrfs_ratio = float(parts[1].strip())
                        break
        except:
            pass
        
        return {
            "ram_total_mb": mem.total / (1024**2),
            "ram_available_mb": mem.available / (1024**2),
            "ram_percent": mem.percent,
            "swap_used_mb": swap.used / (1024**2),
            "swap_percent": swap.percent,
            "zram": zram_stats,
            "btrfs_mount": self.btrfs_mount,
            "btrfs_compression_ratio": btrfs_ratio,
            "swappiness": self.swappiness,
        }
    
    def should_load_model(self, model_ram_mb: float) -> bool:
        """
        Decide se é seguro carregar modelo.
        Com zRAM agressivo (swappiness 150), aceitamos mais pressão.
        """
        stats = self.get_stats()
        
        ram_avail = stats["ram_available_mb"]
        
        # Com zRAM LZ4, taxa ~2:1 é realista
        zram_headroom = 0
        if self.zram_enabled and stats["zram"]:
            # zRAM ainda tem capacidade?
            ratio = stats["zram"]["ratio"]
            if ratio < 3.0:  # ainda comprimindo bem
                zram_headroom = 2000  # assume 2GB virtual disponível
        
        effective_avail = ram_avail + zram_headroom
        
        # Margem de 30% para segurança
        return effective_avail > model_ram_mb * 1.3
    
    def pre_allocate(self, size_mb: float):
        """Força GC antes de alocação grande."""
        gc.collect()
        gc.collect()
        
        # Dica de memória sequencial para o kernel
        try:
            import ctypes
            ctypes.CDLL("libc.so.6").malloc_trim(0)
        except:
            pass
        
    def emergency_cleanup(self):
        """Liberação agressiva."""
        gc.set_threshold(700, 10, 10)
        gc.collect()
        
        try:
            import ctypes
            ctypes.CDLL("libc.so.6").malloc_trim(0)
        except:
            pass
        
        self.last_pressure = psutil.virtual_memory().percent


# Singleton
_memory_mgr = MemoryManager()

def get_memory_manager() -> MemoryManager:
    return _memory_mgr
