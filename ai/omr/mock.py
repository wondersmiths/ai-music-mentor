from ai.omr.models import Measure, Note, ScoreResult


def mock_score() -> ScoreResult:
    """Return 赛马 (Horse Racing) opening 24 measures as fallback.

    Jianpu key: 1=F (F major). Converted to western pitch notation.
    Time signature: 2/4, ~130 BPM.
    Pitch mapping: 1=F4 2=G4 3=A4 4=Bb4 5=C5 6=D5 7=E5
    """
    def m(num: int, notes: list[tuple[str, str, float, str]]) -> Measure:
        return Measure(
            number=num,
            time_signature="2/4",
            notes=[Note(pitch=p, duration=d, beat=b, jianpu=j) for p, d, b, j in notes],
        )

    # Opening theme: 6. 35 (D5 quarter + A4-C5 eighths)
    theme = [("D5", "quarter", 1.0, "6"), ("A4", "eighth", 2.0, "3"), ("C5", "eighth", 2.5, "5")]

    # Running sixteenths: 0535 0535
    run_ac = [
        ("C5", "sixteenth", 1.0, "5"), ("A4", "sixteenth", 1.25, "3"),
        ("C5", "sixteenth", 1.5, "5"), ("A4", "sixteenth", 1.75, "3"),
        ("C5", "sixteenth", 2.0, "5"), ("A4", "sixteenth", 2.25, "3"),
        ("C5", "sixteenth", 2.5, "5"), ("A4", "sixteenth", 2.75, "3"),
    ]

    # 6 56 pattern
    d5c5 = [
        ("D5", "eighth", 1.0, "6"), ("C5", "eighth", 1.5, "5"),
        ("D5", "eighth", 2.0, "6"), ("C5", "eighth", 2.5, "5"),
    ]

    # Descending: 6316̣
    desc = [
        ("D5", "eighth", 1.0, "6"), ("A4", "eighth", 1.5, "3"),
        ("F4", "eighth", 2.0, "1"), ("D4", "eighth", 2.5, "6\u0323"),
    ]

    # Ascending: 3653
    asc = [
        ("A4", "eighth", 1.0, "3"), ("D5", "eighth", 1.5, "6"),
        ("C5", "eighth", 2.0, "5"), ("A4", "eighth", 2.5, "3"),
    ]

    # 2321 galloping pattern
    gallop = [
        ("G4", "sixteenth", 1.0, "2"), ("A4", "sixteenth", 1.25, "3"),
        ("G4", "sixteenth", 1.5, "2"), ("F4", "sixteenth", 1.75, "1"),
        ("G4", "sixteenth", 2.0, "2"), ("A4", "sixteenth", 2.25, "3"),
        ("G4", "sixteenth", 2.5, "2"), ("F4", "sixteenth", 2.75, "1"),
    ]

    # Sustained: 2. 61
    sust = [("G4", "quarter", 1.0, "2"), ("D5", "eighth", 2.0, "6"), ("F4", "eighth", 2.5, "1")]

    return ScoreResult(
        title="赛马 (Horse Racing)",
        confidence=0.0,
        is_mock=True,
        notation_type="jianpu",
        key_signature="1=F",
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
            m(21, [("D5", "quarter", 1.0, "6"), ("C5", "quarter", 2.0, "5")]),
            m(22, [("A4", "quarter", 1.0, "3"), ("C5", "quarter", 2.0, "5")]),
            m(23, theme),
            m(24, [("D5", "half", 1.0, "6")]),
        ],
    )
