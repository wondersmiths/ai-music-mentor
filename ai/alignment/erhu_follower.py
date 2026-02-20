"""
Erhu-specific score follower — aligns live Erhu performance to a written
music score using pitch-pass-through matching.

Design rationale
----------------
The generic ScoreFollower (follower.py) matches discrete pitch events
against score notes. This fails for Erhu because:

1. **Continuous pitch**: Erhu slides between notes, so the pitch at
   an onset may not be the target note — the pitch *passes through*
   the target during a glide.

2. **Legato transitions**: In legato passages the Erhu connects notes
   without distinct onsets. The aligner must detect note transitions
   by monitoring the pitch curve, not just reacting to onsets.

3. **Expressive timing (rubato)**: Erhu players take significant
   rhythmic liberty. Timing tolerance must be wide (±150 ms), and
   the aligner tracks cumulative tempo drift so late/early passages
   don't cascade into misalignment.

Algorithm: forward-tracking cursor with three matching axes:

    pitch pass-through (0.45)  — did the pitch curve visit the target?
    timing proximity   (0.25)  — how close is onset to expected time?
    phrase continuity  (0.30)  — does this advance the phrase sequentially?

Between onsets, a passive-advance mechanism watches the pitch curve
and advances the cursor when pitch dwells at the next expected note
for ≥80 ms, handling legato transitions that produce no onset.
"""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from typing import Optional

from ai.omr.models import ScoreResult

# ── Constants ────────────────────────────────────────────────

PITCH_TOLERANCE_ST = 1.0     # ±1 semitone = "in range"
TIMING_TOLERANCE_S = 0.150   # ±150 ms
LOOKAHEAD = 3                # candidates ahead of cursor
LOOKBEHIND = 1               # candidates behind cursor
ADVANCE_THRESHOLD = 0.40     # minimum fused score to move cursor
PASSIVE_DWELL_S = 0.080      # 80 ms dwell for passive advance

# Axis weights (sum to 1.0)
W_PITCH = 0.45
W_TIMING = 0.25
W_CONTINUITY = 0.30

# ── Pitch helpers ────────────────────────────────────────────

_PITCH_RE = re.compile(r"^([A-Ga-g]#?)(-?\d)$")
_NAME_TO_SEMITONE = {
    "C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5,
    "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11,
}

_DURATION_BEATS = {
    "whole": 4.0, "half": 2.0, "quarter": 1.0,
    "eighth": 0.5, "sixteenth": 0.25,
}


def _pitch_to_midi(pitch: str) -> float:
    """Convert a note name like 'C4' or 'F#3' to a MIDI number."""
    m = _PITCH_RE.match(pitch)
    if not m:
        return -1.0
    name, octave = m.group(1).upper(), int(m.group(2))
    semitone = _NAME_TO_SEMITONE.get(name, -1)
    if semitone < 0:
        return -1.0
    return float((octave + 1) * 12 + semitone)


# ── Data structures ──────────────────────────────────────────

@dataclass
class ScoreNote:
    """One note in the linearized score."""

    index: int               # position in the flat list
    measure: int             # 1-based measure number
    index_in_measure: int    # note position within measure
    midi: float              # target pitch as MIDI number
    pitch: str               # original pitch name (e.g. "D4")
    expected_time: float     # seconds from start, at reference tempo
    duration_s: float        # expected duration in seconds
    beat: float              # beat position within the measure


@dataclass
class AlignmentState:
    """Snapshot of the aligner's current position and confidence."""

    current_measure: int     # 1-based
    current_note_index: int  # global index in linearized score
    confidence: float        # 0.0–1.0


# ── Score linearizer ─────────────────────────────────────────

def _linearize_score(score: ScoreResult, bpm: float) -> list[ScoreNote]:
    """
    Flatten a ScoreResult into a list of ScoreNotes with absolute
    expected times computed from the given BPM.
    """
    spb = 60.0 / bpm  # seconds per beat
    notes: list[ScoreNote] = []
    idx = 0
    beat_offset = 0.0  # cumulative beats before current measure

    for measure in score.measures:
        num_beats = float(measure.time_signature.split("/")[0])
        for note_i, note in enumerate(measure.notes):
            midi = _pitch_to_midi(note.pitch)
            dur_beats = _DURATION_BEATS.get(note.duration, 1.0)
            abs_beat = beat_offset + note.beat - 1.0  # 0-based
            notes.append(ScoreNote(
                index=idx,
                measure=measure.number,
                index_in_measure=note_i,
                midi=midi,
                pitch=note.pitch,
                expected_time=abs_beat * spb,
                duration_s=dur_beats * spb,
                beat=note.beat,
            ))
            idx += 1
        beat_offset += num_beats

    return notes


# ── Aligner ──────────────────────────────────────────────────

class ErhuScoreAligner:
    """
    Streaming score aligner optimized for Erhu performance.

    Consumes two streams: a continuous pitch curve (every frame) and
    discrete onsets (from ErhuOnsetDetector). Maintains a cursor into
    the linearized score and outputs the current alignment state.

    Parameters
    ----------
    score     : ScoreResult from the OMR pipeline
    bpm       : reference tempo in BPM (used for expected note times)
    """

    def __init__(self, score: ScoreResult, bpm: float = 120.0):
        self._notes = _linearize_score(score, bpm)
        self._bpm = bpm
        self._cursor = 0
        self._confidence = 0.0

        # Tempo drift: EMA of (actual_time - expected_time)
        self._tempo_drift = 0.0

        # Pitch curve ring buffer: (time, midi_value) pairs
        self._pitch_buffer: deque[tuple[float, float]] = deque(maxlen=64)

        # Time of last matched note (for pitch buffer scan window)
        self._last_match_time = 0.0

        # Passive advance tracking: (dwell_start_time, note_index)
        self._dwell_start: Optional[float] = None
        self._dwell_target: int = -1

    # ── Public API ───────────────────────────────────────────

    def on_frame(self, time: float, pitch_midi: float, confidence: float):
        """
        Called every audio frame to feed the pitch curve buffer
        and check for passive (legato) note transitions.

        Parameters
        ----------
        time         : timestamp in seconds
        pitch_midi   : current pitch as fractional MIDI number (0 if silent)
        confidence   : pitch tracker confidence, 0.0–1.0
        """
        if pitch_midi > 0 and confidence > 0.3:
            self._pitch_buffer.append((time, pitch_midi))

        self._check_passive_advance(time, pitch_midi, confidence)

    def on_onset(self, time: float, onset_confidence: float) -> AlignmentState:
        """
        Called when ErhuOnsetDetector fires an onset.
        Core alignment step: matches the onset against score candidates
        and potentially advances the cursor.

        Parameters
        ----------
        time              : onset timestamp in seconds
        onset_confidence  : onset detector confidence, 0.0–1.0

        Returns
        -------
        AlignmentState with current measure, note index, and confidence.
        """
        if not self._notes or self._cursor >= len(self._notes):
            return self._current_state()

        # ── 1. Build candidate window around cursor ──────────
        lo = max(0, self._cursor - LOOKBEHIND)
        hi = min(len(self._notes), self._cursor + LOOKAHEAD + 1)

        candidates = []
        for i in range(lo, hi):
            score = self._score_candidate(i, time)
            candidates.append((i, score))

        # ── 2. Pick best candidate ───────────────────────────
        best_idx, best_score = max(candidates, key=lambda c: c[1])

        # ── 3. Advance cursor if score exceeds threshold ─────
        if best_score >= ADVANCE_THRESHOLD:
            self._cursor = best_idx + 1  # advance past matched note
            self._confidence = best_score

            # Update tempo drift (EMA: 70% old + 30% new)
            expected = self._notes[best_idx].expected_time
            new_drift = time - expected
            self._tempo_drift = 0.7 * self._tempo_drift + 0.3 * new_drift
            self._last_match_time = time

            # Reset passive dwell tracking
            self._dwell_start = None
            self._dwell_target = -1
        else:
            # No good match — decay confidence
            self._confidence *= 0.85

        return self._current_state()

    def state(self) -> AlignmentState:
        """Return the current alignment state."""
        return self._current_state()

    def reset(self):
        """Reset alignment to the beginning of the score."""
        self._cursor = 0
        self._confidence = 0.0
        self._tempo_drift = 0.0
        self._pitch_buffer.clear()
        self._last_match_time = 0.0
        self._dwell_start = None
        self._dwell_target = -1

    # ── Candidate scoring ────────────────────────────────────

    def _score_candidate(self, note_idx: int, onset_time: float) -> float:
        """
        Compute fused match score for a candidate note on three axes:
        pitch pass-through, timing proximity, phrase continuity.
        """
        note = self._notes[note_idx]

        # ── Axis 1: Pitch pass-through ───────────────────────
        # Scan pitch buffer for frames within ±1 semitone of target.
        # Measures what fraction of recent frames match, giving credit
        # for slides that pass through the target note.
        matches = 0
        total = 0
        for t, midi in self._pitch_buffer:
            if t < self._last_match_time:
                continue  # only frames since last matched note
            total += 1
            if abs(midi - note.midi) <= PITCH_TOLERANCE_ST:
                matches += 1

        if total == 0:
            pitch_score = 0.0
        else:
            hit_ratio = matches / total
            # 50%+ in range → full score; partial credit below
            pitch_score = min(1.0, hit_ratio * 2.0)

        # ── Axis 2: Timing proximity ─────────────────────────
        # Compare onset time to expected time (adjusted for drift).
        # Linear decay from 1.0 at exact match to 0.0 at ±150 ms.
        adjusted_expected = note.expected_time + self._tempo_drift
        time_error = abs(onset_time - adjusted_expected)
        timing_score = max(0.0, 1.0 - time_error / TIMING_TOLERANCE_S)

        # ── Axis 3: Phrase continuity ────────────────────────
        # Reward sequential advancement. The cursor points to the
        # *next expected* note, so step=0 means "this is the next note".
        step = note_idx - self._cursor

        if step == 0:
            continuity_score = 1.0    # ideal: the next expected note
        elif step == -1:
            continuity_score = 0.5    # re-match previous note
        elif step == 1:
            continuity_score = 0.4    # skipped one note
        elif step == -2:
            continuity_score = 0.2    # went back two (correction)
        else:
            continuity_score = 0.0    # large jump — unlikely

        return (W_PITCH * pitch_score
                + W_TIMING * timing_score
                + W_CONTINUITY * continuity_score)

    # ── Passive advance (legato detection) ───────────────────

    def _check_passive_advance(
        self, time: float, pitch_midi: float, confidence: float,
    ):
        """
        Detect notes matched by slide-through without a distinct onset.

        If pitch dwells within ±1 semitone of the next expected note
        for ≥80 ms, passively advance the cursor. This handles legato
        passages where the Erhu glides smoothly between notes without
        producing an onset event.
        """
        if self._cursor >= len(self._notes):
            return

        if pitch_midi <= 0 or confidence <= 0.3:
            # No valid pitch — reset dwell tracking
            self._dwell_start = None
            self._dwell_target = -1
            return

        next_note = self._notes[self._cursor]

        if abs(pitch_midi - next_note.midi) <= PITCH_TOLERANCE_ST:
            # Pitch is in range of next expected note
            if self._dwell_target != self._cursor or self._dwell_start is None:
                # Start tracking a new dwell
                self._dwell_start = time
                self._dwell_target = self._cursor
            elif time - self._dwell_start >= PASSIVE_DWELL_S:
                # Dwell threshold reached — verify timing is plausible
                adjusted_expected = next_note.expected_time + self._tempo_drift
                if abs(time - adjusted_expected) < TIMING_TOLERANCE_S * 2:
                    # Passive advance
                    self._cursor += 1
                    self._confidence = 0.6  # lower than onset-matched
                    self._tempo_drift = (
                        0.7 * self._tempo_drift
                        + 0.3 * (time - adjusted_expected)
                    )
                    self._last_match_time = time
                    self._dwell_start = None
                    self._dwell_target = -1
        else:
            # Pitch left the target range — reset dwell
            if self._dwell_target == self._cursor:
                self._dwell_start = None
                self._dwell_target = -1

    # ── Helpers ──────────────────────────────────────────────

    def _current_state(self) -> AlignmentState:
        """Build an AlignmentState from current cursor position."""
        if not self._notes:
            return AlignmentState(
                current_measure=0,
                current_note_index=0,
                confidence=0.0,
            )

        # Cursor points past the last matched note; the "current" note
        # is the one we just matched (cursor - 1), clamped to valid range.
        idx = min(max(self._cursor - 1, 0), len(self._notes) - 1)
        note = self._notes[idx]

        return AlignmentState(
            current_measure=note.measure,
            current_note_index=idx,
            confidence=round(self._confidence, 3),
        )
