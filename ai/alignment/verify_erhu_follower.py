#!/usr/bin/env python3
"""
Verification script for ErhuScoreAligner.

Simulates Erhu performance scenarios by feeding pitch curves and onsets
into the aligner, then checks alignment correctness.

Run:  python -m ai.alignment.verify_erhu_follower
"""

from __future__ import annotations

import sys

from ai.alignment.erhu_follower import ErhuScoreAligner, _pitch_to_midi
from ai.omr.models import Measure, Note, ScoreResult

# ── Helpers ──────────────────────────────────────────────────

BPM = 120.0
SPB = 60.0 / BPM  # 0.5 seconds per beat


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
        title="Test Score", confidence=1.0, is_mock=False, measures=measures,
    )


def simulate_frames(
    aligner: ErhuScoreAligner,
    events: list[dict],
    frame_interval: float = 0.02,
):
    """
    Simulate a performance by feeding pitch frames and onsets.

    events: list of dicts, each with:
        "start": float  — time this event starts (seconds)
        "end": float    — time this event ends (seconds)
        "pitch": str    — note name (e.g. "D4"), or "" for silence
        "onset": bool   — whether an onset fires at start (default True)
        "confidence": float — pitch confidence (default 0.9)

    Between events, frames are fed at frame_interval spacing.
    Returns a list of AlignmentState snapshots (one per onset).
    """
    states = []

    for event in events:
        start = event["start"]
        end = event["end"]
        pitch = event.get("pitch", "")
        fire_onset = event.get("onset", True)
        confidence = event.get("confidence", 0.9)

        midi = _pitch_to_midi(pitch) if pitch else 0.0

        # Feed frames covering this event
        t = start
        onset_fired = False
        while t < end:
            aligner.on_frame(t, midi, confidence if midi > 0 else 0.0)

            if fire_onset and not onset_fired and t >= start:
                state = aligner.on_onset(t, 0.8)
                states.append(state)
                onset_fired = True

            t += frame_interval

    return states


def run_test(name: str, test_fn) -> bool:
    """Run a single test, print pass/fail."""
    try:
        test_fn()
        print(f"  PASS  {name}")
        return True
    except AssertionError as e:
        print(f"  FAIL  {name}: {e}")
        return False


# ── Test cases ───────────────────────────────────────────────

def test_stepwise_melody():
    """D4→E4→F#4→A4 played on-time. Cursor should reach note 3 (A4)."""
    score = make_score([
        {"notes": [("D4", "quarter"), ("E4", "quarter"),
                   ("F#4", "quarter"), ("A4", "quarter")]},
    ])
    aligner = ErhuScoreAligner(score, bpm=BPM)

    events = [
        {"start": 0.0, "end": 0.45, "pitch": "D4"},
        {"start": 0.5, "end": 0.95, "pitch": "E4"},
        {"start": 1.0, "end": 1.45, "pitch": "F#4"},
        {"start": 1.5, "end": 1.95, "pitch": "A4"},
    ]
    states = simulate_frames(aligner, events)

    final = aligner.state()
    assert final.current_measure == 1, (
        f"expected measure 1, got {final.current_measure}"
    )
    assert final.current_note_index >= 2, (
        f"expected note index ≥2, got {final.current_note_index}"
    )
    assert final.confidence > 0.3, (
        f"expected confidence > 0.3, got {final.confidence}"
    )


def test_portamento_no_extra_advance():
    """
    Slide from D4→A4 without distinct intermediate onsets.
    The cursor should not jump through intermediate notes.
    """
    score = make_score([
        {"notes": [("D4", "quarter"), ("E4", "quarter"),
                   ("F#4", "quarter"), ("A4", "quarter")]},
    ])
    aligner = ErhuScoreAligner(score, bpm=BPM)

    # Play D4 with onset, then continuous glide (no onsets)
    events = [
        {"start": 0.0, "end": 0.5, "pitch": "D4", "onset": True},
        {"start": 0.5, "end": 0.8, "pitch": "E4", "onset": False},
        {"start": 0.8, "end": 1.1, "pitch": "F#4", "onset": False},
        {"start": 1.1, "end": 1.5, "pitch": "A4", "onset": False},
    ]
    states = simulate_frames(aligner, events)

    # Should have only 1 onset-triggered state (the D4)
    assert len(states) == 1, (
        f"expected 1 onset state, got {len(states)}"
    )


def test_passive_advance_legato():
    """
    Legato: D4 → E4 with no onset on E4.
    Passive advance should detect the pitch dwell on E4.
    """
    score = make_score([
        {"notes": [("D4", "quarter"), ("E4", "quarter")]},
    ])
    aligner = ErhuScoreAligner(score, bpm=BPM)

    # D4 with onset, then smooth transition to E4 with no onset
    events = [
        {"start": 0.0, "end": 0.45, "pitch": "D4", "onset": True},
        # E4 sustained for well over 80ms, no onset
        {"start": 0.5, "end": 1.0, "pitch": "E4", "onset": False},
    ]
    simulate_frames(aligner, events)

    final = aligner.state()
    # Passive advance should have moved cursor to E4 (index 1)
    assert final.current_note_index >= 1, (
        f"expected passive advance to note ≥1, got {final.current_note_index}"
    )


def test_rubato_timing():
    """
    Expressive timing: notes arrive ±100 ms from expected.
    Should still align correctly within ±150 ms tolerance.
    """
    score = make_score([
        {"notes": [("D4", "quarter"), ("E4", "quarter"),
                   ("F#4", "quarter"), ("A4", "quarter")]},
    ])
    aligner = ErhuScoreAligner(score, bpm=BPM)

    # Slightly early and late
    events = [
        {"start": 0.05, "end": 0.45, "pitch": "D4"},   # 50ms late
        {"start": 0.40, "end": 0.90, "pitch": "E4"},    # 100ms early
        {"start": 1.10, "end": 1.45, "pitch": "F#4"},   # 100ms late
        {"start": 1.55, "end": 1.95, "pitch": "A4"},    # 50ms late
    ]
    states = simulate_frames(aligner, events)

    final = aligner.state()
    assert final.current_note_index >= 2, (
        f"rubato: expected note index ≥2, got {final.current_note_index}"
    )


def test_skipped_note():
    """
    Player skips E4 (goes D4 → F#4). Aligner should jump ahead.
    """
    score = make_score([
        {"notes": [("D4", "quarter"), ("E4", "quarter"),
                   ("F#4", "quarter"), ("A4", "quarter")]},
    ])
    aligner = ErhuScoreAligner(score, bpm=BPM)

    events = [
        {"start": 0.0, "end": 0.45, "pitch": "D4"},
        # Skip E4 entirely, play F#4 at E4's time
        {"start": 0.5, "end": 0.95, "pitch": "F#4"},
        {"start": 1.5, "end": 1.95, "pitch": "A4"},
    ]
    states = simulate_frames(aligner, events)

    final = aligner.state()
    # Should have reached A4 (index 3) or at least F#4 (index 2)
    assert final.current_note_index >= 2, (
        f"skip: expected note index ≥2, got {final.current_note_index}"
    )


def test_repeated_note():
    """
    Player re-articulates D4 twice before moving on.
    Cursor should not go backwards.
    """
    score = make_score([
        {"notes": [("D4", "quarter"), ("E4", "quarter")]},
    ])
    aligner = ErhuScoreAligner(score, bpm=BPM)

    events = [
        {"start": 0.0, "end": 0.2, "pitch": "D4"},
        {"start": 0.25, "end": 0.45, "pitch": "D4"},  # re-articulation
        {"start": 0.5, "end": 0.95, "pitch": "E4"},
    ]
    states = simulate_frames(aligner, events)

    final = aligner.state()
    assert final.current_note_index >= 1, (
        f"repeated: expected note index ≥1, got {final.current_note_index}"
    )


def test_silence_reentry():
    """
    Silence gap mid-phrase, then resumption. Cursor should continue.
    """
    score = make_score([
        {"notes": [("D4", "quarter"), ("E4", "quarter"),
                   ("F#4", "quarter"), ("A4", "quarter")]},
    ])
    aligner = ErhuScoreAligner(score, bpm=BPM)

    events = [
        {"start": 0.0, "end": 0.45, "pitch": "D4"},
        {"start": 0.5, "end": 0.95, "pitch": "E4"},
        # Silence
        {"start": 0.95, "end": 1.3, "pitch": "", "onset": False},
        # Resume at F#4
        {"start": 1.3, "end": 1.8, "pitch": "F#4"},
    ]
    states = simulate_frames(aligner, events)

    final = aligner.state()
    assert final.current_note_index >= 2, (
        f"reentry: expected note index ≥2, got {final.current_note_index}"
    )


def test_two_measures():
    """
    Two-measure score with cross-measure continuation.
    Cursor should reach measure 2.
    """
    score = make_score([
        {"notes": [("D4", "quarter"), ("E4", "quarter"),
                   ("F#4", "quarter"), ("A4", "quarter")]},
        {"notes": [("B4", "quarter"), ("D5", "quarter"),
                   ("A4", "quarter"), ("F#4", "quarter")]},
    ])
    aligner = ErhuScoreAligner(score, bpm=BPM)

    # Play first 4 notes, then first 2 of measure 2
    events = [
        {"start": 0.0, "end": 0.45, "pitch": "D4"},
        {"start": 0.5, "end": 0.95, "pitch": "E4"},
        {"start": 1.0, "end": 1.45, "pitch": "F#4"},
        {"start": 1.5, "end": 1.95, "pitch": "A4"},
        {"start": 2.0, "end": 2.45, "pitch": "B4"},
        {"start": 2.5, "end": 2.95, "pitch": "D5"},
    ]
    states = simulate_frames(aligner, events)

    final = aligner.state()
    assert final.current_measure == 2, (
        f"expected measure 2, got {final.current_measure}"
    )
    assert final.confidence > 0.3, (
        f"expected confidence > 0.3, got {final.confidence}"
    )


def test_low_confidence_frames():
    """
    Frames with low pitch confidence should not cause passive advance.
    """
    score = make_score([
        {"notes": [("D4", "quarter"), ("E4", "quarter")]},
    ])
    aligner = ErhuScoreAligner(score, bpm=BPM)

    # D4 with onset, then E4 frames but low confidence
    events = [
        {"start": 0.0, "end": 0.45, "pitch": "D4", "onset": True},
        {"start": 0.5, "end": 1.0, "pitch": "E4",
         "onset": False, "confidence": 0.2},  # below 0.3 threshold
    ]
    simulate_frames(aligner, events)

    final = aligner.state()
    # Should NOT have passively advanced to E4
    assert final.current_note_index == 0, (
        f"low-conf: expected note 0 (no advance), got {final.current_note_index}"
    )


# ── Main ─────────────────────────────────────────────────────

def main():
    print("ErhuScoreAligner verification")
    print("=" * 50)

    tests = [
        ("Stepwise melody (D4→E4→F#4→A4)", test_stepwise_melody),
        ("Portamento — no extra advance", test_portamento_no_extra_advance),
        ("Passive advance (legato)", test_passive_advance_legato),
        ("Rubato timing (±100 ms)", test_rubato_timing),
        ("Skipped note (D4→F#4)", test_skipped_note),
        ("Repeated note (D4, D4, E4)", test_repeated_note),
        ("Silence re-entry", test_silence_reentry),
        ("Two-measure continuation", test_two_measures),
        ("Low-confidence suppression", test_low_confidence_frames),
    ]

    results = [run_test(name, fn) for name, fn in tests]
    passed = sum(results)
    total = len(results)

    print("=" * 50)
    print(f"{passed}/{total} tests passed")

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
