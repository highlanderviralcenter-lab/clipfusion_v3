"""ClipFusion — Network Evasion: agenda de upload com jitter ±20%."""
import random
from datetime import datetime, timedelta
from typing import List

class NetworkEvasion:
    PLATFORM_CONFIGS = {
        "tiktok":    {"peak": [(7,9),(12,14),(19,22)], "interval": (4,8),   "max_day": 5},
        "instagram": {"peak": [(11,13),(19,21)],        "interval": (18,30), "max_day": 2},
        "youtube":   {"peak": [(14,16),(19,21)],        "interval": (48,96), "max_day": 1},
        "kwai":      {"peak": [(12,14),(20,23)],        "interval": (6,12),  "max_day": 4},
    }

    def __init__(self, seed: int = None):
        self.rng = random.Random(seed)

    def generate_schedule(self, count: int, platform: str = "tiktok") -> List[dict]:
        cfg = self.PLATFORM_CONFIGS.get(platform, self.PLATFORM_CONFIGS["tiktok"])
        current = datetime.now()
        out = []
        for i in range(count):
            min_h, max_h = cfg["interval"]
            hours   = self.rng.uniform(min_h, max_h)
            jitter  = hours * self.rng.uniform(-0.20, 0.20)
            current = current + timedelta(hours=hours + jitter)
            window  = self.rng.choice(cfg["peak"])
            current = current.replace(
                hour=int(self.rng.uniform(*window)),
                minute=self.rng.randint(0,59), second=self.rng.randint(0,59))
            out.append({"index": i+1, "platform": platform,
                        "datetime": current.strftime("%d/%m/%Y %H:%M")})
        return out

    def format_schedule(self, schedule: list) -> str:
        lines = [f"📅 Agenda — {len(schedule)} vídeos\n"]
        for s in schedule:
            lines.append(f"  #{s['index']:02d}  {s['datetime']}  [{s['platform']}]")
        return "\n".join(lines)
