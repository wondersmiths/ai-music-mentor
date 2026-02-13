from ai.omr.models import Measure, Note, ScoreResult


def mock_score() -> ScoreResult:
    """Return a fixed 4-measure C-major melody as fallback."""
    return ScoreResult(
        title="Mock Score",
        confidence=0.0,
        is_mock=True,
        measures=[
            Measure(
                number=1,
                time_signature="4/4",
                notes=[
                    Note(pitch="C4", duration="quarter", beat=1.0),
                    Note(pitch="D4", duration="quarter", beat=2.0),
                    Note(pitch="E4", duration="quarter", beat=3.0),
                    Note(pitch="F4", duration="quarter", beat=4.0),
                ],
            ),
            Measure(
                number=2,
                time_signature="4/4",
                notes=[
                    Note(pitch="G4", duration="quarter", beat=1.0),
                    Note(pitch="A4", duration="quarter", beat=2.0),
                    Note(pitch="B4", duration="quarter", beat=3.0),
                    Note(pitch="C5", duration="quarter", beat=4.0),
                ],
            ),
            Measure(
                number=3,
                time_signature="4/4",
                notes=[
                    Note(pitch="C5", duration="half", beat=1.0),
                    Note(pitch="B4", duration="half", beat=3.0),
                ],
            ),
            Measure(
                number=4,
                time_signature="4/4",
                notes=[
                    Note(pitch="A4", duration="half", beat=1.0),
                    Note(pitch="G4", duration="half", beat=3.0),
                ],
            ),
        ],
    )
