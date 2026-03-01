"""
Onset detection from pitch frames.

Detects note transitions by identifying frequency jumps greater than
a threshold (in cents) with a cooldown period to avoid double-triggers.
Returns a list of onset timestamps.
"""

from __future__ import annotations

import math
from typing import List, Tuple

# Minimum frequency jump in cents to count as a new onset
ONSET_THRESHOLD_CENTS = 50.0
# Minimum time between consecutive onsets (seconds)
COOLDOWN_S = 0.08


def _cents_between(f1: float, f2: float) -> float:
    """Absolute cents distance between two frequencies."""
    if f1 <= 0 or f2 <= 0:
        return 0.0
    return abs(1200.0 * math.log2(f2 / f1))


def detect_onsets_from_pitch(
    frames: List[Tuple[float, float, float]],
    threshold_cents: float = ONSET_THRESHOLD_CENTS,
    cooldown_s: float = COOLDOWN_S,
) -> List[float]:
    """
    Detect note onsets from pitch frames by finding frequency jumps.

    Args:
        frames: list of (time, frequency, confidence) tuples.
        threshold_cents: minimum cents jump to trigger an onset.
        cooldown_s: minimum time between consecutive onsets.

    Returns:
        Sorted list of onset timestamps in seconds.
    """
    # Filter to voiced frames (positive frequency)
    voiced = [(t, f) for t, f, c in frames if f > 0 and c > 0]

    if len(voiced) < 2:
        return [voiced[0][0]] if voiced else []

    onsets: List[float] = [voiced[0][0]]  # First voiced frame is always an onset

    last_onset_time = voiced[0][0]

    for i in range(1, len(voiced)):
        t, f = voiced[i]
        _, prev_f = voiced[i - 1]

        cents = _cents_between(prev_f, f)

        if cents >= threshold_cents and (t - last_onset_time) >= cooldown_s:
            onsets.append(t)
            last_onset_time = t

    return onsets
