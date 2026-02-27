"""
B2: Pitch stability analyzer (backend).

Analyzes a played pitch curve for stability around a target frequency.
Calculates mean deviation in cents, variance, and identifies unstable
segments. Tolerates vibrato within a configurable band (default ±20 cents).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class UnstableSegment:
    """A contiguous time range where pitch deviated beyond the stability threshold."""
    start_time: float
    end_time: float
    mean_deviation_cents: float


@dataclass
class StabilityResult:
    """Result of pitch stability analysis."""
    stability_score: float               # 0–100
    mean_deviation_cents: float          # signed mean (positive = sharp)
    variance_cents: float                # variance of cents deviations
    unstable_ranges: list[UnstableSegment] = field(default_factory=list)


def _freq_to_cents(detected: float, target: float) -> float:
    """Cents deviation from target. Positive = sharp, negative = flat."""
    if detected <= 0 or target <= 0:
        return 0.0
    return 1200.0 * np.log2(detected / target)


def analyze_stability(
    frames: list[tuple[float, float, float]],
    target_frequency: float,
    vibrato_tolerance_cents: float = 20.0,
    unstable_threshold_cents: float = 50.0,
    min_segment_duration: float = 0.1,
) -> StabilityResult:
    """
    Analyze pitch stability of a performance.

    Args:
        frames: list of (time, frequency, confidence) tuples.
        target_frequency: expected frequency in Hz.
        vibrato_tolerance_cents: deviation within this range is not penalized
            (accommodates natural vibrato). Default ±20 cents.
        unstable_threshold_cents: deviation beyond this marks an unstable segment.
        min_segment_duration: minimum duration (seconds) for an unstable segment
            to be reported.

    Returns:
        StabilityResult with score, deviations, and unstable ranges.
    """
    if target_frequency <= 0:
        return StabilityResult(
            stability_score=0.0,
            mean_deviation_cents=0.0,
            variance_cents=0.0,
        )

    # Filter: keep only frames with positive frequency
    valid = [(t, f, c) for t, f, c in frames if f > 0]

    if not valid:
        return StabilityResult(
            stability_score=0.0,
            mean_deviation_cents=0.0,
            variance_cents=0.0,
        )

    times = np.array([t for t, _, _ in valid])
    freqs = np.array([f for _, f, _ in valid])

    # Convert to cents deviation from target
    cents = 1200.0 * np.log2(freqs / target_frequency)

    mean_cents = float(np.mean(cents))
    variance = float(np.var(cents))

    # Scoring: penalize deviations beyond vibrato tolerance
    abs_cents = np.abs(cents)
    # Excess deviation beyond vibrato band
    excess = np.maximum(abs_cents - vibrato_tolerance_cents, 0.0)
    # Mean excess as fraction of a semitone (100 cents)
    mean_excess = float(np.mean(excess))
    # Score: 100 when mean_excess=0, drops toward 0 as excess grows
    # Linear ramp: 0 excess → 100, 80+ cents excess → 0
    score = max(0.0, 100.0 * (1.0 - mean_excess / 80.0))

    # Identify unstable segments (contiguous frames beyond threshold)
    unstable_mask = abs_cents > unstable_threshold_cents
    segments: list[UnstableSegment] = []

    if np.any(unstable_mask):
        # Find contiguous runs of True in unstable_mask
        changes = np.diff(unstable_mask.astype(int))
        starts = np.where(changes == 1)[0] + 1
        ends = np.where(changes == -1)[0] + 1

        # Handle edge cases: starts/ends at boundaries
        if unstable_mask[0]:
            starts = np.concatenate(([0], starts))
        if unstable_mask[-1]:
            ends = np.concatenate((ends, [len(unstable_mask)]))

        for s, e in zip(starts, ends):
            seg_times = times[s:e]
            seg_cents = cents[s:e]
            duration = float(seg_times[-1] - seg_times[0]) if len(seg_times) > 1 else 0.0

            if duration >= min_segment_duration:
                segments.append(UnstableSegment(
                    start_time=round(float(seg_times[0]), 4),
                    end_time=round(float(seg_times[-1]), 4),
                    mean_deviation_cents=round(float(np.mean(seg_cents)), 2),
                ))

    return StabilityResult(
        stability_score=round(score, 2),
        mean_deviation_cents=round(mean_cents, 2),
        variance_cents=round(variance, 2),
        unstable_ranges=segments,
    )
