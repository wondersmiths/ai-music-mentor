"""
Practice analyzer — compares a live performance against a score and
produces a list of concrete issues (wrong pitch, missed note, rhythm
deviation) with measure numbers and severity levels.

Works after a performance: provide the full score and the sequence of
detected notes, and get back a graded report. For real-time feedback
during play, use ScoreFollower instead.

Algorithm
---------
1. Flatten the score into expected events with absolute beat positions.
2. Convert detected onset timestamps to absolute beats via BPM.
3. Two-pass alignment:
   a) Anchor exact-pitch matches within a tight timing window.
   b) Match remaining events greedily by pitch + timing score.
4. Walk the alignment and classify each event:
   - Matched with correct pitch → check rhythm deviation
   - Matched with wrong pitch   → wrong-pitch issue
   - Expected but never matched → missed-note issue
   - Detected but unmatched     → extra-note issue (info only)
5. Rate severity by simple thresholds.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from ai.omr.models import ScoreResult


# ── Enums ───────────────────────────────────────────────────

class IssueType(str, Enum):
    WRONG_PITCH = "wrong_pitch"
    MISSED_NOTE = "missed_note"
    RHYTHM_DEVIATION = "rhythm_deviation"
    EXTRA_NOTE = "extra_note"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


# ── Public data structures ──────────────────────────────────

@dataclass
class DetectedNote:
    """A note detected from the live audio stream."""

    pitch: str       # e.g. "A4"
    time: float      # onset timestamp in seconds
    confidence: float


@dataclass
class Issue:
    """A single performance issue."""

    type: IssueType
    severity: Severity
    measure: int         # 1-based measure number
    beat: float          # beat position in the measure
    expected_pitch: str  # what the score says (empty for extra notes)
    actual_pitch: str    # what was played (empty for missed notes)
    detail: str          # human-readable description


@dataclass
class AnalysisResult:
    """Full analysis of a practice session."""

    issues: list[Issue]
    total_notes: int       # notes in the score
    notes_hit: int         # correctly matched (pitch within tolerance)
    accuracy: float        # notes_hit / total_notes, 0.0–1.0
    rhythm_score: float    # average rhythm accuracy, 0.0–1.0


# ── Thresholds ──────────────────────────────────────────────

@dataclass
class Thresholds:
    """Tunable thresholds for issue classification."""

    # Pitch: semitone distance boundaries
    pitch_warn: int = 1       # ±1 semitone → warning
    pitch_error: int = 2      # ≥2 semitones → error

    # Rhythm: deviation in beats
    rhythm_ok: float = 0.15   # within this → no issue
    rhythm_warn: float = 0.25 # within this → warning
    # beyond rhythm_warn → error

    # Alignment: max beat distance to consider a match
    match_window: float = 1.5


# ── Pitch helpers ───────────────────────────────────────────

_PITCH_RE = re.compile(r"^([A-Ga-g]#?)(-?\d)$")
_NAME_TO_SEMI = {
    "C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5,
    "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11,
}
_DURATION_BEATS = {
    "whole": 4.0, "half": 2.0, "quarter": 1.0,
    "eighth": 0.5, "sixteenth": 0.25,
}


def _to_midi(pitch: str) -> int:
    m = _PITCH_RE.match(pitch)
    if not m:
        return -1
    name, octave = m.group(1).upper(), int(m.group(2))
    semi = _NAME_TO_SEMI.get(name, -1)
    return (octave + 1) * 12 + semi if semi >= 0 else -1


def _semi_dist(a: str, b: str) -> int:
    ma, mb = _to_midi(a), _to_midi(b)
    if ma < 0 or mb < 0:
        return 99
    return abs(ma - mb)


# ── Internal: expected event ────────────────────────────────

@dataclass
class _Expected:
    """A score note with its precomputed absolute beat position."""

    index: int
    measure: int
    beat: float            # beat within the measure (1-based)
    abs_beat: float        # absolute beat from score start (1-based)
    pitch: str
    duration_beats: float
    matched: bool = False
    matched_note: Optional[DetectedNote] = None
    matched_beat_offset: float = 0.0


# ── Core ────────────────────────────────────────────────────

def analyze(
    score: ScoreResult,
    detected: list[DetectedNote],
    bpm: float = 120.0,
    thresholds: Optional[Thresholds] = None,
) -> AnalysisResult:
    """
    Compare detected notes against the score and return issues.

    Parameters
    ----------
    score      : structured score from the OMR pipeline
    detected   : list of DetectedNotes in chronological order
    bpm        : tempo in beats per minute (converts timestamps to beats)
    thresholds : optional custom thresholds

    Returns
    -------
    AnalysisResult with issues, accuracy, and rhythm score.
    """
    th = thresholds or Thresholds()

    # 1. Flatten score → expected events with absolute beat positions
    expected = _flatten(score)
    if not expected:
        return AnalysisResult(
            issues=[], total_notes=0, notes_hit=0,
            accuracy=1.0, rhythm_score=1.0,
        )

    # 2. Convert detected timestamps to absolute beat positions
    spb = 60.0 / bpm
    t0 = detected[0].time if detected else 0.0
    det_beats = [(d.time - t0) / spb + 1.0 for d in detected]

    # 3. Two-pass alignment
    _align(expected, detected, det_beats, th.match_window)

    # 4. Classify issues
    issues: list[Issue] = []
    notes_hit = 0
    rhythm_devs: list[float] = []

    for ev in expected:
        if not ev.matched:
            issues.append(Issue(
                type=IssueType.MISSED_NOTE,
                severity=Severity.ERROR,
                measure=ev.measure,
                beat=ev.beat,
                expected_pitch=ev.pitch,
                actual_pitch="",
                detail=f"Expected {ev.pitch} at beat {ev.beat}",
            ))
            continue

        det = ev.matched_note
        sd = _semi_dist(ev.pitch, det.pitch)

        # Pitch check
        if sd == 0:
            notes_hit += 1
        elif sd <= th.pitch_warn:
            notes_hit += 1  # close enough to count as a hit
            issues.append(Issue(
                type=IssueType.WRONG_PITCH,
                severity=Severity.WARNING,
                measure=ev.measure,
                beat=ev.beat,
                expected_pitch=ev.pitch,
                actual_pitch=det.pitch,
                detail=f"Expected {ev.pitch}, heard {det.pitch} "
                       f"({sd} semitone{'s' if sd != 1 else ''} off)",
            ))
        else:
            issues.append(Issue(
                type=IssueType.WRONG_PITCH,
                severity=Severity.ERROR,
                measure=ev.measure,
                beat=ev.beat,
                expected_pitch=ev.pitch,
                actual_pitch=det.pitch,
                detail=f"Expected {ev.pitch}, heard {det.pitch} "
                       f"({sd} semitones off)",
            ))

        # Rhythm check
        dev = abs(ev.matched_beat_offset)
        rhythm_devs.append(dev)

        if dev > th.rhythm_warn:
            issues.append(Issue(
                type=IssueType.RHYTHM_DEVIATION,
                severity=Severity.ERROR,
                measure=ev.measure,
                beat=ev.beat,
                expected_pitch=ev.pitch,
                actual_pitch=det.pitch,
                detail=f"Beat {ev.beat}: {_direction(ev.matched_beat_offset)} "
                       f"by {dev:.2f} beats",
            ))
        elif dev > th.rhythm_ok:
            issues.append(Issue(
                type=IssueType.RHYTHM_DEVIATION,
                severity=Severity.WARNING,
                measure=ev.measure,
                beat=ev.beat,
                expected_pitch=ev.pitch,
                actual_pitch=det.pitch,
                detail=f"Beat {ev.beat}: slightly {_direction(ev.matched_beat_offset)} "
                       f"by {dev:.2f} beats",
            ))

    # Extra notes (detected but not matched to any expected event)
    matched_ids = {id(ev.matched_note) for ev in expected if ev.matched}
    for i, det in enumerate(detected):
        if id(det) not in matched_ids:
            measure = _nearest_measure(det_beats[i], expected)
            issues.append(Issue(
                type=IssueType.EXTRA_NOTE,
                severity=Severity.INFO,
                measure=measure,
                beat=0.0,
                expected_pitch="",
                actual_pitch=det.pitch,
                detail=f"Extra note {det.pitch} (not in score)",
            ))

    # Summary scores
    total = len(expected)
    accuracy = notes_hit / total if total > 0 else 1.0

    if rhythm_devs:
        avg_dev = sum(rhythm_devs) / len(rhythm_devs)
        rhythm_score = max(0.0, 1.0 - avg_dev)  # 1 beat off → 0.0
    else:
        rhythm_score = 1.0

    severity_rank = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
    issues.sort(key=lambda i: (i.measure, i.beat, severity_rank[i.severity]))

    return AnalysisResult(
        issues=issues,
        total_notes=total,
        notes_hit=notes_hit,
        accuracy=round(accuracy, 3),
        rhythm_score=round(rhythm_score, 3),
    )


# ── Helpers ─────────────────────────────────────────────────

def _flatten(score: ScoreResult) -> list[_Expected]:
    """Convert nested score to flat list with precomputed absolute beats."""
    events: list[_Expected] = []
    idx = 0
    beat_offset = 0.0  # cumulative beats before the current measure

    for measure in score.measures:
        bpm_num = _parse_beats(measure.time_signature)
        for note in measure.notes:
            dur = _DURATION_BEATS.get(note.duration, 1.0)
            events.append(_Expected(
                index=idx,
                measure=measure.number,
                beat=note.beat,
                abs_beat=beat_offset + note.beat,
                pitch=note.pitch,
                duration_beats=dur,
            ))
            idx += 1
        beat_offset += bpm_num

    return events


def _parse_beats(time_sig: str) -> float:
    """Parse beats per measure from a time signature string like '4/4'."""
    parts = time_sig.split("/")
    if len(parts) == 2:
        try:
            return float(parts[0])
        except ValueError:
            pass
    return 4.0


def _align(
    expected: list[_Expected],
    detected: list[DetectedNote],
    det_beats: list[float],
    match_window: float,
) -> None:
    """
    Two-pass alignment.

    Pass 1: anchor exact-pitch matches within a tight window (±0.75
    beats). This prevents correctly-played notes from being stolen
    by earlier missed notes.

    Pass 2: match remaining expected events to the best available
    detected note by pitch + timing score.
    """
    available = set(range(len(detected)))

    # Pass 1: exact pitch, tight window
    tight = min(match_window, 0.75)
    for ev in expected:
        best_idx = -1
        best_dist = tight + 1.0

        for i in available:
            if _semi_dist(ev.pitch, detected[i].pitch) != 0:
                continue
            dist = abs(det_beats[i] - ev.abs_beat)
            if dist <= tight and dist < best_dist:
                best_dist = dist
                best_idx = i

        if best_idx >= 0:
            ev.matched = True
            ev.matched_note = detected[best_idx]
            ev.matched_beat_offset = det_beats[best_idx] - ev.abs_beat
            available.discard(best_idx)

    # Pass 2: remaining events, any pitch, full window
    for ev in expected:
        if ev.matched:
            continue

        best_idx = -1
        best_score = -1.0

        for i in available:
            beat_dist = abs(det_beats[i] - ev.abs_beat)
            if beat_dist > match_window:
                continue

            sd = _semi_dist(ev.pitch, detected[i].pitch)
            pitch_score = max(0.0, 1.0 - sd / 12.0)
            timing_score = 1.0 - beat_dist / match_window
            score = 0.6 * pitch_score + 0.4 * timing_score

            if score > best_score:
                best_score = score
                best_idx = i

        if best_idx >= 0 and best_score > 0.2:
            ev.matched = True
            ev.matched_note = detected[best_idx]
            ev.matched_beat_offset = det_beats[best_idx] - ev.abs_beat
            available.discard(best_idx)


def _direction(offset: float) -> str:
    if offset > 0:
        return "late"
    if offset < 0:
        return "early"
    return "on time"


def _nearest_measure(det_beat: float, expected: list[_Expected]) -> int:
    """Find the measure number closest to an absolute beat position."""
    best = expected[0]
    best_dist = abs(best.abs_beat - det_beat)
    for ev in expected[1:]:
        d = abs(ev.abs_beat - det_beat)
        if d < best_dist:
            best_dist = d
            best = ev
    return best.measure
