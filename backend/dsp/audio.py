"""
Audio loading and validation.

Accepts WAV bytes from the frontend, validates duration and format,
resamples to the target sample rate, and returns a numpy array.
"""

from __future__ import annotations

import io
import logging
import wave

import numpy as np

from backend.config import settings

logger = logging.getLogger(__name__)


class AudioValidationError(Exception):
    """Raised when uploaded audio fails validation."""


def load_wav_bytes(data: bytes) -> tuple[np.ndarray, int]:
    """
    Parse WAV bytes into a float64 numpy array + sample rate.
    Validates duration limits.
    """
    try:
        with wave.open(io.BytesIO(data), "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            sr = wf.getframerate()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)
    except Exception as e:
        raise AudioValidationError(f"Invalid WAV file: {e}")

    if sr > settings.MAX_AUDIO_SAMPLE_RATE:
        raise AudioValidationError(
            f"Sample rate {sr} Hz exceeds maximum {settings.MAX_AUDIO_SAMPLE_RATE} Hz"
        )

    duration_s = n_frames / sr
    if duration_s > settings.MAX_AUDIO_SECONDS:
        raise AudioValidationError(
            f"Audio duration {duration_s:.1f}s exceeds maximum "
            f"{settings.MAX_AUDIO_SECONDS}s"
        )
    if n_frames == 0:
        raise AudioValidationError("Audio file is empty")

    # Convert raw bytes to float64 array
    if sampwidth == 2:
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
        samples /= 32768.0
    elif sampwidth == 4:
        samples = np.frombuffer(raw, dtype=np.int32).astype(np.float64)
        samples /= 2147483648.0
    elif sampwidth == 1:
        samples = np.frombuffer(raw, dtype=np.uint8).astype(np.float64)
        samples = (samples - 128.0) / 128.0
    else:
        raise AudioValidationError(f"Unsupported sample width: {sampwidth} bytes")

    # Mix to mono if stereo
    if n_channels == 2:
        samples = (samples[0::2] + samples[1::2]) / 2.0
    elif n_channels > 2:
        raise AudioValidationError(f"Unsupported channel count: {n_channels}")

    logger.info(
        "Loaded audio: %.2fs, %d Hz, %d samples",
        duration_s, sr, len(samples),
    )

    return samples, sr


def resample(samples: np.ndarray, sr_from: int, sr_to: int) -> np.ndarray:
    """Simple linear interpolation resampler."""
    if sr_from == sr_to:
        return samples
    ratio = sr_to / sr_from
    n_out = int(len(samples) * ratio)
    indices = np.arange(n_out) / ratio
    lo = np.floor(indices).astype(int)
    lo = np.clip(lo, 0, len(samples) - 2)
    frac = indices - lo
    return samples[lo] * (1 - frac) + samples[lo + 1] * frac
