"""
Erhu-specific onset detection using pitch-settle detection.

Design rationale
----------------
The standard energy-rise onset detector (onset.py) fails on Erhu because
bowed onsets are gradual — there's no sharp energy spike at note starts.
Instead, we detect **musical onsets** (new pitches) by fusing three cues:

1. **Pitch-change** (weight 0.55) — Primary signal. A "new note" is defined
   as the moment pitch *settles* at a new value after a glide, not the moment
   pitch starts moving. This gives a clear, unambiguous onset for each note.

2. **Spectral flux** (weight 0.25) — Catches bow articulations (détaché,
   spiccato) and timbral changes that don't produce pitch changes.

3. **Energy change** (weight 0.20) — Catches re-attacks and loud entries
   from silence. Supporting cue only.

Core algorithm: a three-state machine (STABLE / GLIDING / SILENT) tracks
pitch movement and emits an onset when pitch settles at a new value. An
ambiguity window (±80 ms) refines the exact onset timestamp, and confidence
gating suppresses false onsets during bow noise.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

import numpy as np

from ai.pitch.erhu import ErhuPitchTracker
from ai.pitch.notes import freq_to_midi
from ai.pitch.onset import TempoEstimate


# ── Data structures ──────────────────────────────────────────

@dataclass
class ErhuOnset:
    """A single detected Erhu note onset."""

    time: float        # seconds from stream start
    confidence: float  # 0.0–1.0 (fused cue strength)


@dataclass
class ErhuOnsetResult:
    """Full result returned by ErhuOnsetDetector after processing."""

    onsets: list[ErhuOnset]
    tempo: TempoEstimate


# ── Pitch state machine ─────────────────────────────────────

class _PitchState(Enum):
    SILENT = auto()
    STABLE = auto()
    GLIDING = auto()


# ── Detector ─────────────────────────────────────────────────

class ErhuOnsetDetector:
    """
    Streaming onset detector optimized for Erhu (二胡).

    Detects musical onsets by tracking when pitch settles at a new
    value, supplemented by spectral flux and energy change cues.

    Parameters
    ----------
    sample_rate      : audio sample rate in Hz
    frame_size       : samples per frame (must match what you feed)
    hop_size         : samples between frames. Defaults to frame_size.
    cooldown_ms      : minimum ms between consecutive onsets (150 ms)
    settle_threshold : semitones/frame below which pitch is "settled"
    glide_threshold  : semitones/frame above which pitch is "gliding"
    note_change_min  : minimum semitone change to register a new note
    flux_multiplier  : spectral flux threshold = median * this
    energy_sensitivity : energy rise threshold = peak_rms * this
    ambiguity_ms     : ± window in ms for onset timestamp refinement

    Usage
    -----
        det = ErhuOnsetDetector(sample_rate=16000, frame_size=2048)
        for frame in audio_frames:
            onset = det.feed(frame)
            if onset:
                print(onset.time, onset.confidence)
        result = det.result()
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_size: int = 2048,
        hop_size: Optional[int] = None,
        cooldown_ms: float = 150.0,
        settle_threshold: float = 0.3,
        glide_threshold: float = 0.5,
        note_change_min: float = 0.8,
        flux_multiplier: float = 3.0,
        energy_sensitivity: float = 0.15,
        ambiguity_ms: float = 80.0,
    ):
        self.sample_rate = sample_rate
        self.frame_size = frame_size
        self.hop_size = hop_size or frame_size
        self.cooldown_s = cooldown_ms / 1000.0
        self.settle_threshold = settle_threshold
        self.glide_threshold = glide_threshold
        self.note_change_min = note_change_min
        self.flux_multiplier = flux_multiplier
        self.energy_sensitivity = energy_sensitivity

        # Ambiguity window in frames (±)
        frame_duration = self.hop_size / self.sample_rate
        self._ambiguity_frames = max(1, int(ambiguity_ms / 1000.0 / frame_duration))

        # Lookback for onset placement (2 frames before settle point)
        self._lookback_frames = 2

        # Internal pitch tracker (composition)
        self._pitch_tracker = ErhuPitchTracker(
            sample_rate, frame_size, hop_size or frame_size,
        )

        # ── Pitch state machine ──
        self._pitch_state = _PitchState.SILENT
        self._stable_midi = 0.0       # MIDI note value when last stable
        self._prev_midi = 0.0         # previous frame's MIDI value

        # ── Spectral flux state ──
        self._prev_spectrum: Optional[np.ndarray] = None
        self._flux_history: deque[float] = deque(maxlen=32)

        # ── Energy state ──
        self._prev_rms = 0.0
        self._peak_rms = 1e-6
        self._rms_decay = 0.995

        # ── Score ring buffer for ambiguity window refinement ──
        buf_size = self._ambiguity_frames * 2 + 4
        self._score_buffer: deque[tuple[float, float, float]] = deque(
            maxlen=buf_size,
        )  # (timestamp, combined_score, pitch_confidence)

        # ── General state ──
        self._frame_index = 0
        self._onsets: list[ErhuOnset] = []
        self._last_onset_time = -1.0

    # ── Public API ───────────────────────────────────────────

    def feed(self, frame: np.ndarray) -> Optional[ErhuOnset]:
        """
        Process one audio frame. Returns an ErhuOnset if one is
        detected, otherwise None.
        """
        timestamp = self._frame_index * self.hop_size / self.sample_rate
        self._frame_index += 1

        # ── 1. Get pitch from ErhuPitchTracker ───────────────
        pitch_result = self._pitch_tracker.feed(frame)
        current_midi = freq_to_midi(pitch_result.pitch_hz)
        pitch_confidence = pitch_result.confidence

        # ── 2. Compute three cue scores ──────────────────────
        pitch_score = self._update_pitch_state(current_midi, pitch_confidence)
        flux_score = self._compute_spectral_flux(frame)
        energy_score = self._compute_energy_change(frame)

        # ── 3. Fuse cues ─────────────────────────────────────
        combined = 0.55 * pitch_score + 0.25 * flux_score + 0.20 * energy_score

        # Store in ring buffer for ambiguity refinement
        self._score_buffer.append((timestamp, combined, pitch_confidence))

        # ── 4. Onset decision ─────────────────────────────────
        cooldown_ok = (timestamp - self._last_onset_time) >= self.cooldown_s

        if combined >= 0.4 and cooldown_ok:
            # Confidence gating: suppress when pitch confidence is low
            # (unless energy alone is strong — re-entry from silence)
            if pitch_confidence < 0.3 and energy_score <= 0.8:
                return None

            # Refine timestamp within ambiguity window
            onset = self._refine_onset(timestamp, combined)
            self._onsets.append(onset)
            self._last_onset_time = onset.time
            return onset

        return None

    def result(self) -> ErhuOnsetResult:
        """Return all detected onsets and estimated tempo."""
        return ErhuOnsetResult(
            onsets=list(self._onsets),
            tempo=self.estimate_tempo(),
        )

    def estimate_tempo(self, max_onsets: int = 64) -> TempoEstimate:
        """
        Estimate BPM from recent onset intervals.
        Reuses the same median-IOI logic as the generic OnsetDetector.
        """
        onsets = self._onsets[-max_onsets:]
        if len(onsets) < 3:
            return TempoEstimate(bpm=0.0, confidence=0.0)

        times = [o.time for o in onsets]
        iois = np.diff(times)

        # Filter to plausible beat range (30–240 BPM)
        min_ioi = 60.0 / 240.0
        max_ioi = 60.0 / 30.0
        valid = iois[(iois >= min_ioi) & (iois <= max_ioi)]

        if len(valid) < 2:
            return TempoEstimate(bpm=0.0, confidence=0.0)

        median_ioi = float(np.median(valid))
        bpm = 60.0 / median_ioi

        std_ioi = float(np.std(valid))
        consistency = 1.0 - min(std_ioi / (median_ioi + 1e-9), 1.0)
        count_factor = min(len(valid) / 8.0, 1.0)
        confidence = round(consistency * count_factor, 3)

        return TempoEstimate(bpm=round(bpm, 1), confidence=confidence)

    def reset(self):
        """Clear all state for a new recording session."""
        self._pitch_tracker.reset()
        self._pitch_state = _PitchState.SILENT
        self._stable_midi = 0.0
        self._prev_midi = 0.0
        self._prev_spectrum = None
        self._flux_history.clear()
        self._prev_rms = 0.0
        self._peak_rms = 1e-6
        self._score_buffer.clear()
        self._frame_index = 0
        self._onsets.clear()
        self._last_onset_time = -1.0

    # ── Pitch state machine ──────────────────────────────────

    def _update_pitch_state(
        self, current_midi: float, confidence: float,
    ) -> float:
        """
        Update the SILENT/STABLE/GLIDING state machine.
        Returns pitch_score: 1.0 if a new note just settled, else 0.0.
        """
        pitch_score = 0.0

        if current_midi <= 0 or confidence <= 0:
            # No pitch detected
            if self._pitch_state != _PitchState.SILENT:
                self._pitch_state = _PitchState.SILENT
            self._prev_midi = 0.0
            return 0.0

        if self._pitch_state == _PitchState.SILENT:
            # First pitched frame after silence → onset
            self._pitch_state = _PitchState.STABLE
            self._stable_midi = current_midi
            self._prev_midi = current_midi
            return 1.0

        # Compute pitch change rate (semitones/frame)
        if self._prev_midi > 0:
            delta = abs(current_midi - self._prev_midi)
        else:
            delta = 0.0

        if self._pitch_state == _PitchState.STABLE:
            if delta > self.glide_threshold:
                # Pitch started moving → enter glide
                self._pitch_state = _PitchState.GLIDING
                # _stable_midi retains the pre-glide value

        elif self._pitch_state == _PitchState.GLIDING:
            if delta < self.settle_threshold:
                # Pitch has settled — check if it's a new note
                change_from_stable = abs(current_midi - self._stable_midi)
                if change_from_stable > self.note_change_min:
                    # New note! Emit onset.
                    pitch_score = 1.0
                    self._stable_midi = current_midi
                self._pitch_state = _PitchState.STABLE

        self._prev_midi = current_midi
        return pitch_score

    # ── Spectral flux ────────────────────────────────────────

    def _compute_spectral_flux(self, frame: np.ndarray) -> float:
        """
        Weighted spectral flux with high-frequency emphasis.
        De-emphasizes below 250 Hz (bow noise region).
        """
        x = frame.astype(np.float64)
        spectrum = np.abs(np.fft.rfft(x, n=self.frame_size))

        if self._prev_spectrum is None:
            self._prev_spectrum = spectrum
            return 0.0

        # Frequency axis
        freqs = np.fft.rfftfreq(self.frame_size, 1.0 / self.sample_rate)

        # Weight: ramp from 0 to 1 between 0 and 250 Hz, 1.0 above
        weight = np.minimum(1.0, freqs / 250.0)

        # Half-wave rectified spectral difference, weighted
        diff = np.maximum(spectrum - self._prev_spectrum, 0.0) ** 2
        weight_sum = np.sum(weight)
        if weight_sum > 0:
            flux = float(np.sum(weight * diff) / weight_sum)
        else:
            flux = 0.0

        self._prev_spectrum = spectrum
        self._flux_history.append(flux)

        # Adaptive threshold: median of recent flux * multiplier
        if len(self._flux_history) < 3:
            return 0.0

        median_flux = float(np.median(list(self._flux_history)))
        threshold = median_flux * self.flux_multiplier
        if threshold <= 0:
            return 0.0

        return min(1.0, flux / threshold)

    # ── Energy change ────────────────────────────────────────

    def _compute_energy_change(self, frame: np.ndarray) -> float:
        """
        RMS energy rise detection. Supporting cue for re-attacks
        and entries from silence.
        """
        rms = float(np.sqrt(np.mean(frame.astype(np.float64) ** 2)))

        # Update peak tracker (slow decay)
        self._peak_rms = max(rms, self._peak_rms * self._rms_decay)

        # Energy rise (half-wave rectified)
        rise = max(rms - self._prev_rms, 0.0)
        self._prev_rms = rms

        # Threshold relative to peak RMS
        threshold = self._peak_rms * self.energy_sensitivity
        if threshold <= 0:
            return 0.0

        return min(1.0, rise / threshold)

    # ── Ambiguity window refinement ──────────────────────────

    def _refine_onset(
        self, initial_time: float, initial_score: float,
    ) -> ErhuOnset:
        """
        Refine the onset timestamp by finding the frame with the
        highest combined score within ±ambiguity_frames of the
        initial detection. Applies lookback to compensate for
        pitch tracker smoothing delay.
        """
        buf = list(self._score_buffer)
        if not buf:
            return ErhuOnset(
                time=round(initial_time, 4),
                confidence=round(min(1.0, initial_score), 3),
            )

        # Find the best score in the buffer (which covers the
        # recent ambiguity window)
        best_time = initial_time
        best_score = initial_score
        for ts, score, _conf in buf:
            if abs(ts - initial_time) <= (
                self._ambiguity_frames * self.hop_size / self.sample_rate
            ):
                if score > best_score:
                    best_score = score
                    best_time = ts

        # Apply lookback adjustment
        lookback_s = self._lookback_frames * self.hop_size / self.sample_rate
        adjusted_time = max(0.0, best_time - lookback_s)

        return ErhuOnset(
            time=round(adjusted_time, 4),
            confidence=round(min(1.0, best_score), 3),
        )
