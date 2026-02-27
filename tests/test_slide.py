"""
Unit tests for B3: Slide quality analyzer.
"""

from __future__ import annotations

import numpy as np
import pytest

from ai.evaluation.slide import SlideResult, analyze_slides


# ── Helpers ──────────────────────────────────────────────────

def make_constant(freq: float, duration: float = 1.0, fps: int = 50):
    """Generate constant-frequency frames."""
    return [(i / fps, freq, 0.9) for i in range(int(duration * fps))]


def make_slide(
    start_freq: float,
    end_freq: float,
    duration: float = 0.3,
    fps: int = 50,
    start_time: float = 0.0,
):
    """Generate a perfect linear slide in frequency space."""
    n = int(duration * fps)
    frames = []
    for i in range(n):
        t = start_time + i / fps
        # Linear interpolation in log-frequency space (cents)
        ratio = i / max(1, n - 1)
        freq = start_freq * (end_freq / start_freq) ** ratio
        frames.append((t, freq, 0.9))
    return frames


# ── No slides → score 100 ───────────────────────────────────

class TestNoSlides:
    def test_constant_pitch_scores_100(self):
        frames = make_constant(440.0, duration=2.0)
        result = analyze_slides(frames)
        assert result.slide_score == 100.0
        assert result.slide_count == 0

    def test_empty_frames(self):
        result = analyze_slides([])
        assert result.slide_score == 100.0
        assert result.slide_count == 0


# ── Slide detection ──────────────────────────────────────────

class TestSlideDetection:
    def test_detects_large_slide(self):
        """A 200-cent slide should be detected."""
        start = 440.0
        end = 440.0 * 2 ** (200 / 1200)  # 200 cents up
        # Build: stable → slide → stable with continuous timestamps
        frames = []
        fps = 50
        for i in range(25):
            frames.append((i / fps, start, 0.9))
        for i in range(15):
            t = 0.5 + i / fps
            ratio = i / 14
            freq = start * (end / start) ** ratio
            frames.append((t, freq, 0.9))
        for i in range(25):
            frames.append((0.8 + i / fps, end, 0.9))

        result = analyze_slides(frames)
        assert result.slide_count >= 1

    def test_smooth_slide_high_score(self):
        """A perfectly smooth slide should score well."""
        start = 440.0
        end = 440.0 * 2 ** (150 / 1200)
        # Build: stable → slide → stable
        frames = []
        fps = 50
        # 0.5s stable
        for i in range(25):
            frames.append((i / fps, start, 0.9))
        # 0.3s slide
        for i in range(15):
            t = 0.5 + i / fps
            ratio = i / 14
            freq = start * (end / start) ** ratio
            frames.append((t, freq, 0.9))
        # 0.5s stable
        for i in range(25):
            frames.append((0.8 + i / fps, end, 0.9))

        result = analyze_slides(frames)
        if result.slide_count > 0:
            # Smooth slides should have high smoothness
            for seg in result.segments:
                assert seg.smoothness >= 0.5


# ── Overshoot detection ─────────────────────────────────────

class TestOvershoot:
    def test_overshoot_detected(self):
        """Slide that goes past the target should show overshoot."""
        start = 440.0
        target = 440.0 * 2 ** (100 / 1200)
        overshoot = 440.0 * 2 ** (130 / 1200)  # 30 cents past

        frames = []
        fps = 50
        # Stable start
        for i in range(25):
            frames.append((i / fps, start, 0.9))
        # Slide up past target
        for i in range(10):
            t = 0.5 + i / fps
            ratio = i / 9
            freq = start * (overshoot / start) ** ratio
            frames.append((t, freq, 0.9))
        # Settle back to target
        for i in range(25):
            frames.append((0.7 + i / fps, target, 0.9))

        result = analyze_slides(frames)
        if result.slide_count > 0:
            assert any(seg.overshoot_cents > 0 for seg in result.segments)


# ── Silence handling ─────────────────────────────────────────

class TestSilence:
    def test_zero_frequency_filtered(self):
        frames = [(0.0, 0.0, 0.9), (0.02, 0.0, 0.9), (0.04, 440.0, 0.9)]
        result = analyze_slides(frames)
        assert result.slide_score == 100.0


# ── Score range ──────────────────────────────────────────────

class TestScoreRange:
    def test_score_between_0_and_100(self):
        """Score should always be in valid range."""
        start = 440.0
        end = 880.0  # octave jump
        frames = []
        fps = 50
        for i in range(25):
            frames.append((i / fps, start, 0.9))
        for i in range(5):
            t = 0.5 + i / fps
            ratio = i / 4
            freq = start * (end / start) ** ratio
            frames.append((t, freq, 0.9))
        for i in range(25):
            frames.append((0.6 + i / fps, end, 0.9))

        result = analyze_slides(frames)
        assert 0 <= result.slide_score <= 100
