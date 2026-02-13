"""
Public interface for pitch detection.

Combines YIN pitch estimation with frequency-to-note conversion
to produce a single PitchResult per audio frame.
"""

from dataclasses import dataclass

import numpy as np

from ai.pitch.notes import freq_to_note
from ai.pitch.yin import yin_pitch


@dataclass
class PitchResult:
    """Result of pitch detection on a single audio frame."""

    frequency: float  # Hz, 0.0 if no pitch detected
    note: str  # e.g. "A4", "" if no pitch
    cents_off: int  # deviation from nearest note (-50 to +50)
    confidence: float  # 0.0 to 1.0


def detect_pitch(
    frame: np.ndarray,
    sample_rate: int = 16000,
    threshold: float = 0.15,
    freq_min: float = 50.0,
    freq_max: float = 2000.0,
) -> PitchResult:
    """
    Detect the pitch of a monophonic audio frame.

    Parameters
    ----------
    frame        : 1-D float array of audio samples
    sample_rate  : sample rate in Hz (must match the frame)
    threshold    : YIN confidence threshold (lower = stricter)
    freq_min     : lowest pitch to detect (Hz)
    freq_max     : highest pitch to detect (Hz)

    Returns
    -------
    PitchResult with frequency, note name, cents deviation, and confidence.
    """
    freq, confidence = yin_pitch(
        frame,
        sample_rate=sample_rate,
        threshold=threshold,
        freq_min=freq_min,
        freq_max=freq_max,
    )

    if freq > 0:
        note, cents = freq_to_note(freq)
    else:
        note, cents = "", 0

    return PitchResult(
        frequency=freq,
        note=note,
        cents_off=cents,
        confidence=confidence,
    )
