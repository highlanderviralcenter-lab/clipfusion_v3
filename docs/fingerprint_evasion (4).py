"""ClipFusion — Fingerprint Evasion: cor, noise, chroma, frequency, metadados."""
import random, hashlib
from datetime import datetime, timedelta

class FingerprintEvasion:
    def __init__(self, seed: int):
        self.rng = random.Random(seed)

    def color_filters(self) -> list:
        b = self.rng.uniform(-0.006, 0.006); c = self.rng.uniform(0.995, 1.005)
        s = self.rng.uniform(0.996, 1.004);  g = self.rng.uniform(0.996, 1.004)
        return [f"eq=brightness={b:.4f}:contrast={c:.4f}:saturation={s:.4f}:gamma={g:.4f}"]

    def noise_filters(self) -> list:
        return [f"noise=alls={self.rng.uniform(0.3, 0.6):.2f}:allf=t+u"]

    def chroma_filters(self) -> list:
        h = self.rng.uniform(-0.4, 0.4); s = self.rng.uniform(0.997, 1.003)
        return [f"hue=h={h:.3f}:s={s:.4f}"]

    def frequency_filters(self) -> list:
        lx = self.rng.randint(3, 5); la = self.rng.uniform(-0.05, 0.05)
        cx = self.rng.randint(3, 5); ca = self.rng.uniform(-0.03, 0.03)
        return [f"unsharp=luma_msize_x={lx}:luma_msize_y={lx}:luma_amount={la:.3f}"
                f":chroma_msize_x={cx}:chroma_msize_y={cx}:chroma_amount={ca:.3f}"]

    def metadata_inject_args(self, project_id: str) -> list:
        rng = random.Random(int(hashlib.md5(project_id.encode()).hexdigest()[:8], 16))
        fake_date = datetime.now() - timedelta(
            days=rng.randint(0,730), hours=rng.randint(0,23), minutes=rng.randint(0,59))
        encoders = ["libx264 (High@L4.1)", "H.264/AVC Codec", "libx265 (Main@L4.0)"]
        return [
            "-metadata", f"creation_time={fake_date.isoformat()}",
            "-metadata", f"encoder={rng.choice(encoders)}",
            "-metadata", "copyright=", "-metadata", "description=",
            "-metadata", "title=", "-metadata", "artist=",
        ]
