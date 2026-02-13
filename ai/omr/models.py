from pydantic import BaseModel


class Note(BaseModel):
    pitch: str  # e.g. "C4"
    duration: str  # e.g. "quarter"
    beat: float  # beat position within the measure


class Measure(BaseModel):
    number: int
    time_signature: str  # e.g. "4/4"
    notes: list[Note]


class ScoreResult(BaseModel):
    title: str
    confidence: float
    is_mock: bool
    measures: list[Measure]
