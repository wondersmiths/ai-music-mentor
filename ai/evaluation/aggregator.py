"""
B5: Evaluation aggregator.

Combines DTW alignment, pitch stability, and (future) slide/rhythm metrics
into a single evaluation result with overall score, sub-scores,
recommended training type, and textual feedback.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ai.evaluation.dtw import DTWResult, dtw_align
from ai.evaluation.stability import StabilityResult, analyze_stability


@dataclass
class EvaluationResult:
    """Aggregated evaluation of a practice session."""
    overall_score: float          # 0–100
    pitch_score: float            # 0–100 (from DTW pitch error)
    stability_score: float        # 0–100 (from stability analyzer)
    slide_score: float            # 0–100 (placeholder for B3)
    rhythm_score: float           # 0–100 (placeholder for B4)
    recommended_training_type: str
    textual_feedback: str
    dtw_result: DTWResult | None = None
    stability_result: StabilityResult | None = None


# ── Score weights by exercise type ──────────────────────────

WEIGHTS = {
    "long_tone": {"pitch": 0.3, "stability": 0.5, "slide": 0.0, "rhythm": 0.2},
    "scale":     {"pitch": 0.4, "stability": 0.2, "slide": 0.1, "rhythm": 0.3},
    "melody":    {"pitch": 0.35, "stability": 0.15, "slide": 0.15, "rhythm": 0.35},
}
DEFAULT_WEIGHTS = {"pitch": 0.35, "stability": 0.25, "slide": 0.1, "rhythm": 0.3}


# ── Pitch score from DTW cents error ────────────────────────

def _pitch_score_from_error(mean_cents_error: float) -> float:
    """
    Convert mean pitch error in cents to a 0–100 score.
    0 cents → 100, 100+ cents → 0. Linear ramp.
    """
    return max(0.0, 100.0 * (1.0 - mean_cents_error / 100.0))


# ── Rhythm score from timing deviation ──────────────────────

def _rhythm_score_from_deviation(timing_dev: float) -> float:
    """
    Convert mean timing deviation in seconds to 0–100 score.
    0s → 100, 0.5s+ → 0. Linear ramp.
    """
    return max(0.0, 100.0 * (1.0 - timing_dev / 0.5))


# ── Training recommendation ────────────────────────────────

def _recommend_training(
    pitch_score: float,
    stability_score: float,
    rhythm_score: float,
) -> str:
    """Pick the weakest area and recommend a training type."""
    scores = {
        "long_tone": stability_score,
        "scale": pitch_score,
        "rhythm_drill": rhythm_score,
    }
    return min(scores, key=scores.get)  # type: ignore[arg-type]


# ── Feedback generation ─────────────────────────────────────

def _generate_feedback(
    overall: float,
    pitch_score: float,
    stability_score: float,
    rhythm_score: float,
    exercise_type: str,
) -> str:
    """
    Generate encouraging textual feedback.
    Structure: encouragement → one main weakness → next exercise suggestion.
    """
    lines: list[str] = []

    # Encouragement first
    if overall >= 90:
        lines.append("Excellent work! Your performance is very strong.")
    elif overall >= 75:
        lines.append("Good job! You're making solid progress.")
    elif overall >= 50:
        lines.append("Nice effort! There's room to improve — keep practicing.")
    else:
        lines.append("Keep going! Every practice session builds your skill.")

    # Identify main weakness
    weaknesses = {
        "pitch accuracy": pitch_score,
        "tone stability": stability_score,
        "rhythmic timing": rhythm_score,
    }
    weakest_area = min(weaknesses, key=weaknesses.get)  # type: ignore[arg-type]
    weakest_score = weaknesses[weakest_area]

    if weakest_score < 80:
        lines.append(f"Focus on {weakest_area} — it scored {weakest_score:.0f}/100.")

    # Suggest next exercise
    suggestion = _recommend_training(pitch_score, stability_score, rhythm_score)
    exercise_names = {
        "long_tone": "long tone exercises",
        "scale": "slow scale practice",
        "rhythm_drill": "rhythm drills with a metronome",
    }
    lines.append(f"Try {exercise_names.get(suggestion, suggestion)} next.")

    return " ".join(lines)


# ── Main evaluator ──────────────────────────────────────────

def evaluate(
    played_frames: list[tuple[float, float, float]],
    exercise_type: str,
    target_frequency: float | None = None,
    reference_curve: list[tuple[float, float]] | None = None,
    bpm: float | None = None,
) -> EvaluationResult:
    """
    Run the full evaluation pipeline on a practice session.

    Args:
        played_frames: list of (time, frequency, confidence) from the recorder.
        exercise_type: "long_tone", "scale", "melody", etc.
        target_frequency: for long_tone exercises, the target Hz.
        reference_curve: for scale/melody, the expected (time, frequency) curve.
        bpm: beats per minute (informational, for future rhythm analysis).

    Returns:
        EvaluationResult with all scores and feedback.
    """
    # ── DTW alignment (if reference curve provided) ──────────
    dtw_result: DTWResult | None = None
    pitch_score = 100.0
    rhythm_score = 100.0

    played_tf = [(t, f) for t, f, _ in played_frames]

    if reference_curve:
        dtw_result = dtw_align(played_tf, reference_curve)
        pitch_score = _pitch_score_from_error(dtw_result.pitch_error_mean)
        rhythm_score = _rhythm_score_from_deviation(dtw_result.timing_deviation)
    elif target_frequency and target_frequency > 0:
        # For long_tone: measure pitch accuracy as mean deviation from target
        valid_freqs = [f for _, f, _ in played_frames if f > 0]
        if valid_freqs:
            import numpy as np
            cents = [abs(1200.0 * np.log2(f / target_frequency)) for f in valid_freqs]
            pitch_score = _pitch_score_from_error(float(np.mean(cents)))

    # ── Stability analysis ───────────────────────────────────
    stability_result: StabilityResult | None = None
    stab_score = 100.0

    if target_frequency and target_frequency > 0:
        stability_result = analyze_stability(played_frames, target_frequency)
        stab_score = stability_result.stability_score
    elif reference_curve:
        # Use median frequency of reference as rough target
        ref_freqs = [f for _, f in reference_curve if f > 0]
        if ref_freqs:
            import numpy as np
            median_freq = float(np.median(ref_freqs))
            stability_result = analyze_stability(played_frames, median_freq)
            stab_score = stability_result.stability_score

    # ── Slide score (placeholder for B3) ─────────────────────
    slide_score = 100.0  # TODO: integrate slide quality analyzer when available

    # ── Weighted overall score ───────────────────────────────
    w = WEIGHTS.get(exercise_type, DEFAULT_WEIGHTS)
    overall = (
        w["pitch"] * pitch_score
        + w["stability"] * stab_score
        + w["slide"] * slide_score
        + w["rhythm"] * rhythm_score
    )

    # ── Feedback ─────────────────────────────────────────────
    recommended = _recommend_training(pitch_score, stab_score, rhythm_score)
    feedback = _generate_feedback(overall, pitch_score, stab_score, rhythm_score, exercise_type)

    return EvaluationResult(
        overall_score=round(overall, 2),
        pitch_score=round(pitch_score, 2),
        stability_score=round(stab_score, 2),
        slide_score=round(slide_score, 2),
        rhythm_score=round(rhythm_score, 2),
        recommended_training_type=recommended,
        textual_feedback=feedback,
        dtw_result=dtw_result,
        stability_result=stability_result,
    )
