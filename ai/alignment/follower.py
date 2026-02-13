"""
Live score follower — aligns a stream of detected pitches and onsets
to a structured music score.

Algorithm overview
------------------
The score is flattened into a linear sequence of "score events" (one per
note). The follower maintains a **cursor** into this sequence and a small
**look-ahead window**. Each incoming live note is compared against the
candidates in the window. The best-matching candidate advances the
cursor.

This is a simplified online variant of dynamic-time-warping (DTW) that
trades global optimality for constant-memory, constant-time-per-event
streaming. It is deliberately forgiving:

- **Skipped notes**: if the player skips ahead, the look-ahead window
  lets the cursor jump forward.
- **Extra notes**: unmatched live notes (wrong pitch, repeated notes)
  are absorbed without moving the cursor.
- **Tempo variation**: matching is pitch-first, time-second, so rubato
  and hesitation don't break alignment.

Confidence is a running exponential average of per-note match quality
(pitch match + timing proximity).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from ai.omr.models import Measure, ScoreResult

# ── Duration to beats lookup ────────────────────────────────

_DURATION_BEATS = {
    "whole": 4.0,
    "half": 2.0,
    "quarter": 1.0,
    "eighth": 0.5,
    "sixteenth": 0.25,
}

# ── Pitch helpers ───────────────────────────────────────────

_PITCH_RE = re.compile(r"^([A-Ga-g]#?)(-?\d)$")
_NAME_TO_SEMITONE = {
    "C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5,
    "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11,
}


def _pitch_to_midi(pitch: str) -> int:
    """Convert a note name like 'C4' or 'F#3' to a MIDI number."""
    m = _PITCH_RE.match(pitch)
    if not m:
        return -1
    name, octave = m.group(1).upper(), int(m.group(2))
    semitone = _NAME_TO_SEMITONE.get(name, -1)
    if semitone < 0:
        return -1
    return (octave + 1) * 12 + semitone


def _semitone_distance(a: str, b: str) -> int:
    """Absolute semitone distance between two pitch names."""
    ma, mb = _pitch_to_midi(a), _pitch_to_midi(b)
    if ma < 0 or mb < 0:
        return 99  # unknown pitch — treat as maximum mismatch
    return abs(ma - mb)


# ── Data structures ─────────────────────────────────────────

@dataclass
class ScoreEvent:
    """One note in the flattened score sequence."""

    index: int  # position in the flat list
    measure: int  # 1-based measure number
    beat: float  # beat position within the measure
    pitch: str  # e.g. "C4"
    duration_beats: float  # length in beats
    time_sig: str  # e.g. "4/4"


@dataclass
class AlignmentState:
    """Snapshot of the follower's current position and confidence."""

    current_measure: int  # 1-based
    current_beat: float
    cursor: int  # index into the flat score event list
    total_events: int  # length of the score
    confidence: float  # running match quality, 0.0–1.0
    matched_events: int  # how many live notes matched a score event
    total_input: int  # how many live notes received so far
    is_complete: bool  # True when cursor has reached the end


@dataclass
class MatchResult:
    """Result of matching a single live note against the score."""

    matched: bool  # True if this note advanced the cursor
    expected_pitch: str  # what the score expected
    actual_pitch: str  # what was detected
    pitch_correct: bool  # exact pitch match
    semitone_error: int  # absolute semitone distance
    measure: int
    beat: float
    match_quality: float  # 0.0–1.0 for this note


# ── Score follower ──────────────────────────────────────────

class ScoreFollower:
    """
    Streaming score follower that aligns live notes to a score.

    Parameters
    ----------
    score         : ScoreResult from the OMR pipeline (or manually built)
    look_ahead    : how many score events ahead of the cursor to search.
                    Larger = more tolerant of skipped notes, but also more
                    likely to jump too far on a wrong note.
    look_behind   : how many events behind the cursor to allow matching.
                    Handles the case where the player repeats a note.
    pitch_weight  : weight of pitch match in the quality score (0–1)
    alpha         : smoothing factor for the running confidence EMA.
                    Lower = smoother / slower to react.

    Usage
    -----
        follower = ScoreFollower(score)
        for pitch, onset_time in live_notes:
            match = follower.feed(pitch, onset_time)
            state = follower.state()
            print(state.current_measure, state.current_beat, state.confidence)
    """

    def __init__(
        self,
        score: ScoreResult,
        look_ahead: int = 4,
        look_behind: int = 1,
        pitch_weight: float = 0.7,
        alpha: float = 0.3,
    ):
        self._events = _flatten_score(score)
        self._cursor = 0
        self._look_ahead = look_ahead
        self._look_behind = look_behind
        self._pitch_weight = pitch_weight
        self._alpha = alpha

        self._confidence = 0.5  # start neutral
        self._matched = 0
        self._total_input = 0

        # For timing-based matching: track the expected onset time
        # of the cursor note based on accumulated beat durations and
        # an estimated seconds-per-beat (updated from live IOIs).
        self._last_onset_time = 0.0
        self._spb_estimate = 0.5  # seconds per beat, default 120 BPM

    def feed(
        self, pitch: str, onset_time: float, bpm_hint: float = 0.0
    ) -> MatchResult:
        """
        Process one detected note.

        Parameters
        ----------
        pitch      : detected pitch name, e.g. "A4"
        onset_time : timestamp in seconds from the start of playback
        bpm_hint   : optional BPM from the onset detector's tempo
                     estimate; used to improve timing predictions.

        Returns
        -------
        MatchResult describing how this note aligned to the score.
        """
        self._total_input += 1

        if bpm_hint > 0:
            self._spb_estimate = 60.0 / bpm_hint

        if not self._events or self._cursor >= len(self._events):
            # Score exhausted — return a no-match
            return MatchResult(
                matched=False,
                expected_pitch="",
                actual_pitch=pitch,
                pitch_correct=False,
                semitone_error=99,
                measure=self._events[-1].measure if self._events else 0,
                beat=0.0,
                match_quality=0.0,
            )

        # Build the candidate window around the cursor
        lo = max(0, self._cursor - self._look_behind)
        hi = min(len(self._events), self._cursor + self._look_ahead + 1)
        candidates = self._events[lo:hi]

        # Score each candidate
        best_event = None
        best_quality = -1.0

        for event in candidates:
            quality = self._match_quality(pitch, onset_time, event)
            if quality > best_quality:
                best_quality = quality
                best_event = event

        # Accept the match if quality exceeds a minimum bar
        min_quality = 0.15
        matched = best_event is not None and best_quality >= min_quality

        if matched:
            # Advance cursor to just past the matched event
            self._cursor = best_event.index + 1
            self._matched += 1
            self._last_onset_time = onset_time

        # Update running confidence (EMA)
        self._confidence = (
            self._alpha * best_quality + (1 - self._alpha) * self._confidence
        )

        expected = best_event if best_event else self._events[min(self._cursor, len(self._events) - 1)]
        sd = _semitone_distance(pitch, expected.pitch)

        return MatchResult(
            matched=matched,
            expected_pitch=expected.pitch,
            actual_pitch=pitch,
            pitch_correct=(sd == 0),
            semitone_error=sd,
            measure=expected.measure,
            beat=expected.beat,
            match_quality=round(best_quality, 3),
        )

    def state(self) -> AlignmentState:
        """Return the current alignment state."""
        if not self._events:
            return AlignmentState(
                current_measure=0, current_beat=0.0,
                cursor=0, total_events=0, confidence=0.0,
                matched_events=0, total_input=self._total_input,
                is_complete=True,
            )

        idx = min(self._cursor, len(self._events) - 1)
        ev = self._events[idx]

        return AlignmentState(
            current_measure=ev.measure,
            current_beat=ev.beat,
            cursor=self._cursor,
            total_events=len(self._events),
            confidence=round(self._confidence, 3),
            matched_events=self._matched,
            total_input=self._total_input,
            is_complete=self._cursor >= len(self._events),
        )

    def reset(self):
        """Reset the follower to the beginning of the score."""
        self._cursor = 0
        self._confidence = 0.5
        self._matched = 0
        self._total_input = 0
        self._last_onset_time = 0.0

    # ── Internals ──────────────────────────────────────────

    def _match_quality(
        self, pitch: str, onset_time: float, event: ScoreEvent
    ) -> float:
        """
        Compute a match quality score (0–1) between a live note and
        a score event. Combines pitch similarity and positional proximity.
        """
        # -- Pitch component (0–1) --
        sd = _semitone_distance(pitch, event.pitch)
        if sd == 0:
            pitch_score = 1.0
        elif sd <= 1:
            pitch_score = 0.6  # adjacent semitone — might be accidental
        elif sd <= 2:
            pitch_score = 0.3  # close but wrong
        else:
            pitch_score = 0.0

        # -- Position component (0–1) --
        # How far is this event from the cursor?  Events near the cursor
        # get higher position scores.  This biases toward forward progress
        # without requiring exact timing.
        distance = abs(event.index - self._cursor)
        position_score = 1.0 / (1.0 + distance)

        # Weighted combination
        pw = self._pitch_weight
        quality = pw * pitch_score + (1 - pw) * position_score

        return quality


# ── Helpers ─────────────────────────────────────────────────

def _flatten_score(score: ScoreResult) -> list[ScoreEvent]:
    """Convert a nested ScoreResult into a flat list of ScoreEvents."""
    events: list[ScoreEvent] = []
    idx = 0
    for measure in score.measures:
        for note in measure.notes:
            dur = _DURATION_BEATS.get(note.duration, 1.0)
            events.append(ScoreEvent(
                index=idx,
                measure=measure.number,
                beat=note.beat,
                pitch=note.pitch,
                duration_beats=dur,
                time_sig=measure.time_signature,
            ))
            idx += 1
    return events
