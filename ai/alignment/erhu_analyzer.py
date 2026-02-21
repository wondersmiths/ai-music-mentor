"""
Erhu-aware mistake detection — classifies performance issues while
respecting expressive techniques that are normal in Erhu playing.

Design rationale
----------------
A generic note-by-note analyzer penalizes slides, vibrato, and rubato
— all of which are *correct* Erhu technique. This analyzer is designed
to feel fair to a human Erhu teacher by distinguishing real mistakes
from expressive intent:

    PENALIZED (real mistakes):
      - Missed a target pitch entirely (pitch never visited the range)
      - Sustained intonation drift (>50 cents for >200 ms — not vibrato)
      - Phrase-level rhythm breakdown (whole measure rushing/dragging)

    TOLERATED (normal Erhu expression):
      - Grace slides (brief pitch excursions during transitions)
      - Vibrato (rapid oscillation around the target — mean stays close)
      - Expressive timing / rubato (±150 ms per note is fine)
      - Portamento between notes

Algorithm
---------
For each expected note in the score:

1. Define a time window: [expected_onset - tolerance, expected_onset +
   note_duration + tolerance].
2. Gather all pitch samples in that window from the continuous pitch
   curve.
3. **Pass-through check**: did any samples fall within ±1 semitone of
   the target for at least 80 ms? If not → MISSED_NOTE.
4. **Intonation check**: for samples near the target (±1.5 semitones),
   compute the mean cents deviation. If |mean| > 50 cents → INTONATION
   issue. Using the mean filters out vibrato (symmetric oscillation
   averages to ~0) while catching sustained drift (consistently
   sharp/flat). The 1.5-semitone inclusion radius is tight enough to
   exclude bleed from adjacent scale notes.

For rhythm (phrase-level, not note-level):

1. Group matched notes by measure.
2. For each measure with ≥2 matched notes, compare the actual time span
   (first to last onset) to the expected span.
3. If the tempo ratio deviates > 20% → RHYTHM issue. This catches whole-
   phrase rushing/dragging without penalizing individual note timing.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ai.omr.models import ScoreResult


# ── Enums ────────────────────────────────────────────────────

class ErhuIssueType(str, Enum):
    MISSED_NOTE = "missed_note"
    INTONATION = "intonation"
    RHYTHM = "rhythm"


class ErhuSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


# ── Data structures ──────────────────────────────────────────

@dataclass
class PitchSample:
    """One frame from the continuous pitch curve."""

    time: float        # seconds from start
    midi: float        # fractional MIDI number (0.0 if silent)
    confidence: float  # pitch tracker confidence, 0.0–1.0


@dataclass
class ErhuIssue:
    """A single performance issue."""

    type: ErhuIssueType
    severity: ErhuSeverity
    measure: int
    detail: str


@dataclass
class ErhuAnalysisResult:
    """Complete analysis of an Erhu practice session."""

    issues: list[ErhuIssue]
    total_notes: int           # notes in the score
    notes_reached: int         # notes where pitch visited the target range
    accuracy: float            # notes_reached / total_notes, 0.0–1.0
    phrase_rhythm_score: float # average phrase rhythm quality, 0.0–1.0


# ── Thresholds ───────────────────────────────────────────────

@dataclass
class ErhuThresholds:
    """Tunable parameters for Erhu-fair issue classification."""

    # Pitch pass-through: semitones tolerance for "visited the target"
    pitch_tolerance_st: float = 1.0

    # Minimum dwell time (seconds) to count as "reached the note"
    # This filters out grace slides (brief pitch excursions)
    min_dwell_s: float = 0.080  # 80 ms

    # Intonation: cents thresholds for drift detection
    # Uses mean deviation to filter out symmetric vibrato
    intonation_warn_cents: float = 50.0   # mean drift → warning
    intonation_error_cents: float = 80.0  # mean drift → error

    # Intonation: how far from target to include samples in mean calc.
    # 1.5 semitones excludes adjacent-note bleed (most scale steps are
    # 1-2 semitones apart) while still capturing moderate drift.
    intonation_inclusion_st: float = 1.5  # ±1.5 semitones

    # Rhythm: phrase-level tempo ratio thresholds
    # ratio = actual_span / expected_span
    rhythm_warn_ratio: float = 0.20   # >20% off → warning
    rhythm_error_ratio: float = 0.35  # >35% off → error

    # Time tolerance for the note search window (seconds)
    time_tolerance_s: float = 0.300   # ±300 ms window expansion

    # Minimum pitch confidence to include a sample
    min_confidence: float = 0.3


# ── Pitch helpers ────────────────────────────────────────────

_PITCH_RE = re.compile(r"^([A-Ga-g]#?)(-?\d)$")
_NAME_TO_SEMI = {
    "C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5,
    "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11,
}
_DURATION_BEATS = {
    "whole": 4.0, "half": 2.0, "quarter": 1.0,
    "eighth": 0.5, "sixteenth": 0.25,
}


def _pitch_to_midi(pitch: str) -> float:
    m = _PITCH_RE.match(pitch)
    if not m:
        return -1.0
    name, octave = m.group(1).upper(), int(m.group(2))
    semi = _NAME_TO_SEMI.get(name, -1)
    if semi < 0:
        return -1.0
    return float((octave + 1) * 12 + semi)


# ── Internal: expected note with absolute time ───────────────

@dataclass
class _ExpectedNote:
    index: int
    measure: int
    beat: float
    pitch: str
    midi: float
    expected_time: float   # seconds from start
    duration_s: float      # expected duration in seconds


def _linearize(score: ScoreResult, bpm: float) -> list[_ExpectedNote]:
    """Flatten score into list of expected notes with absolute times."""
    spb = 60.0 / bpm
    notes: list[_ExpectedNote] = []
    idx = 0
    beat_offset = 0.0

    for measure in score.measures:
        num_beats = float(measure.time_signature.split("/")[0])
        for note in measure.notes:
            midi = _pitch_to_midi(note.pitch)
            dur_beats = _DURATION_BEATS.get(note.duration, 1.0)
            abs_beat = beat_offset + note.beat - 1.0  # 0-based
            notes.append(_ExpectedNote(
                index=idx,
                measure=measure.number,
                beat=note.beat,
                pitch=note.pitch,
                midi=midi,
                expected_time=abs_beat * spb,
                duration_s=dur_beats * spb,
            ))
            idx += 1
        beat_offset += num_beats

    return notes


# ── Core analysis ────────────────────────────────────────────

def erhu_analyze(
    score: ScoreResult,
    pitch_curve: list[PitchSample],
    onset_times: list[float],
    bpm: float = 120.0,
    thresholds: Optional[ErhuThresholds] = None,
) -> ErhuAnalysisResult:
    """
    Analyze an Erhu performance against a score.

    Parameters
    ----------
    score        : structured score from the OMR pipeline
    pitch_curve  : continuous pitch samples (time, midi, confidence)
    onset_times  : onset timestamps from ErhuOnsetDetector
    bpm          : reference tempo
    thresholds   : optional custom thresholds

    Returns
    -------
    ErhuAnalysisResult with issues, accuracy, and phrase rhythm score.
    """
    th = thresholds or ErhuThresholds()
    expected = _linearize(score, bpm)

    if not expected:
        return ErhuAnalysisResult(
            issues=[], total_notes=0, notes_reached=0,
            accuracy=1.0, phrase_rhythm_score=1.0,
        )

    issues: list[ErhuIssue] = []
    notes_reached = 0

    for note in expected:
        # Define search window
        window_start = note.expected_time - th.time_tolerance_s
        window_end = note.expected_time + note.duration_s + th.time_tolerance_s

        # Gather pitch samples in window with sufficient confidence
        samples = [
            s for s in pitch_curve
            if window_start <= s.time <= window_end
            and s.midi > 0
            and s.confidence >= th.min_confidence
        ]

        # ── Pass-through check ───────────────────────────────
        # Did the pitch visit ±1 semitone of target for ≥80 ms?
        reached = _check_pass_through(
            samples, note.midi, th.pitch_tolerance_st, th.min_dwell_s,
        )

        if not reached:
            issues.append(ErhuIssue(
                type=ErhuIssueType.MISSED_NOTE,
                severity=ErhuSeverity.ERROR,
                measure=note.measure,
                detail=f"Beat {note.beat}: {note.pitch} — pitch never "
                       f"reached the target range",
            ))
            continue

        notes_reached += 1

        # ── Intonation check ─────────────────────────────────
        # Compute mean cents deviation of samples near the target.
        # Vibrato (symmetric oscillation) averages out to ~0.
        # Sustained drift (consistently sharp/flat) shows as
        # |mean| > 50 cents.
        mean_cents = _mean_cents_deviation(
            samples, note.midi, th.intonation_inclusion_st,
        )

        if mean_cents is not None:
            abs_cents = abs(mean_cents)
            direction = "sharp" if mean_cents > 0 else "flat"

            if abs_cents >= th.intonation_error_cents:
                issues.append(ErhuIssue(
                    type=ErhuIssueType.INTONATION,
                    severity=ErhuSeverity.ERROR,
                    measure=note.measure,
                    detail=f"Beat {note.beat}: {note.pitch} is {abs_cents:.0f} "
                           f"cents {direction} (sustained drift)",
                ))
            elif abs_cents >= th.intonation_warn_cents:
                issues.append(ErhuIssue(
                    type=ErhuIssueType.INTONATION,
                    severity=ErhuSeverity.WARNING,
                    measure=note.measure,
                    detail=f"Beat {note.beat}: {note.pitch} is {abs_cents:.0f} "
                           f"cents {direction}",
                ))

    # ── Phrase-level rhythm analysis ─────────────────────────
    # Decoupled from pitch matching: matches onsets to expected
    # times directly so rhythm issues are detected even when the
    # player rushes/drags far from expected timing windows.
    phrase_scores = _analyze_phrase_rhythm(expected, onset_times, th)
    for issue in phrase_scores["issues"]:
        issues.append(issue)

    # Sort by measure, then severity
    severity_rank = {
        ErhuSeverity.ERROR: 0,
        ErhuSeverity.WARNING: 1,
        ErhuSeverity.INFO: 2,
    }
    issues.sort(key=lambda i: (i.measure, severity_rank[i.severity]))

    total = len(expected)
    accuracy = notes_reached / total if total > 0 else 1.0

    return ErhuAnalysisResult(
        issues=issues,
        total_notes=total,
        notes_reached=notes_reached,
        accuracy=round(accuracy, 3),
        phrase_rhythm_score=round(phrase_scores["score"], 3),
    )


# ── Pass-through detection ───────────────────────────────────

def _check_pass_through(
    samples: list[PitchSample],
    target_midi: float,
    tolerance_st: float,
    min_dwell_s: float,
) -> bool:
    """
    Check if pitch samples visit the target range for at least
    min_dwell_s seconds. This filters out grace slides — brief
    pitch excursions that pass through a note without dwelling.
    """
    if not samples:
        return False

    # Accumulate total time spent in the target range
    dwell_total = 0.0
    prev_time: Optional[float] = None

    for s in samples:
        if abs(s.midi - target_midi) <= tolerance_st:
            if prev_time is not None:
                dwell_total += s.time - prev_time
            prev_time = s.time
        else:
            prev_time = None

    # Also count the initial frame if it's in range
    if dwell_total == 0.0 and prev_time is not None:
        # Only one sample was in range — count as minimal dwell
        dwell_total = 0.001

    return dwell_total >= min_dwell_s


# ── Intonation (mean cents deviation) ────────────────────────

def _mean_cents_deviation(
    samples: list[PitchSample],
    target_midi: float,
    inclusion_st: float,
) -> Optional[float]:
    """
    Compute mean cents deviation of pitch samples near the target.

    Only includes samples within ±inclusion_st semitones of target.
    Returns None if no qualifying samples.

    Using the mean filters out vibrato: symmetric oscillation
    (±30 cents at 5-7 Hz) averages to ~0 cents. Sustained drift
    (player consistently 60 cents sharp) shows as mean ≈ +60.
    """
    deviations = []
    for s in samples:
        delta_st = s.midi - target_midi
        if abs(delta_st) <= inclusion_st:
            deviations.append(delta_st * 100.0)  # semitones → cents

    if not deviations:
        return None

    return sum(deviations) / len(deviations)


# ── Phrase-level rhythm ──────────────────────────────────────

def _analyze_phrase_rhythm(
    expected: list[_ExpectedNote],
    onset_times: list[float],
    th: ErhuThresholds,
) -> dict:
    """
    Analyze rhythm at the phrase (measure) level.

    Decoupled from pitch matching: greedily matches onsets to expected
    note times by proximity, then compares phrase-level timing ratios.
    This works even when the player rushes or drags far outside the
    pitch-matching windows.

    For each measure with ≥2 matched onsets, compares actual time span
    to expected span. Flags measures where the ratio deviates
    significantly — catching whole-phrase rushing/dragging without
    penalizing individual note expressiveness.
    """
    issues: list[ErhuIssue] = []
    ratios: list[float] = []

    if not onset_times or not expected:
        return {"issues": issues, "score": 1.0}

    # Greedy nearest-match: assign each expected note to its closest
    # onset (by time), without reusing onsets.
    available = sorted(onset_times)
    matched: list[tuple[int, float, float]] = []  # (measure, expected_t, actual_t)

    for note in expected:
        if not available:
            break
        # Find closest available onset
        best_idx = 0
        best_dist = abs(available[0] - note.expected_time)
        for i, t in enumerate(available[1:], 1):
            d = abs(t - note.expected_time)
            if d < best_dist:
                best_dist = d
                best_idx = i
        matched.append((note.measure, note.expected_time, available[best_idx]))
        available.pop(best_idx)

    # Group by measure
    by_measure: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for measure, expected_t, actual_t in matched:
        by_measure[measure].append((expected_t, actual_t))

    for measure, times in sorted(by_measure.items()):
        if len(times) < 2:
            continue

        times.sort(key=lambda x: x[0])

        expected_span = times[-1][0] - times[0][0]
        actual_span = times[-1][1] - times[0][1]

        if expected_span <= 0:
            continue

        ratio = actual_span / expected_span
        deviation = abs(1.0 - ratio)
        ratios.append(max(0.0, 1.0 - deviation))

        if deviation >= th.rhythm_error_ratio:
            direction = "rushing" if ratio < 1.0 else "dragging"
            issues.append(ErhuIssue(
                type=ErhuIssueType.RHYTHM,
                severity=ErhuSeverity.ERROR,
                measure=measure,
                detail=f"Phrase rhythm: {direction} "
                       f"({deviation * 100:.0f}% tempo deviation)",
            ))
        elif deviation >= th.rhythm_warn_ratio:
            direction = "rushing" if ratio < 1.0 else "dragging"
            issues.append(ErhuIssue(
                type=ErhuIssueType.RHYTHM,
                severity=ErhuSeverity.WARNING,
                measure=measure,
                detail=f"Phrase rhythm: slightly {direction} "
                       f"({deviation * 100:.0f}% tempo deviation)",
            ))

    score = sum(ratios) / len(ratios) if ratios else 1.0
    return {"issues": issues, "score": max(0.0, score)}
