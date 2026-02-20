"""
Shared fixtures for the test harness.

Provides score builders, audio synthesizers, and pipeline runners
that test cases can compose freely.
"""

from __future__ import annotations

import numpy as np
import pytest

from ai.omr.models import Measure, Note, ScoreResult


# ── Score builders ──────────────────────────────────────────

# Pitch name → frequency (Hz), covering the range we test
FREQ_TABLE = {
    "C3": 130.81, "D3": 146.83, "E3": 164.81, "F3": 174.61,
    "G3": 196.00, "A3": 220.00, "B3": 246.94,
    "C4": 261.63, "C#4": 277.18, "D4": 293.66, "D#4": 311.13,
    "E4": 329.63, "F4": 349.23, "F#4": 369.99, "G4": 392.00,
    "G#4": 415.30, "A4": 440.00, "A#4": 466.16, "B4": 493.88,
    "C5": 523.25, "D5": 587.33, "E5": 659.25,
}

DURATION_BEATS = {
    "whole": 4.0, "half": 2.0, "quarter": 1.0,
    "eighth": 0.5, "sixteenth": 0.25,
}


def make_score(measures_data: list[dict]) -> ScoreResult:
    """
    Build a ScoreResult from a compact description.

    measures_data: list of dicts, each with:
        "time_sig": "4/4" (optional, default "4/4")
        "notes": [("C4", "quarter"), ("D4", "half"), ...]
    """
    measures = []
    for i, md in enumerate(measures_data):
        ts = md.get("time_sig", "4/4")
        beat = 1.0
        notes = []
        for pitch, dur in md["notes"]:
            notes.append(Note(pitch=pitch, duration=dur, beat=beat))
            beat += DURATION_BEATS.get(dur, 1.0)
        measures.append(Measure(number=i + 1, time_signature=ts, notes=notes))

    return ScoreResult(
        title="Test Score", confidence=1.0, is_mock=False, measures=measures,
    )


# ── Audio synthesizer ──────────────────────────────────────

def synthesize(
    score: ScoreResult,
    bpm: float = 120.0,
    sample_rate: int = 16000,
    amplitude: float = 0.5,
    modifications: dict | None = None,
) -> np.ndarray:
    """
    Synthesize audio from a score for testing.

    modifications: optional dict to alter the performance:
        "skip": [("measure", "pitch")]  — omit these notes
        "wrong": {("measure", "pitch"): "new_pitch"}  — play wrong note
        "timing": {("measure", "pitch"): offset_beats}  — shift onset
    """
    mods = modifications or {}
    skip_set = set(tuple(s) for s in mods.get("skip", []))
    wrong_map = {tuple(k): v for k, v in mods.get("wrong", {}).items()}
    timing_map = {tuple(k): v for k, v in mods.get("timing", {}).items()}

    spb = 60.0 / bpm  # seconds per beat
    beat_offset = 0.0  # cumulative beats before current measure

    # Calculate total duration
    total_beats = 0.0
    for measure in score.measures:
        num, _ = measure.time_signature.split("/")
        total_beats += float(num)
    total_samples = int((total_beats * spb + 1.0) * sample_rate)
    audio = np.zeros(total_samples, dtype=np.float32)

    for measure in score.measures:
        num_beats = float(measure.time_signature.split("/")[0])
        for note in measure.notes:
            key = (measure.number, note.pitch)

            # Skip?
            if key in skip_set:
                continue

            # Wrong pitch?
            pitch = wrong_map.get(key, note.pitch)

            # Timing offset?
            timing_offset = timing_map.get(key, 0.0)

            # Compute onset in seconds
            abs_beat = beat_offset + note.beat - 1.0 + timing_offset
            onset_s = abs_beat * spb
            if onset_s < 0:
                onset_s = 0

            # Note duration in seconds (70% of beat duration for separation)
            dur_beats = DURATION_BEATS.get(note.duration, 1.0)
            dur_s = dur_beats * spb * 0.7

            freq = FREQ_TABLE.get(pitch, 440.0)

            # Synthesize with attack/decay envelope
            n_samples = int(dur_s * sample_rate)
            t = np.arange(n_samples) / sample_rate
            envelope = np.minimum(t / 0.005, 1.0) * np.exp(-t * 2.5)
            wave = amplitude * np.sin(2 * np.pi * freq * t) * envelope

            start = int(onset_s * sample_rate)
            end = min(start + n_samples, total_samples)
            if start < total_samples and end > start:
                audio[start:end] += wave[: end - start].astype(np.float32)

        beat_offset += num_beats

    return audio


# ── Pipeline runner ─────────────────────────────────────────

def run_pipeline(
    score: ScoreResult,
    audio: np.ndarray,
    bpm: float = 120.0,
    sample_rate: int = 16000,
    frame_size: int = 2048,
):
    """
    Run the full detection → alignment → analysis → feedback pipeline.

    Returns a dict with all intermediate and final results.
    """
    from ai.alignment.analyzer import DetectedNote, analyze
    from ai.alignment.feedback import generate_plan
    from ai.alignment.follower import ScoreFollower
    from ai.pitch.detector import detect_pitch
    from ai.pitch.onset import OnsetDetector

    # 1. Onset + pitch detection
    onset_det = OnsetDetector(sample_rate=sample_rate, frame_size=frame_size)
    detected_notes = []

    for pos in range(0, len(audio) - frame_size, frame_size):
        frame = audio[pos : pos + frame_size]
        onset = onset_det.feed(frame)
        if onset:
            pr = detect_pitch(frame, sample_rate=sample_rate)
            if pr.note:
                detected_notes.append(
                    DetectedNote(pitch=pr.note, time=onset.time, confidence=pr.confidence)
                )

    onset_result = onset_det.result()

    # 2. Score follower (streaming alignment)
    follower = ScoreFollower(score)
    follower_states = []
    for dn in detected_notes:
        match = follower.feed(dn.pitch, dn.time, bpm_hint=onset_result.tempo.bpm)
        follower_states.append(match)

    # 3. Batch analysis
    analysis = analyze(score, detected_notes, bpm=bpm)

    # 4. Practice plan
    plan = generate_plan(analysis, practice_bpm=bpm)

    return {
        "detected_notes": detected_notes,
        "onset_result": onset_result,
        "follower_states": follower_states,
        "follower_final": follower.state(),
        "analysis": analysis,
        "plan": plan,
    }


# ── Reusable fixtures ──────────────────────────────────────

@pytest.fixture
def c_major_scale_score():
    """Two-measure C major scale: C4-D4-E4-F4 | G4-A4-B4-C5"""
    return make_score([
        {"notes": [("C4", "quarter"), ("D4", "quarter"),
                   ("E4", "quarter"), ("F4", "quarter")]},
        {"notes": [("G4", "quarter"), ("A4", "quarter"),
                   ("B4", "quarter"), ("C5", "quarter")]},
    ])
