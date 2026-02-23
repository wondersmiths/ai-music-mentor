from __future__ import annotations

from ai.omr.detector import detect_noteheads, detect_staff_lines, estimate_confidence
from ai.omr.jianpu import detect_notation_type, recognize_jianpu
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

    # 2. Detect staff lines
    staff_lines = detect_staff_lines(binary)

    # 3. Determine notation type
    notation_type = detect_notation_type(binary, staff_lines)

    # 4. Branch by notation type
    if notation_type == "jianpu":
        return _recognize_jianpu(binary)

    # Western pipeline
    if not staff_lines:
        return mock_score()

    detections = detect_noteheads(binary, staff_lines)

    confidence = estimate_confidence(detections)
    if confidence < confidence_threshold:
        return mock_score()

    measures = build_measures(detections, staff_lines)

    return ScoreResult(
        title="Uploaded Score",
        confidence=confidence,
        is_mock=False,
        measures=measures,
    )


def _recognize_jianpu(binary) -> ScoreResult:
    """Run jianpu OCR pipeline, falling back to mock on failure."""
    measures, key_sig, time_sig, confidence = recognize_jianpu(binary)

    if not measures:
        return mock_score()

    return ScoreResult(
        title="Uploaded Score",
        confidence=confidence,
        is_mock=False,
        measures=measures,
        notation_type="jianpu",
        key_signature=key_sig,
    )


def recognize_multi(
    file_paths: list[str], confidence_threshold: float = 0.6
) -> ScoreResult:
    """Process multiple pages as one score, concatenating measures."""
    if not file_paths:
        return mock_score()

    if len(file_paths) == 1:
        result = recognize(file_paths[0], confidence_threshold)
        result.page_count = 1
        return result

    all_measures = []
    total_confidence = 0.0
    notation_type = "western"
    key_signature = None
    title = "Uploaded Score"
    any_real = False

    for path in file_paths:
        result = recognize(path, confidence_threshold)
        if not result.is_mock:
            any_real = True
        total_confidence += result.confidence
        if result.notation_type == "jianpu":
            notation_type = "jianpu"
        if result.key_signature:
            key_signature = result.key_signature
        if result.title != "Uploaded Score":
            title = result.title
        all_measures.extend(result.measures)

    # Renumber measures sequentially
    for i, measure in enumerate(all_measures):
        measure.number = i + 1

    avg_confidence = total_confidence / len(file_paths) if file_paths else 0.0

    return ScoreResult(
        title=title,
        confidence=avg_confidence,
        is_mock=not any_real,
        measures=all_measures,
        notation_type=notation_type,
        key_signature=key_signature,
        page_count=len(file_paths),
    )
