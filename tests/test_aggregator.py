"""
Unit tests for B5: Evaluation aggregator.
"""

from __future__ import annotations

import numpy as np
import pytest

from ai.evaluation.aggregator import EvaluationResult, evaluate


# ── Helpers ──────────────────────────────────────────────────

def make_frames(
    freq: float, duration: float = 2.0, fps: int = 50, confidence: float = 0.9
) -> list[tuple[float, float, float]]:
    """Generate constant-frequency frames."""
    return [(i / fps, freq, confidence) for i in range(int(duration * fps))]


def make_ref_curve(freq: float, duration: float = 2.0, fps: int = 50) -> list[tuple[float, float]]:
    return [(i / fps, freq) for i in range(int(duration * fps))]


# ── Long tone evaluation ────────────────────────────────────

class TestLongTone:
    def test_perfect_long_tone(self):
        frames = make_frames(440.0, duration=5.0)
        result = evaluate(
            played_frames=frames,
            exercise_type="long_tone",
            target_frequency=440.0,
        )

        assert result.overall_score >= 95
        assert result.pitch_score >= 95
        assert result.stability_score >= 95
        assert result.stability_result is not None
        assert "Excellent" in result.textual_feedback

    def test_off_pitch_long_tone(self):
        freq = 440.0 * 2 ** (50 / 1200)  # 50 cents sharp
        frames = make_frames(freq, duration=5.0)
        result = evaluate(
            played_frames=frames,
            exercise_type="long_tone",
            target_frequency=440.0,
        )

        assert result.pitch_score < 60
        assert result.overall_score < 80


# ── Scale / melody with reference curve ──────────────────────

class TestWithReference:
    def test_perfect_match(self):
        frames = make_frames(440.0, duration=2.0)
        ref = make_ref_curve(440.0, duration=2.0)

        result = evaluate(
            played_frames=frames,
            exercise_type="scale",
            reference_curve=ref,
            target_frequency=440.0,
        )

        assert result.overall_score >= 95
        assert result.pitch_score >= 95
        assert result.dtw_result is not None

    def test_pitch_mismatch(self):
        played = make_frames(440.0 * 2 ** (80 / 1200), duration=2.0)
        ref = make_ref_curve(440.0, duration=2.0)

        result = evaluate(
            played_frames=played,
            exercise_type="scale",
            reference_curve=ref,
            target_frequency=440.0,
        )

        assert result.pitch_score < 30
        assert result.dtw_result is not None
        assert result.dtw_result.pitch_error_mean > 70


# ── Feedback content ─────────────────────────────────────────

class TestFeedback:
    def test_encouragement_for_good_score(self):
        frames = make_frames(440.0, duration=2.0)
        result = evaluate(frames, "long_tone", target_frequency=440.0)
        assert "Excellent" in result.textual_feedback or "Good" in result.textual_feedback

    def test_weakness_mentioned_for_low_score(self):
        freq = 440.0 * 2 ** (70 / 1200)
        frames = make_frames(freq, duration=2.0)
        result = evaluate(frames, "long_tone", target_frequency=440.0)
        assert "Focus on" in result.textual_feedback or "Try" in result.textual_feedback

    def test_recommended_training_type_valid(self):
        frames = make_frames(440.0, duration=2.0)
        result = evaluate(frames, "long_tone", target_frequency=440.0)
        assert result.recommended_training_type in ("long_tone", "scale", "rhythm_drill")


# ── Weight profiles ──────────────────────────────────────────

class TestWeights:
    def test_long_tone_weights_stability_higher(self):
        """Long tone should weight stability more than pitch."""
        # Slightly off pitch but very stable
        freq = 440.0 * 2 ** (15 / 1200)  # 15 cents sharp
        frames = make_frames(freq, duration=2.0)

        result = evaluate(frames, "long_tone", target_frequency=440.0)
        # Should still score well because stability is high and weighted heavily
        assert result.overall_score >= 80


# ── Edge cases ───────────────────────────────────────────────

class TestEdgeCases:
    def test_no_target_no_reference(self):
        """With no target or reference, should still return scores (defaults)."""
        frames = make_frames(440.0, duration=1.0)
        result = evaluate(frames, "long_tone")
        assert result.overall_score > 0

    def test_all_result_fields_present(self):
        frames = make_frames(440.0, duration=1.0)
        result = evaluate(frames, "long_tone", target_frequency=440.0)

        assert isinstance(result.overall_score, float)
        assert isinstance(result.pitch_score, float)
        assert isinstance(result.stability_score, float)
        assert isinstance(result.slide_score, float)
        assert isinstance(result.rhythm_score, float)
        assert isinstance(result.recommended_training_type, str)
        assert isinstance(result.textual_feedback, str)
