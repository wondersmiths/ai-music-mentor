from ai.omr.detector import detect_noteheads, detect_staff_lines, estimate_confidence
from ai.omr.mock import mock_score
from ai.omr.models import ScoreResult
from ai.omr.parser import build_measures
from ai.omr.preprocessor import load_image, preprocess


def recognize(
    file_path: str, confidence_threshold: float = 0.6
) -> ScoreResult:
    """Full OMR pipeline: load, detect, parse, or fall back to mock."""
    # 1. Load and preprocess
    raw = load_image(file_path)
    binary = preprocess(raw)

    # 2. Detect staff lines and noteheads
    staff_lines = detect_staff_lines(binary)
    if not staff_lines:
        return mock_score()

    detections = detect_noteheads(binary, staff_lines)

    # 3. Estimate confidence — fall back if too low
    confidence = estimate_confidence(detections)
    if confidence < confidence_threshold:
        return mock_score()

    # 4. Parse detections into measures
    measures = build_measures(detections, staff_lines)

    # 5. Return result
    return ScoreResult(
        title="Uploaded Score",
        confidence=confidence,
        is_mock=False,
        measures=measures,
    )
