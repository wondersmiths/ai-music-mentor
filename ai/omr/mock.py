from ai.omr.models import Measure, Note, ScoreResult


def mock_score() -> ScoreResult:
    """Return 赛马 (Horse Racing) opening 24 measures as fallback.

    Jianpu key: 1=F (F major). Converted to western pitch notation.
    Time signature: 2/4, ~130 BPM.
    """
    def m(num: int, notes: list[tuple[str, str, float]]) -> Measure:
        return Measure(
            number=num,
            time_signature="2/4",
            notes=[Note(pitch=p, duration=d, beat=b) for p, d, b in notes],
        )

    # Opening theme: 6. 35 (D5 quarter + A4-C5 eighths)
    theme = [("D5", "quarter", 1.0), ("A4", "eighth", 2.0), ("C5", "eighth", 2.5)]

    # Running sixteenths: 0535 0535
    run_ac = [
        ("C5", "sixteenth", 1.0), ("A4", "sixteenth", 1.25),
        ("C5", "sixteenth", 1.5), ("A4", "sixteenth", 1.75),
        ("C5", "sixteenth", 2.0), ("A4", "sixteenth", 2.25),
        ("C5", "sixteenth", 2.5), ("A4", "sixteenth", 2.75),
    ]

    # 6 56 pattern
    d5c5 = [
        ("D5", "eighth", 1.0), ("C5", "eighth", 1.5),
        ("D5", "eighth", 2.0), ("C5", "eighth", 2.5),
    ]

    # Descending: 6316
    desc = [
        ("D5", "eighth", 1.0), ("A4", "eighth", 1.5),
        ("F4", "eighth", 2.0), ("D4", "eighth", 2.5),
    ]

    # Ascending: 3653
    asc = [
        ("A4", "eighth", 1.0), ("D5", "eighth", 1.5),
        ("C5", "eighth", 2.0), ("A4", "eighth", 2.5),
    ]

    # 2321 galloping pattern
    gallop = [
        ("G4", "sixteenth", 1.0), ("A4", "sixteenth", 1.25),
        ("G4", "sixteenth", 1.5), ("F4", "sixteenth", 1.75),
        ("G4", "sixteenth", 2.0), ("A4", "sixteenth", 2.25),
        ("G4", "sixteenth", 2.5), ("F4", "sixteenth", 2.75),
    ]

    # Sustained: 2. 61
    sust = [("G4", "quarter", 1.0), ("D5", "eighth", 2.0), ("F4", "eighth", 2.5)]

    return ScoreResult(
        title="赛马 (Horse Racing)",
        confidence=0.0,
        is_mock=True,
        measures=[
            m(1, theme), m(2, theme), m(3, theme),
            m(4, run_ac), m(5, run_ac),
            m(6, d5c5), m(7, d5c5),
            m(8, desc), m(9, asc),
            m(10, gallop), m(11, gallop),
            m(12, desc), m(13, asc),
            m(14, gallop), m(15, gallop),
            m(16, sust), m(17, sust), m(18, sust), m(19, sust),
            m(20, gallop),
            m(21, [("D5", "quarter", 1.0), ("C5", "quarter", 2.0)]),
            m(22, [("A4", "quarter", 1.0), ("C5", "quarter", 2.0)]),
            m(23, theme),
            m(24, [("D5", "half", 1.0)]),
        ],
    )
