from typing import List, Optional

from pydantic import BaseModel


class Note(BaseModel):
    pitch: str  # e.g. "C4"
    duration: str  # e.g. "quarter"
    beat: float  # beat position within the measure
    jianpu: Optional[str] = None  # e.g. "6" or "6̇" (jianpu display label)


class Measure(BaseModel):
    number: int
    time_signature: str  # e.g. "4/4"
    notes: List[Note]


class ScoreResult(BaseModel):
    title: str
    confidence: float
    is_mock: bool
    measures: List[Measure]
    notation_type: str = "western"  # "western" or "jianpu"
    key_signature: Optional[str] = None  # e.g. "1=F"
    page_count: int = 1
