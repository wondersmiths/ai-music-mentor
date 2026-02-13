"""
Streaming onset detection and tempo estimation for practice feedback.

Uses energy-rise onset detection: computes the frame-to-frame increase
in RMS energy, then picks peaks in the energy-rise signal that exceed
an adaptive threshold. Simple, robust, and well-suited for monophonic
instrumental audio.

Designed for real-time use: feed frames sequentially via OnsetDetector.feed().
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class Onset:
    """A single detected note onset."""

    time: float  # timestamp in seconds from start of stream
    strength: float  # onset strength (energy rise)


@dataclass
class TempoEstimate:
    """Tempo estimated from recent onsets."""

    bpm: float  # beats per minute, 0.0 if insufficient data
    confidence: float  # 0.0–1.0 based on IOI consistency


@dataclass
class OnsetResult:
    """Full result returned by OnsetDetector after processing all frames."""

    onsets: list[Onset]
    tempo: TempoEstimate


class OnsetDetector:
    """
    Streaming energy-rise onset detector with tempo estimation.

    Detects note attacks by tracking the frame-to-frame increase
    in RMS energy. An onset is detected when:

    1. Energy rise exceeds an adaptive threshold (based on running
       peak energy, so it adapts to the player's volume).
    2. The rise is a local peak (previous rise was smaller) — this
       prevents double-triggers on gradual attacks.
    3. Enough time has passed since the last onset (cooldown).

    Parameters
    ----------
    sample_rate   : audio sample rate in Hz
    frame_size    : samples per frame (must match what you feed)
    hop_size      : samples between frame starts. Defaults to frame_size.
    sensitivity   : onset sensitivity, 0.0–1.0. Higher = more sensitive.
                    0.5 is a good default for practice feedback.
    cooldown_ms   : minimum time between consecutive onsets (ms)
    bpm_min       : lowest BPM to consider for tempo estimation
    bpm_max       : highest BPM to consider for tempo estimation

    Usage
    -----
        det = OnsetDetector(sample_rate=16000, frame_size=2048)
        for frame in audio_frames:
            det.feed(frame)
        result = det.result()
        print(result.onsets, result.tempo.bpm)
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_size: int = 2048,
        hop_size: Optional[int] = None,
        sensitivity: float = 0.5,
        cooldown_ms: float = 100.0,
        bpm_min: float = 30.0,
        bpm_max: float = 240.0,
    ):
        self.sample_rate = sample_rate
        self.frame_size = frame_size
        self.hop_size = hop_size or frame_size
        self.cooldown_s = cooldown_ms / 1000.0
        self.bpm_min = bpm_min
        self.bpm_max = bpm_max

        # Sensitivity maps to the threshold multiplier.
        # sensitivity=0 → multiplier=0.3 (very strict)
        # sensitivity=1 → multiplier=0.02 (very sensitive)
        self._threshold_mult = 0.3 * (1.0 - sensitivity) + 0.02 * sensitivity

        # Internal state
        self._prev_rms = 0.0
        self._prev_rise = 0.0
        self._peak_rms = 1e-6  # running peak RMS, for adaptive threshold
        self._rms_decay = 0.995  # slow decay of peak tracker
        self._frame_index = 0
        self._onsets: list[Onset] = []
        self._last_onset_time = -1.0

    def feed(self, frame: np.ndarray) -> Optional[Onset]:
        """
        Process one audio frame. Returns an Onset if one is detected,
        otherwise None.
        """
        timestamp = self._frame_index * self.hop_size / self.sample_rate
        self._frame_index += 1

        # RMS energy of this frame
        rms = float(np.sqrt(np.mean(frame.astype(np.float64) ** 2)))

        # Update peak RMS tracker (slow decay so it adapts to volume)
        self._peak_rms = max(rms, self._peak_rms * self._rms_decay)

        # Energy rise: how much louder is this frame vs. the previous?
        # Only positive rises matter (half-wave rectification).
        rise = max(rms - self._prev_rms, 0.0)

        # Adaptive threshold: proportional to the recent peak level.
        # This makes onset detection work at any volume.
        threshold = self._peak_rms * self._threshold_mult

        # Onset = energy rise exceeds threshold AND is a local peak
        # (rise > prev_rise means we're at or past the steepest point
        # of the attack transient).
        onset = None
        is_peak = rise > self._prev_rise
        above_threshold = rise > threshold
        cooldown_ok = (timestamp - self._last_onset_time) >= self.cooldown_s

        if is_peak and above_threshold and cooldown_ok:
            onset = Onset(time=round(timestamp, 4), strength=round(rise, 6))
            self._onsets.append(onset)
            self._last_onset_time = timestamp

        self._prev_rms = rms
        self._prev_rise = rise
        return onset

    def result(self) -> OnsetResult:
        """Return all detected onsets and the estimated tempo."""
        return OnsetResult(
            onsets=list(self._onsets),
            tempo=self.estimate_tempo(),
        )

    def estimate_tempo(self, max_onsets: int = 64) -> TempoEstimate:
        """
        Estimate BPM from the median inter-onset interval (IOI)
        of recent onsets. Uses median instead of mean for robustness
        against syncopation and missed onsets.
        """
        onsets = self._onsets[-max_onsets:]
        if len(onsets) < 3:
            return TempoEstimate(bpm=0.0, confidence=0.0)

        times = [o.time for o in onsets]
        iois = np.diff(times)

        # Filter to plausible beat range
        min_ioi = 60.0 / self.bpm_max
        max_ioi = 60.0 / self.bpm_min
        valid = iois[(iois >= min_ioi) & (iois <= max_ioi)]

        if len(valid) < 2:
            return TempoEstimate(bpm=0.0, confidence=0.0)

        median_ioi = float(np.median(valid))
        bpm = 60.0 / median_ioi

        # Confidence: IOI consistency * data quantity
        std_ioi = float(np.std(valid))
        consistency = 1.0 - min(std_ioi / (median_ioi + 1e-9), 1.0)
        count_factor = min(len(valid) / 8.0, 1.0)
        confidence = round(consistency * count_factor, 3)

        return TempoEstimate(bpm=round(bpm, 1), confidence=confidence)

    def reset(self):
        """Clear all state for a new recording session."""
        self._prev_rms = 0.0
        self._prev_rise = 0.0
        self._peak_rms = 1e-6
        self._frame_index = 0
        self._onsets.clear()
        self._last_onset_time = -1.0
