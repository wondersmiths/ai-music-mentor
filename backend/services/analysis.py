"""
Audio analysis service — pitch detection, onset detection, tempo estimation.

Processes a WAV audio chunk and returns structured analysis results.
This is the core DSP pipeline exposed by the /api/analyze endpoint.
"""

from __future__ import annotations

import logging

import numpy as np

from ai.pitch.detector import detect_pitch
from ai.pitch.onset import OnsetDetector
from backend.config import settings
from backend.dsp.audio import AudioValidationError, load_wav_bytes, resample
from backend.schemas.analysis import (
    AnalysisResponse,
    OnsetEvent,
    PitchEvent,
    TempoResult,
)

logger = logging.getLogger(__name__)


def analyze_audio(wav_bytes: bytes) -> AnalysisResponse:
    """
    Full analysis pipeline: load WAV → resample → detect pitch/onsets → return results.

    Raises AudioValidationError for bad input.
    """
    samples, sr = load_wav_bytes(wav_bytes)

    # Resample to target rate
    sr_target = settings.TARGET_SAMPLE_RATE
    if sr != sr_target:
        samples = resample(samples, sr, sr_target)
        sr = sr_target

    frame_size = settings.FRAME_SIZE
    duration_s = len(samples) / sr

    # ── Pitch detection (frame by frame) ─────────────────────
    pitches: list[PitchEvent] = []
    onset_det = OnsetDetector(sample_rate=sr, frame_size=frame_size)

    for pos in range(0, len(samples) - frame_size + 1, frame_size):
        frame = samples[pos : pos + frame_size]
        timestamp = pos / sr

        # Pitch
        pr = detect_pitch(frame, sample_rate=sr)
        if pr.note:
            pitches.append(PitchEvent(
                time=round(timestamp, 4),
                note=pr.note,
                frequency=round(pr.frequency, 2),
                cents_off=pr.cents_off,
                confidence=round(pr.confidence, 3),
            ))

        # Onset
        onset_det.feed(frame)

    # ── Collect onsets and tempo ──────────────────────────────
    onset_result = onset_det.result()
    onsets = [
        OnsetEvent(time=round(o.time, 4), strength=round(o.strength, 6))
        for o in onset_result.onsets
    ]
    tempo = TempoResult(
        bpm=onset_result.tempo.bpm,
        confidence=onset_result.tempo.confidence,
    )

    logger.info(
        "Analysis: %.2fs audio → %d pitches, %d onsets, %.1f BPM",
        duration_s, len(pitches), len(onsets), tempo.bpm,
    )

    return AnalysisResponse(
        pitches=pitches,
        onsets=onsets,
        tempo=tempo,
        duration_s=round(duration_s, 3),
    )
