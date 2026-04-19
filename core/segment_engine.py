from dataclasses import dataclass
from typing import List, Dict


@dataclass
class Word:
    word: str
    start: float
    end: float
    confidence: float = 0.0


@dataclass
class VideoSegment:
    start: float
    end: float
    text: str
    words: List[Word]
    hook_score: float = 0.0
    retention_score: float = 0.0
    platform_fit: Dict[str, float] = None
    
    def duration(self) -> float:
        return self.end - self.start
