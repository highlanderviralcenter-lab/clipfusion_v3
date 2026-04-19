"""ClipFusion — Temporal: speed variation ±0.5% (abaixo limiar humano ~3%)."""
import random


class TemporalObfuscation:
    def __init__(self, seed: int):
        self.rng = random.Random(seed)

    def ffmpeg_filters(self) -> list:
        speed = self.rng.uniform(0.995, 1.005)
        return [f"setpts={1.0/speed:.5f}*PTS"]
