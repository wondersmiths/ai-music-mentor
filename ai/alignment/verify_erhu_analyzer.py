#!/usr/bin/env python3
"""
Verification script for Erhu mistake detection (erhu_analyzer).

Tests that the analyzer penalizes real mistakes while tolerating
normal Erhu expressive techniques (vibrato, slides, rubato).

Run:  python -m ai.alignment.verify_erhu_analyzer
"""

from __future__ import annotations

import math
import sys

from ai.alignment.erhu_analyzer import (
    ErhuAnalysisResult,
    ErhuIssueType,
    ErhuSeverity,
    PitchSample,
    erhu_analyze,
)
from ai.omr.models import Measure, Note, ScoreResult

# ── Helpers ──────────────────────────────────────────────────

BPM = 120.0
SPB = 60.0 / BPM  # 0.5 seconds per beat

# MIDI values
D4_MIDI = 62.0
E4_MIDI = 64.0
Fs4_MIDI = 66.0  # F#4
A4_MIDI = 69.0


def make_score(measures_data: list[dict]) -> ScoreResult:
    """Build a ScoreResult from compact description."""
    duration_beats = {
        "whole": 4.0, "half": 2.0, "quarter": 1.0,
        "eighth": 0.5, "sixteenth": 0.25,
    }
    measures = []
    for i, md in enumerate(measures_data):
        ts = md.get("time_sig", "4/4")
        beat = 1.0
        notes = []
        for pitch, dur in md["notes"]:
            notes.append(Note(pitch=pitch, duration=dur, beat=beat))
            beat += duration_beats.get(dur, 1.0)
        measures.append(Measure(number=i + 1, time_signature=ts, notes=notes))
    return ScoreResult(
        title="Test", confidence=1.0, is_mock=False, measures=measures,
    )


def make_pitch_curve(
    segments: list[dict], dt: float = 0.010,
) -> list[PitchSample]:
    """
    Build a pitch curve from segments.

    Each segment: {"start": float, "end": float, "midi": float,
                   "confidence": float (default 0.9),
                   "vibrato_cents": float (default 0),
                   "vibrato_hz": float (default 5.5),
                   "drift_cents": float (default 0)}

    vibrato_cents: amplitude of vibrato oscillation (symmetric around midi)
    drift_cents: constant cents offset (e.g. +60 = 60 cents sharp)
    """
    samples = []
    for seg in segments:
        start = seg["start"]
        end = seg["end"]
        midi = seg.get("midi", 0.0)
        conf = seg.get("confidence", 0.9)
        vib_cents = seg.get("vibrato_cents", 0.0)
        vib_hz = seg.get("vibrato_hz", 5.5)
        drift_cents = seg.get("drift_cents", 0.0)

        t = start
        while t < end:
            # Apply vibrato (symmetric oscillation)
            vib_offset = vib_cents / 100.0 * math.sin(
                2 * math.pi * vib_hz * t
            )
            # Apply drift (constant offset)
            drift_offset = drift_cents / 100.0

            actual_midi = midi + vib_offset + drift_offset if midi > 0 else 0.0

            samples.append(PitchSample(
                time=round(t, 4),
                midi=round(actual_midi, 3) if actual_midi > 0 else 0.0,
                confidence=conf,
            ))
            t += dt

    # Sort by time (segments may overlap)
    samples.sort(key=lambda s: s.time)
    return samples


def run_test(name: str, test_fn) -> bool:
    """Run a single test, print pass/fail."""
    try:
        test_fn()
        print(f"  PASS  {name}")
        return True
    except AssertionError as e:
        print(f"  FAIL  {name}: {e}")
        return False


def issues_of_type(result: ErhuAnalysisResult, t: ErhuIssueType) -> list:
    return [i for i in result.issues if i.type == t]


# ── Test cases ───────────────────────────────────────────────

def test_perfect_play():
    """All notes played on-pitch, on-time. Zero issues."""
    score = make_score([
        {"notes": [("D4", "quarter"), ("E4", "quarter"),
                   ("F#4", "quarter"), ("A4", "quarter")]},
    ])

    # Perfect pitch curve: each note at correct MIDI, with onsets
    curve = make_pitch_curve([
        {"start": 0.0, "end": 0.45, "midi": D4_MIDI},
        {"start": 0.5, "end": 0.95, "midi": E4_MIDI},
        {"start": 1.0, "end": 1.45, "midi": Fs4_MIDI},
        {"start": 1.5, "end": 1.95, "midi": A4_MIDI},
    ])
    onsets = [0.0, 0.5, 1.0, 1.5]

    result = erhu_analyze(score, curve, onsets, bpm=BPM)

    assert result.notes_reached == 4, (
        f"expected 4 notes reached, got {result.notes_reached}"
    )
    assert len(result.issues) == 0, (
        f"expected 0 issues for perfect play, got {len(result.issues)}: "
        f"{[i.detail for i in result.issues]}"
    )
    assert result.accuracy >= 0.99, (
        f"expected accuracy ~1.0, got {result.accuracy}"
    )


def test_missed_note():
    """Skip F#4 entirely — silence where it should be. Expect missed_note."""
    score = make_score([
        {"notes": [("D4", "quarter"), ("E4", "quarter"),
                   ("F#4", "quarter"), ("A4", "quarter")]},
    ])

    curve = make_pitch_curve([
        {"start": 0.0, "end": 0.45, "midi": D4_MIDI},
        {"start": 0.5, "end": 0.95, "midi": E4_MIDI},
        # F#4 at 1.0-1.5: silence (midi=0)
        {"start": 1.0, "end": 1.45, "midi": 0.0, "confidence": 0.0},
        {"start": 1.5, "end": 1.95, "midi": A4_MIDI},
    ])
    onsets = [0.0, 0.5, 1.5]

    result = erhu_analyze(score, curve, onsets, bpm=BPM)

    missed = issues_of_type(result, ErhuIssueType.MISSED_NOTE)
    assert len(missed) >= 1, (
        f"expected ≥1 missed note issue, got {len(missed)}"
    )
    assert result.notes_reached == 3, (
        f"expected 3 notes reached, got {result.notes_reached}"
    )


def test_intonation_drift():
    """
    Play D4 consistently 70 cents sharp. Should flag INTONATION warning.
    """
    score = make_score([
        {"notes": [("D4", "half")]},
    ])

    curve = make_pitch_curve([
        {"start": 0.0, "end": 0.95, "midi": D4_MIDI, "drift_cents": 70.0},
    ])
    onsets = [0.0]

    result = erhu_analyze(score, curve, onsets, bpm=BPM)

    intonation = issues_of_type(result, ErhuIssueType.INTONATION)
    assert len(intonation) >= 1, (
        f"expected ≥1 intonation issue for 70-cent drift, "
        f"got {len(intonation)}"
    )
    assert intonation[0].severity in (ErhuSeverity.WARNING, ErhuSeverity.ERROR), (
        f"expected warning or error severity, got {intonation[0].severity}"
    )
    assert result.notes_reached == 1, "note should still count as reached"


def test_vibrato_tolerated():
    """
    Play D4 with ±30 cents vibrato at 5.5 Hz. Should produce NO
    intonation issue — vibrato is normal Erhu technique.
    """
    score = make_score([
        {"notes": [("D4", "half")]},
    ])

    curve = make_pitch_curve([
        {"start": 0.0, "end": 0.95, "midi": D4_MIDI,
         "vibrato_cents": 30.0, "vibrato_hz": 5.5},
    ])
    onsets = [0.0]

    result = erhu_analyze(score, curve, onsets, bpm=BPM)

    intonation = issues_of_type(result, ErhuIssueType.INTONATION)
    assert len(intonation) == 0, (
        f"vibrato should NOT cause intonation issues, "
        f"got {len(intonation)}: {[i.detail for i in intonation]}"
    )


def test_grace_slide_tolerated():
    """
    Brief pass through E4 range (<80 ms) during a D4→F#4 slide.
    E4 is NOT in the score — should NOT be flagged as anything.
    The target notes (D4 and F#4) should be reached.
    """
    score = make_score([
        {"notes": [("D4", "quarter"), ("F#4", "quarter")]},
    ])

    # D4 sustained, then quick slide through E4 (30ms), landing on F#4
    curve = make_pitch_curve([
        {"start": 0.0, "end": 0.45, "midi": D4_MIDI},
        # Quick slide through E4 — only 30ms
        {"start": 0.46, "end": 0.49, "midi": E4_MIDI},
        {"start": 0.5, "end": 0.95, "midi": Fs4_MIDI},
    ])
    onsets = [0.0, 0.5]

    result = erhu_analyze(score, curve, onsets, bpm=BPM)

    assert result.notes_reached == 2, (
        f"expected both D4 and F#4 reached, got {result.notes_reached}"
    )
    # No missed notes
    missed = issues_of_type(result, ErhuIssueType.MISSED_NOTE)
    assert len(missed) == 0, (
        f"expected 0 missed notes, got {len(missed)}"
    )


def test_expressive_timing_tolerated():
    """
    Notes arrive ±100 ms from expected time — within ±150 ms tolerance.
    Should NOT flag any rhythm issues.
    """
    score = make_score([
        {"notes": [("D4", "quarter"), ("E4", "quarter"),
                   ("F#4", "quarter"), ("A4", "quarter")]},
    ])

    # Slightly early/late but within tolerance
    curve = make_pitch_curve([
        {"start": 0.05, "end": 0.45, "midi": D4_MIDI},    # 50ms late
        {"start": 0.40, "end": 0.90, "midi": E4_MIDI},    # 100ms early
        {"start": 1.10, "end": 1.50, "midi": Fs4_MIDI},   # 100ms late
        {"start": 1.55, "end": 1.95, "midi": A4_MIDI},    # 50ms late
    ])
    onsets = [0.05, 0.40, 1.10, 1.55]

    result = erhu_analyze(score, curve, onsets, bpm=BPM)

    rhythm = issues_of_type(result, ErhuIssueType.RHYTHM)
    assert len(rhythm) == 0, (
        f"expressive timing should NOT cause rhythm issues, "
        f"got {len(rhythm)}: {[i.detail for i in rhythm]}"
    )


def test_phrase_rhythm_breakdown():
    """
    Measure played at double speed (50% of expected duration).
    Should flag phrase-level rhythm breakdown.
    """
    score = make_score([
        {"notes": [("D4", "quarter"), ("E4", "quarter"),
                   ("F#4", "quarter"), ("A4", "quarter")]},
    ])

    # Notes at half the expected spacing (rushing badly)
    curve = make_pitch_curve([
        {"start": 0.0, "end": 0.20, "midi": D4_MIDI},
        {"start": 0.25, "end": 0.45, "midi": E4_MIDI},
        {"start": 0.50, "end": 0.70, "midi": Fs4_MIDI},
        {"start": 0.75, "end": 0.95, "midi": A4_MIDI},
    ])
    onsets = [0.0, 0.25, 0.50, 0.75]

    result = erhu_analyze(score, curve, onsets, bpm=BPM)

    rhythm = issues_of_type(result, ErhuIssueType.RHYTHM)
    assert len(rhythm) >= 1, (
        f"expected ≥1 rhythm issue for double-speed phrase, "
        f"got {len(rhythm)}"
    )


def test_severe_intonation_error():
    """
    Play D4 a full semitone sharp (100 cents). Should flag ERROR severity.
    """
    score = make_score([
        {"notes": [("D4", "half")]},
    ])

    curve = make_pitch_curve([
        {"start": 0.0, "end": 0.95, "midi": D4_MIDI, "drift_cents": 100.0},
    ])
    onsets = [0.0]

    result = erhu_analyze(score, curve, onsets, bpm=BPM)

    intonation = issues_of_type(result, ErhuIssueType.INTONATION)
    assert len(intonation) >= 1, (
        f"expected intonation error for 100-cent drift, got 0"
    )
    assert intonation[0].severity == ErhuSeverity.ERROR, (
        f"expected ERROR severity for 100-cent drift, "
        f"got {intonation[0].severity}"
    )


def test_mixed_issues():
    """
    Multiple issues in one piece: missed note + intonation drift.
    Verify both are reported independently.
    """
    score = make_score([
        {"notes": [("D4", "quarter"), ("E4", "quarter"),
                   ("F#4", "quarter"), ("A4", "quarter")]},
    ])

    curve = make_pitch_curve([
        {"start": 0.0, "end": 0.45, "midi": D4_MIDI},
        # E4 played 65 cents sharp
        {"start": 0.5, "end": 0.95, "midi": E4_MIDI, "drift_cents": 65.0},
        # F#4 missed (silence)
        {"start": 1.0, "end": 1.45, "midi": 0.0, "confidence": 0.0},
        {"start": 1.5, "end": 1.95, "midi": A4_MIDI},
    ])
    onsets = [0.0, 0.5, 1.5]

    result = erhu_analyze(score, curve, onsets, bpm=BPM)

    missed = issues_of_type(result, ErhuIssueType.MISSED_NOTE)
    intonation = issues_of_type(result, ErhuIssueType.INTONATION)

    assert len(missed) >= 1, "expected missed F#4"
    assert len(intonation) >= 1, "expected intonation issue on E4"
    assert result.notes_reached == 3, (
        f"expected 3 notes reached, got {result.notes_reached}"
    )


def test_low_confidence_ignored():
    """
    Pitch samples with confidence < 0.3 should be ignored.
    A note with only low-confidence samples counts as missed.
    """
    score = make_score([
        {"notes": [("D4", "quarter")]},
    ])

    # D4 samples but all at very low confidence
    curve = make_pitch_curve([
        {"start": 0.0, "end": 0.45, "midi": D4_MIDI, "confidence": 0.1},
    ])
    onsets = [0.0]

    result = erhu_analyze(score, curve, onsets, bpm=BPM)

    missed = issues_of_type(result, ErhuIssueType.MISSED_NOTE)
    assert len(missed) >= 1, (
        "low-confidence samples should not count — note should be missed"
    )


# ── Main ─────────────────────────────────────────────────────

def main():
    print("Erhu mistake detection verification")
    print("=" * 55)

    tests = [
        ("Perfect play — zero issues", test_perfect_play),
        ("Missed note (F#4 silent)", test_missed_note),
        ("Intonation drift (70 cents sharp)", test_intonation_drift),
        ("Vibrato tolerated (±30 cents)", test_vibrato_tolerated),
        ("Grace slide tolerated (<80 ms)", test_grace_slide_tolerated),
        ("Expressive timing tolerated (±100 ms)", test_expressive_timing_tolerated),
        ("Phrase rhythm breakdown (2x speed)", test_phrase_rhythm_breakdown),
        ("Severe intonation (100 cents → ERROR)", test_severe_intonation_error),
        ("Mixed issues (missed + drift)", test_mixed_issues),
        ("Low confidence ignored", test_low_confidence_ignored),
    ]

    results = [run_test(name, fn) for name, fn in tests]
    passed = sum(results)
    total = len(results)

    print("=" * 55)
    print(f"{passed}/{total} tests passed")

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
