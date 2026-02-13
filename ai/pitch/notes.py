"""
Frequency-to-note conversion using twelve-tone equal temperament (A4 = 440 Hz).
"""

import math

# Semitone names (sharps). Index 0 = C.
_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# A4 reference
_A4_HZ = 440.0
_A4_MIDI = 69


def freq_to_midi(freq: float) -> float:
    """Convert frequency in Hz to a (fractional) MIDI note number."""
    if freq <= 0:
        return 0.0
    return _A4_MIDI + 12.0 * math.log2(freq / _A4_HZ)


def midi_to_note_name(midi: int) -> str:
    """Convert an integer MIDI note number to a note name like 'C4' or 'F#5'."""
    octave = (midi // 12) - 1
    name = _NAMES[midi % 12]
    return f"{name}{octave}"


def freq_to_note(freq: float) -> tuple[str, int]:
    """
    Convert a frequency to the nearest note name and cents deviation.

    Returns
    -------
    (note_name, cents_off)
        note_name : e.g. "A4", "C#5"
        cents_off : deviation from the ideal pitch (-50 to +50)
    """
    if freq <= 0:
        return ("", 0)

    midi_float = freq_to_midi(freq)
    midi_rounded = round(midi_float)
    cents = round((midi_float - midi_rounded) * 100)

    return midi_to_note_name(midi_rounded), cents
