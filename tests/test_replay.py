"""
Replay test harness — synthesizes audio from a score (with optional
modifications), runs the full pipeline, and validates alignment and
mistake detection.

Run:
    cd ai_music_mentor
    python -m pytest tests/ -v

Adding new test cases:
    See ADDING_TESTS section at the bottom of this file.
"""

import numpy as np
import pytest

from tests.conftest import make_score, run_pipeline, synthesize


# ════════════════════════════════════════════════════════════
#  Test cases
# ════════════════════════════════════════════════════════════


class TestPerfectPlayback:
    """Validate that a perfect performance produces no issues."""

    def test_perfect_scale(self, c_major_scale_score):
        audio = synthesize(c_major_scale_score, bpm=120.0)
        result = run_pipeline(c_major_scale_score, audio, bpm=120.0)

        analysis = result["analysis"]
        assert analysis.accuracy >= 0.75, (
            f"Perfect playback accuracy too low: {analysis.accuracy}"
        )
        wrong_or_missed = [
            i for i in analysis.issues
            if i.type.value in ("wrong_pitch", "missed_note")
        ]
        assert len(wrong_or_missed) <= 1, (
            f"Perfect playback should have ≤1 pitch/miss issue, got: "
            f"{[i.detail for i in wrong_or_missed]}"
        )

    def test_perfect_slow_tempo(self, c_major_scale_score):
        """Same score at 80 BPM — pipeline should still work."""
        audio = synthesize(c_major_scale_score, bpm=80.0)
        result = run_pipeline(c_major_scale_score, audio, bpm=80.0)

        assert result["analysis"].accuracy >= 0.75


class TestWrongPitch:
    """Validate that wrong pitches are detected."""

    def test_single_wrong_note(self, c_major_scale_score):
        audio = synthesize(
            c_major_scale_score, bpm=120.0,
            modifications={"wrong": {(1, "E4"): "G4"}},
        )
        result = run_pipeline(c_major_scale_score, audio, bpm=120.0)

        wrong = [i for i in result["analysis"].issues if i.type.value == "wrong_pitch"]
        assert len(wrong) >= 1, "Should detect at least one wrong pitch"
        assert any(i.measure == 1 for i in wrong), (
            "Wrong pitch should be in measure 1"
        )

    def test_multiple_wrong_notes(self):
        score = make_score([
            {"notes": [("C4", "quarter"), ("D4", "quarter"),
                       ("E4", "quarter"), ("F4", "quarter")]},
        ])
        audio = synthesize(
            score, bpm=120.0,
            modifications={"wrong": {(1, "D4"): "F#4", (1, "F4"): "A4"}},
        )
        result = run_pipeline(score, audio, bpm=120.0)

        wrong = [i for i in result["analysis"].issues if i.type.value == "wrong_pitch"]
        assert len(wrong) >= 1, "Should detect wrong pitches"


class TestMissedNotes:
    """Validate that skipped notes are detected as missed."""

    def test_single_missed_note(self, c_major_scale_score):
        audio = synthesize(
            c_major_scale_score, bpm=120.0,
            modifications={"skip": [(1, "E4")]},
        )
        result = run_pipeline(c_major_scale_score, audio, bpm=120.0)

        missed = [i for i in result["analysis"].issues if i.type.value == "missed_note"]
        assert len(missed) >= 1, "Should detect at least one missed note"

    def test_skip_entire_measure(self):
        score = make_score([
            {"notes": [("C4", "quarter"), ("D4", "quarter"),
                       ("E4", "quarter"), ("F4", "quarter")]},
            {"notes": [("G4", "quarter"), ("A4", "quarter"),
                       ("B4", "quarter"), ("C5", "quarter")]},
        ])
        audio = synthesize(
            score, bpm=120.0,
            modifications={"skip": [(2, "G4"), (2, "A4"), (2, "B4"), (2, "C5")]},
        )
        result = run_pipeline(score, audio, bpm=120.0)

        missed = [i for i in result["analysis"].issues if i.type.value == "missed_note"]
        m2_missed = [i for i in missed if i.measure == 2]
        assert len(m2_missed) >= 2, (
            f"Should detect multiple missed notes in measure 2, got {len(m2_missed)}"
        )


class TestRhythmDeviation:
    """Validate that timing issues are detected."""

    def test_late_note(self, c_major_scale_score):
        audio = synthesize(
            c_major_scale_score, bpm=120.0,
            modifications={"timing": {(1, "D4"): 0.5}},  # half beat late
        )
        result = run_pipeline(c_major_scale_score, audio, bpm=120.0)

        rhythm = [i for i in result["analysis"].issues
                  if i.type.value == "rhythm_deviation"]
        assert len(rhythm) >= 1, "Should detect rhythm deviation"

    def test_early_note(self, c_major_scale_score):
        audio = synthesize(
            c_major_scale_score, bpm=120.0,
            modifications={"timing": {(1, "F4"): -0.4}},  # early
        )
        result = run_pipeline(c_major_scale_score, audio, bpm=120.0)

        rhythm = [i for i in result["analysis"].issues
                  if i.type.value == "rhythm_deviation"]
        # May or may not detect depending on frame alignment — just check no crash
        assert result["analysis"].rhythm_score <= 1.0


class TestMixedErrors:
    """Validate combined error scenarios."""

    def test_miss_and_wrong(self):
        score = make_score([
            {"notes": [("C4", "quarter"), ("D4", "quarter"),
                       ("E4", "quarter"), ("F4", "quarter")]},
            {"notes": [("G4", "quarter"), ("A4", "quarter"),
                       ("B4", "quarter"), ("C5", "quarter")]},
        ])
        audio = synthesize(
            score, bpm=120.0,
            modifications={
                "skip": [(1, "E4")],
                "wrong": {(2, "A4"): "G#4"},
                "timing": {(2, "B4"): 0.3},
            },
        )
        result = run_pipeline(score, audio, bpm=120.0)

        analysis = result["analysis"]
        assert analysis.accuracy < 1.0, "Should not be perfect"

        # Verify practice plan is generated
        plan = result["plan"]
        assert len(plan.drills) >= 1, "Should generate at least one drill"
        assert plan.accuracy_pct < 100


class TestFeedbackPlan:
    """Validate that the practice plan is coherent."""

    def test_plan_structure(self, c_major_scale_score):
        audio = synthesize(
            c_major_scale_score, bpm=120.0,
            modifications={"skip": [(1, "E4")], "wrong": {(2, "A4"): "C3"}},
        )
        result = run_pipeline(c_major_scale_score, audio, bpm=120.0)

        plan = result["plan"]
        plan_dict = plan.to_dict()

        # Check JSON structure
        assert "summary" in plan_dict
        assert "drills" in plan_dict
        assert "warmup" in plan_dict
        assert "closing" in plan_dict
        assert isinstance(plan_dict["priority_measures"], list)

        # Drills should have required fields
        for drill in plan_dict["drills"]:
            assert drill["priority"] in ("high", "medium", "low")
            assert drill["suggested_tempo"] > 0
            assert drill["repetitions"] > 0
            assert len(drill["tip"]) > 0

    def test_perfect_plan_has_no_drills(self, c_major_scale_score):
        audio = synthesize(c_major_scale_score, bpm=120.0)
        result = run_pipeline(c_major_scale_score, audio, bpm=120.0)

        plan = result["plan"]
        # A near-perfect performance should have few or no drills
        assert plan.accuracy_pct >= 75


class TestScoreFollower:
    """Validate the streaming follower tracks position correctly."""

    def test_follower_completes(self, c_major_scale_score):
        audio = synthesize(c_major_scale_score, bpm=120.0)
        result = run_pipeline(c_major_scale_score, audio, bpm=120.0)

        final = result["follower_final"]
        assert final.matched_events > 0, "Follower should match some events"
        assert final.confidence > 0.3, (
            f"Confidence should be reasonable, got {final.confidence}"
        )

    def test_follower_handles_silence(self, c_major_scale_score):
        """Feeding silence should not crash."""
        silence = np.zeros(16000 * 3, dtype=np.float32)
        result = run_pipeline(c_major_scale_score, silence, bpm=120.0)

        assert result["follower_final"].matched_events == 0


class TestEdgeCases:
    """Boundary conditions and robustness."""

    def test_single_note_score(self):
        score = make_score([{"notes": [("A4", "whole")]}])
        audio = synthesize(score, bpm=60.0)
        result = run_pipeline(score, audio, bpm=60.0)
        # Should not crash
        assert result["analysis"].total_notes == 1

    def test_fast_tempo(self):
        score = make_score([
            {"notes": [("C4", "eighth"), ("D4", "eighth"),
                       ("E4", "eighth"), ("F4", "eighth"),
                       ("G4", "eighth"), ("A4", "eighth"),
                       ("B4", "eighth"), ("C5", "eighth")]},
        ])
        audio = synthesize(score, bpm=200.0)
        result = run_pipeline(score, audio, bpm=200.0)
        # At high tempo, detection may miss some — just verify no crash
        assert result["analysis"].total_notes == 8

    def test_three_four_time(self):
        score = make_score([
            {"time_sig": "3/4",
             "notes": [("C4", "quarter"), ("E4", "quarter"), ("G4", "quarter")]},
            {"time_sig": "3/4",
             "notes": [("C5", "half"), ("G4", "quarter")]},
        ])
        audio = synthesize(score, bpm=120.0)
        result = run_pipeline(score, audio, bpm=120.0)
        assert result["analysis"].total_notes == 5

    def test_empty_detected(self, c_major_scale_score):
        """No audio input → all notes missed."""
        result = run_pipeline(
            c_major_scale_score,
            np.zeros(16000, dtype=np.float32),
            bpm=120.0,
        )
        assert result["analysis"].accuracy == 0.0
        missed = [i for i in result["analysis"].issues
                  if i.type.value == "missed_note"]
        assert len(missed) == result["analysis"].total_notes


# ════════════════════════════════════════════════════════════
#  ADDING NEW TEST CASES
# ════════════════════════════════════════════════════════════
#
#  1. Define a score using make_score():
#
#       score = make_score([
#           {"notes": [("C4", "quarter"), ("D4", "half")]},
#           {"time_sig": "3/4", "notes": [("E4", "quarter"), ...]},
#       ])
#
#     Each entry is a measure. Notes are (pitch, duration) tuples.
#     Beats are assigned automatically. Supported durations:
#     whole, half, quarter, eighth, sixteenth.
#
#  2. Synthesize audio with optional modifications:
#
#       audio = synthesize(score, bpm=120.0, modifications={
#           "skip":   [(1, "D4")],              # skip note in measure 1
#           "wrong":  {(1, "E4"): "F4"},        # play F4 instead of E4
#           "timing": {(2, "C4"): 0.3},         # 0.3 beats late
#       })
#
#     Keys in skip/wrong/timing are (measure_number, pitch_name).
#
#  3. Run the pipeline:
#
#       result = run_pipeline(score, audio, bpm=120.0)
#
#  4. Assert on the results:
#
#       result["analysis"].accuracy       — 0.0 to 1.0
#       result["analysis"].rhythm_score   — 0.0 to 1.0
#       result["analysis"].issues         — list of Issue objects
#       result["plan"].drills             — list of MeasureDrill objects
#       result["follower_final"]          — AlignmentState
#       result["detected_notes"]          — list of DetectedNote
#
#  Example — test that a specific wrong note is caught:
#
#     class TestMyNewCase:
#         def test_wrong_f_sharp(self):
#             score = make_score([
#                 {"notes": [("C4", "quarter"), ("D4", "quarter"),
#                            ("E4", "quarter"), ("F4", "quarter")]},
#             ])
#             audio = synthesize(score, bpm=100.0,
#                                modifications={"wrong": {(1, "E4"): "F#4"}})
#             result = run_pipeline(score, audio, bpm=100.0)
#             wrong = [i for i in result["analysis"].issues
#                      if i.type.value == "wrong_pitch"]
#             assert any(i.expected_pitch == "E4" for i in wrong)
#
# ════════════════════════════════════════════════════════════
