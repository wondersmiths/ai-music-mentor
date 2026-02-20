#!/usr/bin/env python3
"""
Verification script for ErhuOnsetDetector.

Generates synthetic audio signals that simulate Erhu playing patterns
and verifies the onset detector produces correct results.

Run:  python -m ai.pitch.verify_erhu_onset
"""

from __future__ import annotations

import math
import sys

import numpy as np

from ai.pitch.erhu_onset import ErhuOnsetDetector

# ── Helpers ──────────────────────────────────────────────────

SAMPLE_RATE = 16000
FRAME_SIZE = 2048

# Erhu note frequencies (Hz)
D4 = 293.66
E4 = 329.63
Fs4 = 369.99  # F#4
A4 = 440.00
B4 = 493.88
D5 = 587.33


def make_tone(freq: float, n_frames: int, amplitude: float = 0.5) -> np.ndarray:
    """Generate a pure sine tone lasting n_frames * FRAME_SIZE samples."""
    n_samples = n_frames * FRAME_SIZE
    t = np.arange(n_samples) / SAMPLE_RATE
    # Add a few harmonics to simulate Erhu timbre
    signal = amplitude * (
        np.sin(2 * np.pi * freq * t)
        + 0.4 * np.sin(2 * np.pi * 2 * freq * t)
        + 0.15 * np.sin(2 * np.pi * 3 * freq * t)
    )
    return signal


def make_silence(n_frames: int) -> np.ndarray:
    """Generate silence lasting n_frames * FRAME_SIZE samples."""
    return np.zeros(n_frames * FRAME_SIZE)


def make_glide(freq_start: float, freq_end: float, n_frames: int,
               amplitude: float = 0.5) -> np.ndarray:
    """Generate a smooth portamento glide between two frequencies."""
    n_samples = n_frames * FRAME_SIZE
    t = np.arange(n_samples) / SAMPLE_RATE
    # Log-linear frequency interpolation (perceptually uniform)
    log_start = math.log2(freq_start)
    log_end = math.log2(freq_end)
    frac = np.linspace(0, 1, n_samples)
    freq_curve = 2.0 ** (log_start + (log_end - log_start) * frac)
    # Instantaneous phase via cumulative sum
    phase = np.cumsum(2 * np.pi * freq_curve / SAMPLE_RATE)
    signal = amplitude * (
        np.sin(phase)
        + 0.4 * np.sin(2 * phase)
        + 0.15 * np.sin(3 * phase)
    )
    return signal


def make_noise(n_frames: int, amplitude: float = 0.005) -> np.ndarray:
    """Generate low-amplitude broadband noise (simulates bow noise)."""
    n_samples = n_frames * FRAME_SIZE
    return amplitude * np.random.randn(n_samples)


def feed_signal(det: ErhuOnsetDetector, signal: np.ndarray) -> list:
    """Feed a signal through the detector frame by frame."""
    onsets = []
    for i in range(0, len(signal) - FRAME_SIZE + 1, FRAME_SIZE):
        frame = signal[i:i + FRAME_SIZE]
        onset = det.feed(frame)
        if onset:
            onsets.append(onset)
    return onsets


def run_test(name: str, signal: np.ndarray, check_fn) -> bool:
    """Run a single test: feed signal, check result, print pass/fail."""
    det = ErhuOnsetDetector(
        sample_rate=SAMPLE_RATE,
        frame_size=FRAME_SIZE,
    )
    onsets = feed_signal(det, signal)
    result = det.result()

    try:
        check_fn(onsets, result)
        print(f"  PASS  {name}")
        return True
    except AssertionError as e:
        print(f"  FAIL  {name}: {e}")
        onset_times = [f"{o.time:.3f}s" for o in onsets]
        print(f"        onsets detected: {onset_times}")
        return False


# ── Test cases ───────────────────────────────────────────────

def test_stepwise_melody():
    """D4 → E4 → F#4 → A4, each held for 10 frames. Expect 4 onsets."""
    signal = np.concatenate([
        make_tone(D4, 10),
        make_tone(E4, 10),
        make_tone(Fs4, 10),
        make_tone(A4, 10),
    ])

    def check(onsets, result):
        assert len(onsets) >= 3, (
            f"expected ≥3 onsets for 4 notes, got {len(onsets)}"
        )
        assert len(onsets) <= 5, (
            f"expected ≤5 onsets for 4 notes, got {len(onsets)}"
        )
        # Onsets should be in chronological order
        times = [o.time for o in onsets]
        assert times == sorted(times), "onsets not in order"

    return run_test("Stepwise melody (D4→E4→F#4→A4)", signal, check)


def test_portamento_glide():
    """Smooth D4→A4 glide. Should NOT produce one onset per frame."""
    signal = make_glide(D4, A4, 30)

    def check(onsets, result):
        assert len(onsets) <= 3, (
            f"portamento should give ≤3 onsets, got {len(onsets)}"
        )

    return run_test("Portamento glide (D4→A4)", signal, check)


def test_silence_to_note():
    """Silence then D4 sustained. Expect 1 onset near sound entry."""
    signal = np.concatenate([
        make_silence(10),
        make_tone(D4, 15),
    ])

    def check(onsets, result):
        assert len(onsets) >= 1, "expected at least 1 onset after silence"
        assert len(onsets) <= 2, (
            f"expected ≤2 onsets for silence→note, got {len(onsets)}"
        )
        # First onset should be near the silence-to-sound boundary
        boundary_time = 10 * FRAME_SIZE / SAMPLE_RATE
        assert abs(onsets[0].time - boundary_time) < 1.0, (
            f"onset at {onsets[0].time:.3f}s too far from boundary "
            f"at {boundary_time:.3f}s"
        )

    return run_test("Silence → note (D4)", signal, check)


def test_repeated_pitch():
    """D4, silence gap, D4 again. Expect 2 onsets."""
    signal = np.concatenate([
        make_tone(D4, 10),
        make_silence(8),
        make_tone(D4, 10),
    ])

    def check(onsets, result):
        assert len(onsets) >= 2, (
            f"expected ≥2 onsets for repeated pitch, got {len(onsets)}"
        )
        assert len(onsets) <= 3, (
            f"expected ≤3 onsets for repeated pitch, got {len(onsets)}"
        )

    return run_test("Repeated same pitch (D4, gap, D4)", signal, check)


def test_bow_noise_suppression():
    """Low-amplitude broadband noise. Expect 0 onsets."""
    signal = make_noise(20)

    def check(onsets, result):
        assert len(onsets) == 0, (
            f"expected 0 onsets for bow noise, got {len(onsets)}"
        )

    return run_test("Bow noise suppression", signal, check)


def test_fast_articulation():
    """8 rapid notes at ~200 BPM (0.3s per note). Expect ~8 onsets with ≥150ms spacing."""
    freqs = [D4, E4, Fs4, A4, B4, D5, A4, Fs4]
    # At 200 BPM with eighth notes: ~0.15s per note → need enough frames
    # 0.3s per note = ~2.3 frames at 16kHz/2048
    frames_per_note = max(3, int(0.3 * SAMPLE_RATE / FRAME_SIZE))
    parts = [make_tone(f, frames_per_note) for f in freqs]
    signal = np.concatenate(parts)

    def check(onsets, result):
        assert len(onsets) >= 5, (
            f"expected ≥5 onsets for 8 rapid notes, got {len(onsets)}"
        )
        # Check minimum spacing (cooldown = 150ms)
        for i in range(1, len(onsets)):
            gap = onsets[i].time - onsets[i - 1].time
            assert gap >= 0.14, (
                f"onset gap {gap:.3f}s < 0.14s between onsets "
                f"{i-1} and {i}"
            )

    return run_test("Fast articulation (8 notes, ~200 BPM)", signal, check)


# ── Main ─────────────────────────────────────────────────────

def main():
    print("ErhuOnsetDetector verification")
    print("=" * 50)

    tests = [
        test_stepwise_melody,
        test_portamento_glide,
        test_silence_to_note,
        test_repeated_pitch,
        test_bow_noise_suppression,
        test_fast_articulation,
    ]

    results = [t() for t in tests]
    passed = sum(results)
    total = len(results)

    print("=" * 50)
    print(f"{passed}/{total} tests passed")

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
