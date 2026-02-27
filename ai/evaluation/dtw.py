"""
B1: Dynamic Time Warping alignment service for pitch curves.

Aligns a played pitch curve against a reference curve, computing
alignment path, mean pitch error (cents), and timing deviation.
Uses numpy only — no external DTW libraries.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class DTWResult:
    """Result of DTW alignment between played and reference pitch curves."""
    alignment_path: list[tuple[int, int]]  # (played_idx, ref_idx) pairs
    pitch_error_mean: float                # mean absolute pitch error in cents
    timing_deviation: float                # mean absolute timing deviation in seconds
    warped_curve: list[tuple[float, float]]  # (time, frequency) played curve warped to ref timing


def _frequency_to_cents(f1: float, f2: float) -> float:
    """Absolute cents distance between two frequencies."""
    if f1 <= 0 or f2 <= 0:
        return 0.0
    return abs(1200.0 * np.log2(f1 / f2))


def _build_cost_matrix(
    played_freqs: np.ndarray,
    ref_freqs: np.ndarray,
    penalty: float,
) -> np.ndarray:
    """
    Build the DTW accumulated cost matrix.

    Cost between two frames = cents distance, capped at `penalty`.
    """
    n = len(played_freqs)
    m = len(ref_freqs)
    # Local cost: cents distance between each pair
    # Use vectorized log2 for speed
    with np.errstate(divide="ignore", invalid="ignore"):
        played_log = np.where(played_freqs > 0, np.log2(played_freqs), 0.0)
        ref_log = np.where(ref_freqs > 0, np.log2(ref_freqs), 0.0)

    # |1200 * (log2(p) - log2(r))| for all pairs
    local_cost = np.abs(1200.0 * (played_log[:, None] - ref_log[None, :]))
    local_cost = np.minimum(local_cost, penalty)

    # Accumulated cost matrix
    D = np.full((n + 1, m + 1), np.inf)
    D[0, 0] = 0.0

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = local_cost[i - 1, j - 1]
            D[i, j] = cost + min(D[i - 1, j], D[i, j - 1], D[i - 1, j - 1])

    return D


def _traceback(D: np.ndarray) -> list[tuple[int, int]]:
    """Trace back through the accumulated cost matrix to find the optimal path."""
    n, m = D.shape[0] - 1, D.shape[1] - 1
    path = [(n - 1, m - 1)]
    i, j = n, m

    while i > 1 or j > 1:
        candidates = []
        if i > 1 and j > 1:
            candidates.append((D[i - 1, j - 1], i - 1, j - 1))
        if i > 1:
            candidates.append((D[i - 1, j], i - 1, j))
        if j > 1:
            candidates.append((D[i, j - 1], i, j - 1))

        _, i, j = min(candidates, key=lambda x: x[0])
        path.append((i - 1, j - 1))

    path.reverse()
    return path


def dtw_align(
    played: list[tuple[float, float]],
    reference: list[tuple[float, float]],
    penalty: float = 200.0,
) -> DTWResult:
    """
    Align a played pitch curve to a reference pitch curve using DTW.

    Args:
        played: list of (time_seconds, frequency_hz) — the student's performance.
        reference: list of (time_seconds, frequency_hz) — the expected pitch curve.
        penalty: max cents penalty per frame pair (caps cost for very large jumps).

    Returns:
        DTWResult with alignment path, pitch error, timing deviation, and warped curve.

    Both curves are pre-filtered to remove zero-frequency (silence) frames.
    """
    # Filter out zero-frequency frames
    played_clean = [(t, f) for t, f in played if f > 0]
    ref_clean = [(t, f) for t, f in reference if f > 0]

    # Edge cases
    if not played_clean or not ref_clean:
        return DTWResult(
            alignment_path=[],
            pitch_error_mean=0.0,
            timing_deviation=0.0,
            warped_curve=[],
        )

    played_times = np.array([t for t, _ in played_clean])
    played_freqs = np.array([f for _, f in played_clean])
    ref_times = np.array([t for t, _ in ref_clean])
    ref_freqs = np.array([f for _, f in ref_clean])

    # Build cost matrix and trace back
    D = _build_cost_matrix(played_freqs, ref_freqs, penalty)
    path = _traceback(D)

    # Compute pitch error (mean absolute cents along path)
    cents_errors = []
    timing_devs = []
    warped: list[tuple[float, float]] = []

    for pi, ri in path:
        cents = _frequency_to_cents(played_freqs[pi], ref_freqs[ri])
        cents_errors.append(cents)
        timing_devs.append(abs(played_times[pi] - ref_times[ri]))
        # Warped curve: played frequency at reference timing
        warped.append((ref_times[ri], played_freqs[pi]))

    pitch_error_mean = float(np.mean(cents_errors)) if cents_errors else 0.0
    timing_deviation = float(np.mean(timing_devs)) if timing_devs else 0.0

    return DTWResult(
        alignment_path=path,
        pitch_error_mean=round(pitch_error_mean, 2),
        timing_deviation=round(timing_deviation, 4),
        warped_curve=warped,
    )
