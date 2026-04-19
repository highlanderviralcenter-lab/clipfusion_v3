"""ClipFusion — Geometric: zoom 1–3%, micro-rotação, perspectiva."""
import random

class GeometricTransforms:
    def __init__(self, seed: int):
        self.rng = random.Random(seed)

    def ffmpeg_filters(self, rotation: bool = False, perspective: bool = False) -> list:
        zoom = self.rng.uniform(1.010, 1.030)
        filters = [f"scale=iw*{zoom:.4f}:ih*{zoom:.4f},crop=iw/{zoom:.4f}:ih/{zoom:.4f}"]
        if rotation:
            rad = self.rng.uniform(-0.3, 0.3) * 3.14159 / 180
            filters.append(f"rotate={rad:.5f}:fillcolor=black:expand=0")
        if perspective:
            ox = self.rng.uniform(0.001, 0.003); oy = self.rng.uniform(0.001, 0.003)
            filters.append(
                f"perspective=x0=iw*{ox:.4f}:y0=ih*{oy:.4f}:"
                f"x1=iw*(1-{ox:.4f}):y1=ih*{oy:.4f}:"
                f"x2=iw*{ox:.4f}:y2=ih*(1-{oy:.4f}):"
                f"x3=iw*(1-{ox:.4f}):y3=ih*(1-{oy:.4f}):interpolation=linear")
        return filters
