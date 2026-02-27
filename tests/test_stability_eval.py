"""
Unit tests for B2: Backend pitch stability analyzer.
"""

from __future__ import annotations

import numpy as np
import pytest

from ai.evaluation.stability import StabilityResult, UnstableSegment, analyze_stability


# ── Helpers ──────────────────────────────────────────────────

def make_frames(
    freq: float, duration: float = 2.0, fps: int = 50, confidence: float = 0.9
) -> list[tuple[float, float, float]]:
    """Generate constant-frequency frames."""
    return [(i / fps, freq, confidence) for i in range(int(duration * fps))]


# ── Perfect pitch → score 100 ────────────────────────────────

class TestPerfectPitch:
    def test_score_100_on_target(self):
        frames = make_frames(440.0, duration=2.0)
        result = analyze_stability(frames, target_frequency=440.0)

        assert result.stability_score == 100.0
        assert result.mean_deviation_cents == pytest.approx(0.0, abs=0.1)
        assert result.variance_cents == pytest.approx(0.0, abs=0.1)
        assert result.unstable_ranges == []


# ── Vibrato tolerance ────────────────────────────────────────

class TestVibratoTolerance:
    def test_small_vibrato_high_score(self):
        """±15 cents vibrato (within 20 cent tolerance) should score well."""
        frames = []
        for i in range(100):
            t = i / 50
            cents = 15 * np.sin(2 * np.pi * 6 * t)
            freq = 440.0 * 2 ** (cents / 1200)
            frames.append((t, freq, 0.9))

        result = analyze_stability(frames, target_frequency=440.0)
        assert result.stability_score >= 90.0

    def test_vibrato_within_tolerance_no_unstable(self):
        """Vibrato within ±20 cents should not produce unstable segments (at 50 cent threshold)."""
        frames = []
        for i in range(100):
            t = i / 50
            cents = 18 * np.sin(2 * np.pi * 5 * t)
            freq = 440.0 * 2 ** (cents / 1200)
            frames.append((t, freq, 0.9))

        result = analyze_stability(frames, target_frequency=440.0)
        assert result.unstable_ranges == []


# ── Deviation → lower score ──────────────────────────────────

class TestDeviation:
    def test_sustained_offset_lower_score(self):
        """40 cents sharp → significantly lower score."""
        freq = 440.0 * 2 ** (40 / 1200)
        frames = make_frames(freq, duration=2.0)

        result = analyze_stability(frames, target_frequency=440.0)
        assert result.stability_score < 80
        assert result.mean_deviation_cents > 30

    def test_large_offset_low_score(self):
        """80 cents sharp → very low score."""
        freq = 440.0 * 2 ** (80 / 1200)
        frames = make_frames(freq, duration=2.0)

        result = analyze_stability(frames, target_frequency=440.0)
        assert result.stability_score < 30


# ── Unstable segments ────────────────────────────────────────

class TestUnstableSegments:
    def test_detects_unstable_region(self):
        """A burst of high deviation should produce an unstable segment."""
        frames = []
        fps = 50
        # First second: on target
        for i in range(fps):
            frames.append((i / fps, 440.0, 0.9))
        # Second second: 60 cents off (beyond 50 cent threshold)
        off_freq = 440.0 * 2 ** (60 / 1200)
        for i in range(fps):
            frames.append(((fps + i) / fps, off_freq, 0.9))
        # Third second: back on target
        for i in range(fps):
            frames.append(((2 * fps + i) / fps, 440.0, 0.9))

        result = analyze_stability(frames, target_frequency=440.0)
        assert len(result.unstable_ranges) >= 1
        seg = result.unstable_ranges[0]
        assert seg.start_time >= 0.9
        assert seg.end_time <= 2.1
        assert abs(seg.mean_deviation_cents) > 40


# ── Zero frequency filtering ────────────────────────────────

class TestZeroFrequency:
    def test_silence_frames_excluded(self):
        frames = [
            (0.0, 440.0, 0.9),
            (0.02, 0.0, 0.9),   # silence
            (0.04, 440.0, 0.9),
            (0.06, 0.0, 0.0),   # silence
            (0.08, 440.0, 0.9),
        ]
        result = analyze_stability(frames, target_frequency=440.0)
        assert result.stability_score == 100.0

    def test_all_silence_returns_zero(self):
        frames = [(0.0, 0.0, 0.9), (0.02, 0.0, 0.5)]
        result = analyze_stability(frames, target_frequency=440.0)
        assert result.stability_score == 0.0


# ── Edge cases ───────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_frames(self):
        result = analyze_stability([], target_frequency=440.0)
        assert result.stability_score == 0.0

    def test_zero_target_frequency(self):
        frames = make_frames(440.0)
        result = analyze_stability(frames, target_frequency=0.0)
        assert result.stability_score == 0.0

    def test_single_frame(self):
        result = analyze_stability([(0.0, 440.0, 0.9)], target_frequency=440.0)
        assert result.stability_score == 100.0
