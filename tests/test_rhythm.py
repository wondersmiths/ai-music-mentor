"""
Unit tests for B4: Rhythm consistency analyzer.
"""

from __future__ import annotations

import numpy as np
import pytest

from ai.evaluation.rhythm import RhythmResult, analyze_rhythm


# ── Perfect rhythm ───────────────────────────────────────────

class TestPerfectRhythm:
    def test_perfect_onsets_score_100(self):
        """Onsets exactly on the beat grid → score 100."""
        bpm = 120
        sec_per_beat = 60 / bpm
        onsets = [i * sec_per_beat for i in range(8)]  # 2 measures of 4/4

        result = analyze_rhythm(onsets, bpm=120, beats_per_measure=4, num_measures=2)
        assert result.rhythm_score >= 95
        assert result.mean_deviation_ms < 1.0

    def test_perfect_3_4_time(self):
        bpm = 100
        sec_per_beat = 60 / bpm
        onsets = [i * sec_per_beat for i in range(6)]  # 2 measures of 3/4

        result = analyze_rhythm(onsets, bpm=100, beats_per_measure=3, num_measures=2)
        assert result.rhythm_score >= 95


# ── Small deviations ────────────────────────────────────────

class TestSmallDeviations:
    def test_small_jitter_still_high_score(self):
        """±20ms jitter should still score well."""
        bpm = 120
        sec_per_beat = 60 / bpm
        np.random.seed(42)
        jitter = np.random.uniform(-0.02, 0.02, 8)
        onsets = [i * sec_per_beat + jitter[i] for i in range(8)]

        result = analyze_rhythm(onsets, bpm=120, beats_per_measure=4, num_measures=2)
        assert result.rhythm_score >= 80
        assert result.mean_deviation_ms < 30

    def test_moderate_deviation_lower_score(self):
        """±100ms deviation should lower the score significantly."""
        bpm = 120
        sec_per_beat = 60 / bpm
        np.random.seed(42)
        jitter = np.random.uniform(-0.1, 0.1, 8)
        onsets = [i * sec_per_beat + jitter[i] for i in range(8)]

        result = analyze_rhythm(onsets, bpm=120, beats_per_measure=4, num_measures=2)
        assert result.rhythm_score < 92


# ── Missing onsets ──────────────────────────────────────────

class TestMissingOnsets:
    def test_half_onsets_lowers_coverage(self):
        """Only hitting half the beats should reduce the score."""
        bpm = 120
        sec_per_beat = 60 / bpm
        # Only even beats
        onsets = [i * sec_per_beat for i in range(0, 8, 2)]

        result = analyze_rhythm(onsets, bpm=120, beats_per_measure=4, num_measures=2)
        assert result.rhythm_score <= 80

    def test_no_onsets_score_zero(self):
        result = analyze_rhythm([], bpm=120, beats_per_measure=4, num_measures=2)
        assert result.rhythm_score == 0.0
        assert result.onset_count == 0


# ── Tempo drift ─────────────────────────────────────────────

class TestTempoDrift:
    def test_gradual_slowdown_detected(self):
        """Onsets that gradually come later should show negative drift."""
        bpm = 120
        sec_per_beat = 60 / bpm
        # Each beat is 10ms later than expected (cumulative)
        onsets = [i * sec_per_beat + i * 0.01 for i in range(16)]

        result = analyze_rhythm(onsets, bpm=120, beats_per_measure=4, num_measures=4)
        # Tempo drift should be negative (slowing down)
        assert result.tempo_drift < 0

    def test_steady_tempo_no_drift(self):
        bpm = 120
        sec_per_beat = 60 / bpm
        onsets = [i * sec_per_beat for i in range(16)]

        result = analyze_rhythm(onsets, bpm=120, beats_per_measure=4, num_measures=4)
        assert abs(result.tempo_drift) < 1.0


# ── Edge cases ──────────────────────────────────────────────

class TestEdgeCases:
    def test_zero_bpm(self):
        result = analyze_rhythm([0.0, 0.5], bpm=0)
        assert result.rhythm_score == 0.0

    def test_single_onset(self):
        result = analyze_rhythm([0.0], bpm=120, beats_per_measure=4, num_measures=1)
        assert result.rhythm_score > 0
        assert result.onset_count == 1

    def test_inferred_measures_from_duration(self):
        """When num_measures=0, infer from duration."""
        bpm = 120
        sec_per_beat = 60 / bpm
        onsets = [i * sec_per_beat for i in range(8)]

        result = analyze_rhythm(onsets, bpm=120, beats_per_measure=4, duration=4.0)
        assert result.expected_onset_count == 8  # 2 measures × 4 beats

    def test_score_always_in_range(self):
        """Score should never exceed 0–100."""
        bpm = 120
        sec_per_beat = 60 / bpm
        onsets = [i * sec_per_beat + 0.05 for i in range(4)]

        result = analyze_rhythm(onsets, bpm=120, beats_per_measure=4, num_measures=1)
        assert 0 <= result.rhythm_score <= 100
