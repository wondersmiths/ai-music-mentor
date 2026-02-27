"""
Unit tests for B1: DTW alignment service.
"""

from __future__ import annotations

import numpy as np
import pytest

from ai.evaluation.dtw import DTWResult, dtw_align


# ── Helpers ──────────────────────────────────────────────────

def make_curve(freq: float, duration: float, fps: int = 50) -> list[tuple[float, float]]:
    """Generate a constant-pitch curve."""
    return [(i / fps, freq) for i in range(int(duration * fps))]


def make_scale_curve(
    freqs: list[float], note_duration: float = 0.5, fps: int = 50
) -> list[tuple[float, float]]:
    """Generate a scale curve with one frequency per note."""
    curve = []
    for i, freq in enumerate(freqs):
        t_start = i * note_duration
        for j in range(int(note_duration * fps)):
            curve.append((t_start + j / fps, freq))
    return curve


# ── Identical curves → perfect alignment ─────────────────────

class TestIdenticalCurves:
    def test_zero_pitch_error(self):
        ref = make_curve(440.0, 1.0)
        result = dtw_align(ref, ref)

        assert result.pitch_error_mean == 0.0
        assert result.timing_deviation == 0.0

    def test_alignment_path_is_diagonal(self):
        ref = make_curve(440.0, 0.5)
        result = dtw_align(ref, ref)

        # On identical curves, path should be diagonal
        for i, (pi, ri) in enumerate(result.alignment_path):
            assert pi == ri == i


# ── Pitch offset → measured error ────────────────────────────

class TestPitchError:
    def test_constant_offset_measured(self):
        ref = make_curve(440.0, 1.0)
        # ~100 cents sharp (one semitone)
        played = make_curve(440.0 * 2 ** (100 / 1200), 1.0)

        result = dtw_align(played, ref)
        assert result.pitch_error_mean == pytest.approx(100.0, abs=1.0)

    def test_small_offset(self):
        ref = make_curve(440.0, 1.0)
        # 20 cents sharp
        played = make_curve(440.0 * 2 ** (20 / 1200), 1.0)

        result = dtw_align(played, ref)
        assert result.pitch_error_mean == pytest.approx(20.0, abs=1.0)


# ── Timing offset → measured deviation ───────────────────────

class TestTimingDeviation:
    def test_shifted_curve(self):
        fps = 50
        ref = make_curve(440.0, 1.0, fps)
        # Shift played by 0.2 seconds
        played = [(t + 0.2, f) for t, f in ref]

        result = dtw_align(played, ref)
        # Timing deviation should reflect the shift
        assert result.timing_deviation > 0.0

    def test_no_shift_zero_deviation(self):
        ref = make_curve(440.0, 1.0)
        result = dtw_align(ref, ref)
        assert result.timing_deviation == 0.0


# ── Zero-frequency filtering ────────────────────────────────

class TestZeroFrequencyFiltering:
    def test_silence_frames_excluded(self):
        ref = make_curve(440.0, 0.5)
        # Played has some silence gaps
        played = [(0.0, 440.0), (0.02, 0.0), (0.04, 440.0), (0.06, 0.0), (0.08, 440.0)]

        result = dtw_align(played, ref)
        # Should still produce a result — silence frames filtered out
        assert len(result.alignment_path) > 0
        assert result.pitch_error_mean == pytest.approx(0.0, abs=1.0)

    def test_all_silence_returns_empty(self):
        ref = make_curve(440.0, 0.5)
        played = [(0.0, 0.0), (0.02, 0.0)]

        result = dtw_align(played, ref)
        assert result.alignment_path == []
        assert result.pitch_error_mean == 0.0


# ── Warped curve ─────────────────────────────────────────────

class TestWarpedCurve:
    def test_warped_curve_has_ref_timing(self):
        ref = make_curve(440.0, 0.5)
        played = make_curve(441.0, 0.5)

        result = dtw_align(played, ref)
        # Warped curve should use reference timing
        ref_times = [t for t, _ in ref]
        warped_times = [t for t, _ in result.warped_curve]
        for wt in warped_times:
            assert wt in ref_times

    def test_warped_curve_has_played_frequencies(self):
        ref = make_curve(440.0, 0.5)
        played = make_curve(441.0, 0.5)

        result = dtw_align(played, ref)
        for _, freq in result.warped_curve:
            assert freq == pytest.approx(441.0, abs=0.01)


# ── Edge cases ───────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_played(self):
        ref = make_curve(440.0, 0.5)
        result = dtw_align([], ref)
        assert result.alignment_path == []

    def test_empty_reference(self):
        played = make_curve(440.0, 0.5)
        result = dtw_align(played, [])
        assert result.alignment_path == []

    def test_single_frame_each(self):
        result = dtw_align([(0.0, 440.0)], [(0.0, 440.0)])
        assert len(result.alignment_path) == 1
        assert result.pitch_error_mean == 0.0

    def test_scale_alignment(self):
        """Two identical scales should align with near-zero error."""
        freqs = [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88, 523.25]
        ref = make_scale_curve(freqs)
        played = make_scale_curve(freqs)

        result = dtw_align(played, ref)
        assert result.pitch_error_mean == pytest.approx(0.0, abs=0.1)
        assert result.timing_deviation == pytest.approx(0.0, abs=0.001)
