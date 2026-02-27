"""
B3: Slide quality analyzer.

Detects slide (portamento/glissando) segments in a pitch curve, measures
their smoothness, detects overshoot, and identifies step artifacts.
Returns a slide_score (0–100) and per-segment detail.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np


@dataclass
class SlideSegment:
    """A detected slide between two pitch targets."""
    start_time: float
    end_time: float
    start_freq: float      # Hz at slide onset
    end_freq: float        # Hz at slide end
    interval_cents: float  # total interval in cents
    smoothness: float      # 0–1 (1 = perfectly smooth)
    overshoot_cents: float # max overshoot beyond target in cents
    has_step_artifact: bool


@dataclass
class SlideResult:
    """Result of slide quality analysis."""
    slide_score: float                      # 0–100
    segments: List[SlideSegment] = field(default_factory=list)
    slide_count: int = 0


# ── Slide detection thresholds ──────────────────────────────

# Minimum pitch change (cents) over a window to be considered a slide
MIN_SLIDE_CENTS = 30
# Minimum slide duration in seconds
MIN_SLIDE_DURATION = 0.05
# Maximum slide duration in seconds (longer = likely a new note)
MAX_SLIDE_DURATION = 1.0
# Window size for pitch change detection (frames)
CHANGE_WINDOW = 3
# Step artifact: if a single frame-to-frame jump exceeds this fraction
# of the total slide interval, it's a step
STEP_THRESHOLD_RATIO = 0.4


def _freq_to_cents(f1: float, f2: float) -> float:
    """Signed cents from f1 to f2."""
    if f1 <= 0 or f2 <= 0:
        return 0.0
    return 1200.0 * np.log2(f2 / f1)


def _detect_slides(
    times: np.ndarray,
    freqs: np.ndarray,
) -> List[Tuple[int, int]]:
    """
    Find (start_idx, end_idx) pairs for slide segments.

    A slide is a contiguous region where pitch is changing rapidly
    (> MIN_SLIDE_CENTS over CHANGE_WINDOW frames).
    """
    n = len(freqs)
    if n < CHANGE_WINDOW + 1:
        return []

    # Compute frame-to-frame cents changes
    with np.errstate(divide="ignore", invalid="ignore"):
        cents = np.where(
            (freqs[:-1] > 0) & (freqs[1:] > 0),
            1200.0 * np.log2(freqs[1:] / freqs[:-1]),
            0.0,
        )

    # Sliding window: sum of absolute cents change over CHANGE_WINDOW frames
    kernel = np.ones(CHANGE_WINDOW)
    if len(cents) < CHANGE_WINDOW:
        return []
    windowed = np.convolve(np.abs(cents), kernel, mode="valid")

    # Threshold: mark frames that are part of a rapid pitch change
    sliding_mask = windowed > MIN_SLIDE_CENTS

    # Find contiguous runs
    segments = []
    pad = np.concatenate(([False], sliding_mask, [False]))
    changes = np.diff(pad.astype(int))
    starts = np.where(changes == 1)[0]
    ends = np.where(changes == -1)[0]

    for s, e in zip(starts, ends):
        # Expand to include the change window
        s_idx = max(0, s)
        e_idx = min(n - 1, e + CHANGE_WINDOW)

        duration = times[e_idx] - times[s_idx]
        if duration < MIN_SLIDE_DURATION or duration > MAX_SLIDE_DURATION:
            continue

        total_cents = abs(_freq_to_cents(freqs[s_idx], freqs[e_idx]))
        if total_cents >= MIN_SLIDE_CENTS:
            segments.append((s_idx, e_idx))

    return segments


def _analyze_segment(
    times: np.ndarray,
    freqs: np.ndarray,
    s: int,
    e: int,
) -> SlideSegment:
    """Analyze a single slide segment for quality metrics."""
    seg_times = times[s:e + 1]
    seg_freqs = freqs[s:e + 1]

    start_freq = float(seg_freqs[0])
    end_freq = float(seg_freqs[-1])
    interval_cents = _freq_to_cents(start_freq, end_freq)

    # Smoothness: measure deviation from a straight line in cents space
    # Perfect slide = linear interpolation from start to end cents
    n_pts = len(seg_freqs)
    if n_pts < 2:
        return SlideSegment(
            start_time=float(seg_times[0]),
            end_time=float(seg_times[-1]),
            start_freq=start_freq,
            end_freq=end_freq,
            interval_cents=round(interval_cents, 2),
            smoothness=1.0,
            overshoot_cents=0.0,
            has_step_artifact=False,
        )

    # Cents deviation from start for each frame
    actual_cents = np.array([_freq_to_cents(start_freq, f) for f in seg_freqs])
    # Expected linear interpolation
    expected_cents = np.linspace(0, interval_cents, n_pts)
    # RMS deviation from linear
    deviation = np.sqrt(np.mean((actual_cents - expected_cents) ** 2))
    # Smoothness: 1.0 when deviation is 0, drops toward 0 at 50+ cents RMS
    smoothness = max(0.0, 1.0 - deviation / 50.0)

    # Overshoot: did the pitch go beyond the target?
    if interval_cents > 0:
        overshoot = max(0, float(np.max(actual_cents)) - interval_cents)
    elif interval_cents < 0:
        overshoot = max(0, abs(interval_cents) - abs(float(np.min(actual_cents))))
    else:
        overshoot = 0.0

    # Step artifact: any single frame jump > STEP_THRESHOLD_RATIO of total interval
    frame_cents = np.abs(np.diff(actual_cents))
    total_interval = abs(interval_cents) if interval_cents != 0 else 1.0
    has_step = bool(np.any(frame_cents > STEP_THRESHOLD_RATIO * total_interval))

    return SlideSegment(
        start_time=round(float(seg_times[0]), 4),
        end_time=round(float(seg_times[-1]), 4),
        start_freq=round(start_freq, 2),
        end_freq=round(end_freq, 2),
        interval_cents=round(interval_cents, 2),
        smoothness=round(smoothness, 3),
        overshoot_cents=round(overshoot, 2),
        has_step_artifact=has_step,
    )


def analyze_slides(
    frames: List[Tuple[float, float, float]],
) -> SlideResult:
    """
    Analyze slide quality in a pitch curve.

    Args:
        frames: list of (time, frequency, confidence) tuples.

    Returns:
        SlideResult with overall score and per-segment details.
    """
    # Filter: keep only frames with positive frequency
    valid = [(t, f) for t, f, c in frames if f > 0]

    if len(valid) < CHANGE_WINDOW + 1:
        return SlideResult(slide_score=100.0, segments=[], slide_count=0)

    times = np.array([t for t, _ in valid])
    freqs = np.array([f for _, f in valid])

    # Detect slide segments
    raw_segments = _detect_slides(times, freqs)

    if not raw_segments:
        # No slides detected — score 100 (nothing to penalize)
        return SlideResult(slide_score=100.0, segments=[], slide_count=0)

    # Analyze each segment
    segments = [_analyze_segment(times, freqs, s, e) for s, e in raw_segments]

    # Aggregate score: weighted average of smoothness, overshoot penalty, step penalty
    scores = []
    for seg in segments:
        seg_score = seg.smoothness * 100.0
        # Penalize overshoot: -1 point per cent of overshoot
        seg_score -= min(30.0, seg.overshoot_cents * 1.0)
        # Penalize step artifacts: -15 points
        if seg.has_step_artifact:
            seg_score -= 15.0
        scores.append(max(0.0, seg_score))

    slide_score = float(np.mean(scores)) if scores else 100.0

    return SlideResult(
        slide_score=round(slide_score, 2),
        segments=segments,
        slide_count=len(segments),
    )
