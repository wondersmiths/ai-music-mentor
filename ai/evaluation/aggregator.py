"""
B5: Evaluation aggregator.

Combines DTW alignment, pitch stability, and (future) slide/rhythm metrics
into a single evaluation result with overall score, sub-scores,
recommended training type, and textual feedback.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ai.evaluation.dtw import DTWResult, dtw_align

logger = logging.getLogger(__name__)
from ai.evaluation.onset_from_pitch import detect_onsets_from_pitch
from ai.evaluation.rhythm import RhythmResult, analyze_rhythm
from ai.evaluation.slide import SlideResult, analyze_slides
from ai.evaluation.stability import StabilityResult, analyze_stability


@dataclass
class EvaluationResult:
    """Aggregated evaluation of a practice session."""
    overall_score: float          # 0–100
    pitch_score: float            # 0–100 (from DTW pitch error)
    stability_score: float        # 0–100 (from stability analyzer)
    slide_score: float            # 0–100 (from slide quality analyzer)
    rhythm_score: float           # 0–100 (from rhythm consistency analyzer)
    recommended_training_type: str
    textual_feedback: str
    dtw_result: DTWResult | None = None
    stability_result: StabilityResult | None = None
    slide_result: SlideResult | None = None
    rhythm_result: RhythmResult | None = None


# ── Score weights by exercise type ──────────────────────────

WEIGHTS = {
    "long_tone": {"pitch": 0.3, "stability": 0.5, "slide": 0.0, "rhythm": 0.2},
    "scale":     {"pitch": 0.4, "stability": 0.2, "slide": 0.1, "rhythm": 0.3},
    "melody":    {"pitch": 0.35, "stability": 0.15, "slide": 0.15, "rhythm": 0.35},
}
DEFAULT_WEIGHTS = {"pitch": 0.35, "stability": 0.25, "slide": 0.1, "rhythm": 0.3}


# ── Stability from DTW alignment (for scale/melody) ────────

def _stability_from_dtw(
    played: list[tuple[float, float]],
    reference: list[tuple[float, float]],
    dtw_result: DTWResult,
) -> float:
    """
    Compute per-note stability using DTW alignment.

    For each played frame, compare it against the matched reference frequency.
    This avoids the single-target problem where scale/melody stability is
    always 0 because the student is supposed to play different pitches.
    """
    import numpy as np

    played_clean = [(t, f) for t, f in played if f > 0]
    ref_clean = [(t, f) for t, f in reference if f > 0]

    if not played_clean or not ref_clean or not dtw_result.alignment_path:
        return 100.0

    played_freqs = np.array([f for _, f in played_clean])
    ref_freqs = np.array([f for _, f in ref_clean])

    # Compute cents deviation for each aligned pair
    cents_devs = []
    for pi, ri in dtw_result.alignment_path:
        pf = played_freqs[pi]
        rf = ref_freqs[ri]
        if pf > 0 and rf > 0:
            cents_devs.append(abs(1200.0 * np.log2(pf / rf)))

    if not cents_devs:
        return 100.0

    # Stability = how consistently the player matches the reference.
    # Mean deviation within 20 cents (vibrato band) → 100.
    # Excess beyond vibrato band penalizes, 80+ cents excess → 0.
    abs_cents = np.array(cents_devs)
    excess = np.maximum(abs_cents - 20.0, 0.0)
    mean_excess = float(np.mean(excess))
    return max(0.0, round(100.0 * (1.0 - mean_excess / 80.0), 2))


# ── Pitch score from DTW cents error ────────────────────────

def _pitch_score_from_error(mean_cents_error: float) -> float:
    """
    Convert mean pitch error in cents to a 0–100 score.
    0 cents → 100, 200+ cents → 0. Linear ramp.
    Generous threshold accounts for natural vibrato and pitch detection noise.
    """
    return max(0.0, 100.0 * (1.0 - mean_cents_error / 200.0))


# ── Rhythm score from timing deviation ──────────────────────

def _rhythm_score_from_deviation(timing_dev: float) -> float:
    """
    Convert mean timing deviation in seconds to 0–100 score.
    0s → 100, 1.0s+ → 0. Linear ramp.
    """
    return max(0.0, 100.0 * (1.0 - timing_dev / 1.0))


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
        logger.info(
            "DTW: pitch_error_mean=%.1f cents, timing_dev=%.3fs → "
            "pitch_score=%.1f, rhythm_score=%.1f, path_len=%d",
            dtw_result.pitch_error_mean, dtw_result.timing_deviation,
            pitch_score, rhythm_score, len(dtw_result.alignment_path),
        )
    elif target_frequency and target_frequency > 0:
        # For long_tone: measure pitch accuracy as mean deviation from target
        valid_freqs = [f for _, f, _ in played_frames if f > 0]
        if valid_freqs:
            import numpy as np
            cents = [abs(1200.0 * np.log2(f / target_frequency)) for f in valid_freqs]
            mean_cents = float(np.mean(cents))
            pitch_score = _pitch_score_from_error(mean_cents)
            logger.info(
                "Long tone pitch: target=%.1f Hz, played_mean=%.1f Hz, "
                "mean_cents_error=%.1f → pitch_score=%.1f",
                target_frequency, float(np.mean(valid_freqs)),
                mean_cents, pitch_score,
            )

    # ── Stability analysis ───────────────────────────────────
    stability_result: StabilityResult | None = None
    stab_score = 100.0

    if target_frequency and target_frequency > 0:
        stability_result = analyze_stability(played_frames, target_frequency)
        stab_score = stability_result.stability_score
        logger.info(
            "Stability (target=%.1f Hz): mean_dev=%.1f cents, "
            "variance=%.1f → score=%.1f",
            target_frequency, stability_result.mean_deviation_cents,
            stability_result.variance_cents, stab_score,
        )
    elif reference_curve and dtw_result and dtw_result.alignment_path:
        # For scale/melody: measure stability per-note using DTW alignment.
        # For each played frame, the "target" is the matched reference freq.
        stab_score = _stability_from_dtw(played_tf, reference_curve, dtw_result)
        logger.info(
            "Stability (per-note via DTW): score=%.1f", stab_score,
        )

    # ── Slide score ──────────────────────────────────────────
    slide_result = analyze_slides(played_frames)
    slide_score = slide_result.slide_score

    # ── Rhythm score ──────────────────────────────────────────
    rhythm_result: RhythmResult | None = None
    if reference_curve and bpm and bpm > 0:
        onset_times = detect_onsets_from_pitch(played_frames)
        duration = played_frames[-1][0] if played_frames else 0.0
        rhythm_result = analyze_rhythm(
            onset_times=onset_times,
            bpm=bpm,
            duration=duration,
        )
        rhythm_score = rhythm_result.rhythm_score

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
        slide_result=slide_result,
        rhythm_result=rhythm_result,
    )
