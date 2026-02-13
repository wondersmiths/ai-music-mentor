from ai.omr.models import Measure, Note


# Pitch names for treble clef, from bottom staff line (E4) upward
TREBLE_PITCHES = [
    "C4", "D4", "E4", "F4", "G4", "A4", "B4",
    "C5", "D5", "E5", "F5", "G5", "A5", "B5",
]

# Duration values in beats (for 4/4 time)
DURATION_BEATS = {
    "whole": 4.0,
    "half": 2.0,
    "quarter": 1.0,
    "eighth": 0.5,
    "sixteenth": 0.25,
}


def position_to_pitch(
    y: int, staff_lines: list[int], clef: str = "treble", key_sig: str = "C"
) -> str:
    """Map a vertical position to a pitch name based on staff line positions."""
    if len(staff_lines) < 2:
        return "C4"

    # Calculate the space between staff lines (one staff step = half a line space)
    staff_spacing = (staff_lines[-1] - staff_lines[0]) / (len(staff_lines) - 1)
    half_space = staff_spacing / 2.0

    # Bottom line of the staff is E4 in treble clef
    bottom_line = staff_lines[-1]

    # Calculate steps from bottom line (positive = upward)
    steps = round((bottom_line - y) / half_space)

    # E4 is index 2 in TREBLE_PITCHES
    index = steps + 2
    index = max(0, min(index, len(TREBLE_PITCHES) - 1))

    return TREBLE_PITCHES[index]


def classify_duration(
    contour, has_stem: bool, has_flag: bool, has_beam: bool
) -> str:
    """Classify note duration from visual features."""
    if not has_stem:
        return "whole"
    if has_flag or has_beam:
        return "eighth"
    # Filled notehead with stem = quarter, open = half
    return "quarter"


def build_measures(
    detections: list[dict], staff_lines: list[int], time_sig: str = "4/4"
) -> list[Measure]:
    """Group notes into measures based on cumulative beat count."""
    beats_per_measure = float(time_sig.split("/")[0])

    measures: list[Measure] = []
    current_notes: list[Note] = []
    current_beat = 1.0
    measure_num = 1

    for det in detections:
        pitch = position_to_pitch(det["y"], staff_lines)
        duration = classify_duration(
            det.get("contour"),
            det.get("has_stem", False),
            det.get("has_flag", False),
            det.get("has_beam", False),
        )
        beat_value = DURATION_BEATS.get(duration, 1.0)

        note = Note(pitch=pitch, duration=duration, beat=current_beat)
        current_notes.append(note)
        current_beat += beat_value

        # When the measure is full, finalize it
        if current_beat > beats_per_measure + 0.99:
            measures.append(Measure(
                number=measure_num,
                time_signature=time_sig,
                notes=current_notes,
            ))
            current_notes = []
            current_beat = 1.0
            measure_num += 1

    # Remaining notes go into a final measure
    if current_notes:
        measures.append(Measure(
            number=measure_num,
            time_signature=time_sig,
            notes=current_notes,
        ))

    return measures
