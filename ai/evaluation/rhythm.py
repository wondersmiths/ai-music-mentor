"""
B4: Rhythm consistency analyzer.

Compares detected onset timestamps against an expected BPM grid to measure
rhythmic accuracy. Calculates average deviation, tempo drift, and a
consistency score.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np


@dataclass
class RhythmResult:
    """Result of rhythm consistency analysis."""
    rhythm_score: float              # 0–100
    mean_deviation_ms: float         # mean absolute onset deviation in ms
    max_deviation_ms: float          # worst single onset deviation in ms
    tempo_drift: float               # estimated tempo drift in BPM (positive = speeding up)
    onset_count: int                 # number of detected onsets analyzed
    expected_onset_count: int        # number of expected grid onsets


def _build_beat_grid(
    bpm: float,
    beats_per_measure: int,
    num_measures: int,
    offset: float = 0.0,
) -> np.ndarray:
    """
    Build an expected onset grid based on BPM and measure count.

    Returns an array of expected onset times in seconds.
    Each beat position gets an entry.
    """
    sec_per_beat = 60.0 / bpm
    total_beats = beats_per_measure * num_measures
    return np.array([offset + i * sec_per_beat for i in range(total_beats)])


def _match_onsets_to_grid(
    onsets: np.ndarray,
    grid: np.ndarray,
    max_window: float = 0.3,
) -> List[Optional[float]]:
    """
    Match each grid point to the nearest onset within max_window seconds.

    Returns a list of deviations in seconds (None if no match found).
    """
    if len(onsets) == 0:
        return [None] * len(grid)

    deviations: List[Optional[float]] = []
    for expected_time in grid:
        diffs = onsets - expected_time
        abs_diffs = np.abs(diffs)
        min_idx = int(np.argmin(abs_diffs))

        if abs_diffs[min_idx] <= max_window:
            deviations.append(float(diffs[min_idx]))
        else:
            deviations.append(None)

    return deviations


def analyze_rhythm(
    onset_times: List[float],
    bpm: float,
    beats_per_measure: int = 4,
    num_measures: int = 0,
    duration: float = 0.0,
) -> RhythmResult:
    """
    Analyze rhythmic consistency of detected onsets against a BPM grid.

    Args:
        onset_times: list of detected onset timestamps in seconds.
        bpm: expected tempo in beats per minute.
        beats_per_measure: time signature numerator (default 4).
        num_measures: number of measures to analyze. If 0, inferred from
            duration or onset span.
        duration: total duration in seconds (used to infer measure count
            if num_measures is 0).

    Returns:
        RhythmResult with score, deviations, and drift estimate.
    """
    if bpm <= 0:
        return RhythmResult(
            rhythm_score=0.0,
            mean_deviation_ms=0.0,
            max_deviation_ms=0.0,
            tempo_drift=0.0,
            onset_count=len(onset_times),
            expected_onset_count=0,
        )

    onsets = np.array(sorted(onset_times)) if onset_times else np.array([])

    # Infer measure count if not provided
    if num_measures <= 0:
        sec_per_beat = 60.0 / bpm
        sec_per_measure = sec_per_beat * beats_per_measure
        span = duration if duration > 0 else (float(onsets[-1]) if len(onsets) > 0 else 0.0)
        num_measures = max(1, int(np.ceil(span / sec_per_measure))) if span > 0 else 1

    # Build expected grid
    grid = _build_beat_grid(bpm, beats_per_measure, num_measures)

    if len(onsets) == 0:
        return RhythmResult(
            rhythm_score=0.0,
            mean_deviation_ms=0.0,
            max_deviation_ms=0.0,
            tempo_drift=0.0,
            onset_count=0,
            expected_onset_count=len(grid),
        )

    # Match onsets to grid
    deviations = _match_onsets_to_grid(onsets, grid)

    # Filter matched deviations
    matched = [d for d in deviations if d is not None]

    if not matched:
        return RhythmResult(
            rhythm_score=0.0,
            mean_deviation_ms=0.0,
            max_deviation_ms=0.0,
            tempo_drift=0.0,
            onset_count=len(onsets),
            expected_onset_count=len(grid),
        )

    matched_arr = np.array(matched)
    abs_devs = np.abs(matched_arr)

    mean_dev_ms = float(np.mean(abs_devs)) * 1000
    max_dev_ms = float(np.max(abs_devs)) * 1000

    # Coverage: fraction of grid points that got matched
    coverage = len(matched) / len(grid) if len(grid) > 0 else 0.0

    # Score: 100 when mean_dev=0, drops toward 0 at 200ms+ mean deviation
    # Also penalize low coverage
    accuracy_score = max(0.0, 100.0 * (1.0 - mean_dev_ms / 200.0))
    coverage_score = coverage * 100.0
    rhythm_score = 0.6 * accuracy_score + 0.4 * coverage_score

    # Tempo drift: linear regression on matched deviations over time
    # Positive slope = gradually getting late = slowing down
    tempo_drift = 0.0
    if len(matched) >= 3:
        matched_indices = [i for i, d in enumerate(deviations) if d is not None]
        matched_times = grid[matched_indices]
        if matched_times[-1] > matched_times[0]:
            # Fit linear: deviation = a * time + b
            coeffs = np.polyfit(matched_times, matched_arr, 1)
            slope = coeffs[0]  # seconds of drift per second
            # Convert to BPM drift: if drifting +0.01 s/s, that's ~1.2 BPM slow
            tempo_drift = round(-slope * bpm, 2)

    return RhythmResult(
        rhythm_score=round(rhythm_score, 2),
        mean_deviation_ms=round(mean_dev_ms, 2),
        max_deviation_ms=round(max_dev_ms, 2),
        tempo_drift=tempo_drift,
        onset_count=len(onsets),
        expected_onset_count=len(grid),
    )
