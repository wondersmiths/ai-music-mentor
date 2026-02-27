"""
ARCH1: Multi-instrument profiles.

Each instrument profile defines pitch detection parameters, frequency range,
default tuning, and evaluation weight presets. The system selects a profile
based on the instrument_type field in sessions/requests.

Adding a new instrument:
1. Create an InstrumentProfile entry in INSTRUMENT_PROFILES below.
2. (Optional) Write a specialized pitch tracker in ai/pitch/ if needed.
3. The generic pitch tracker will use the profile's freq_min/freq_max/yin_threshold.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class InstrumentProfile:
    """Configuration profile for a specific instrument."""

    # Identity
    name: str               # e.g. "erhu"
    display_name: str       # e.g. "Erhu (二胡)"
    family: str             # "bowed_string", "plucked_string", "wind", "voice"

    # Pitch detection parameters
    freq_min: float         # Hz — lowest expected pitch
    freq_max: float         # Hz — highest expected pitch
    yin_threshold: float    # YIN CMND threshold (lower = stricter)
    pre_emphasis: float     # highpass filter coefficient (0 = off, 0.97 typical for bowed)

    # Tuning
    default_tonic: str      # e.g. "D" for erhu (D4-based)
    base_octave: int        # default octave for jianpu notation
    a4_frequency: float = 440.0  # A4 reference (tunable for historical pitch)

    # Smoothing
    median_window: int = 5
    ema_alpha: float = 0.35
    silence_threshold_db: float = -50.0
    confidence_floor: float = 0.65

    # Evaluation weights by exercise type
    eval_weights: dict = field(default_factory=lambda: {
        "long_tone": {"pitch": 0.3, "stability": 0.5, "slide": 0.0, "rhythm": 0.2},
        "scale":     {"pitch": 0.4, "stability": 0.2, "slide": 0.1, "rhythm": 0.3},
        "melody":    {"pitch": 0.35, "stability": 0.15, "slide": 0.15, "rhythm": 0.35},
    })


# ── Built-in profiles ─────────────────────────────────────────

ERHU_PROFILE = InstrumentProfile(
    name="erhu",
    display_name="Erhu (二胡)",
    family="bowed_string",
    freq_min=260.0,      # just below D4
    freq_max=2400.0,     # just above D7
    yin_threshold=0.12,  # stricter for bow noise rejection
    pre_emphasis=0.97,   # strong highpass for bow rumble
    default_tonic="D",
    base_octave=4,
    median_window=5,
    ema_alpha=0.35,
    silence_threshold_db=-50.0,
    confidence_floor=0.65,
)

VIOLIN_PROFILE = InstrumentProfile(
    name="violin",
    display_name="Violin",
    family="bowed_string",
    freq_min=196.0,      # G3
    freq_max=4200.0,     # ~C8 (harmonics)
    yin_threshold=0.12,
    pre_emphasis=0.97,
    default_tonic="G",
    base_octave=3,
    median_window=5,
    ema_alpha=0.3,
    silence_threshold_db=-50.0,
    confidence_floor=0.6,
)

FLUTE_PROFILE = InstrumentProfile(
    name="flute",
    display_name="Flute (笛子)",
    family="wind",
    freq_min=262.0,      # C4
    freq_max=4200.0,     # C8
    yin_threshold=0.15,  # less strict — cleaner signal
    pre_emphasis=0.5,    # less pre-emphasis for wind
    default_tonic="C",
    base_octave=4,
    median_window=3,
    ema_alpha=0.4,
    silence_threshold_db=-45.0,
    confidence_floor=0.7,
)

VOICE_PROFILE = InstrumentProfile(
    name="voice",
    display_name="Voice",
    family="voice",
    freq_min=80.0,       # E2 (bass)
    freq_max=1100.0,     # C6 (soprano)
    yin_threshold=0.15,
    pre_emphasis=0.0,    # no pre-emphasis for voice
    default_tonic="C",
    base_octave=4,
    median_window=5,
    ema_alpha=0.3,
    silence_threshold_db=-45.0,
    confidence_floor=0.6,
)

GUZHENG_PROFILE = InstrumentProfile(
    name="guzheng",
    display_name="Guzheng (古筝)",
    family="plucked_string",
    freq_min=65.0,       # C2
    freq_max=3200.0,     # ~G#7
    yin_threshold=0.15,
    pre_emphasis=0.5,
    default_tonic="D",
    base_octave=3,
    median_window=3,
    ema_alpha=0.4,
    silence_threshold_db=-50.0,
    confidence_floor=0.6,
    eval_weights={
        "long_tone": {"pitch": 0.4, "stability": 0.3, "slide": 0.1, "rhythm": 0.2},
        "scale":     {"pitch": 0.4, "stability": 0.15, "slide": 0.15, "rhythm": 0.3},
        "melody":    {"pitch": 0.35, "stability": 0.1, "slide": 0.2, "rhythm": 0.35},
    },
)

# ── Profile registry ──────────────────────────────────────────

INSTRUMENT_PROFILES: dict[str, InstrumentProfile] = {
    "erhu": ERHU_PROFILE,
    "violin": VIOLIN_PROFILE,
    "flute": FLUTE_PROFILE,
    "voice": VOICE_PROFILE,
    "guzheng": GUZHENG_PROFILE,
}


def get_profile(instrument: str) -> InstrumentProfile:
    """
    Get the instrument profile by name. Falls back to erhu if unknown.

    Args:
        instrument: instrument name (case-insensitive)

    Returns:
        InstrumentProfile for the requested instrument
    """
    return INSTRUMENT_PROFILES.get(instrument.lower(), ERHU_PROFILE)


def list_instruments() -> list[str]:
    """Return list of supported instrument names."""
    return list(INSTRUMENT_PROFILES.keys())
