"""
Jianpu (numbered musical notation) OCR + parser.

Detects jianpu vs western notation, extracts text via Tesseract OCR,
parses tokens (notes, rests, barlines), converts scale degrees to
western pitches, and builds Measure objects.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np

from ai.omr.models import Measure, Note

logger = logging.getLogger(__name__)

# ── Pitch conversion tables ─────────────────────────────────

DEGREE_INTERVALS = {1: 0, 2: 2, 3: 4, 4: 5, 5: 7, 6: 9, 7: 11}
TONIC_MIDI = {
    "C": 60, "D": 62, "E": 64, "F": 65, "G": 67, "A": 69, "B": 71,
}

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


# ── Data structures ──────────────────────────────────────────

@dataclass
class JianpuToken:
    kind: str  # "note", "rest", "barline", "extend"
    degree: int = 0  # 1-7 for notes
    octave_shift: int = 0  # +1 = dot above, -1 = dot below
    dotted: bool = False  # rhythmic dot (1.5x duration)
    underlines: int = 0  # 0=quarter, 1=eighth, 2=sixteenth


@dataclass
class JianpuParseResult:
    key_sig: str = "1=C"
    time_sig: str = "4/4"
    tokens: List[JianpuToken] = field(default_factory=list)


# ── Detection ────────────────────────────────────────────────

def detect_notation_type(binary: np.ndarray, staff_lines: list[int]) -> str:
    """Decide if the image contains western or jianpu notation."""
    if len(staff_lines) >= 5:
        return "western"

    # No staff lines found — try OCR to check for jianpu patterns
    text = extract_jianpu_text(binary)
    if not text:
        return "western"

    # Look for digits 1-7 (note characters) and "1=" key signature
    digit_count = sum(1 for ch in text if ch in "1234567")
    has_key_sig = bool(re.search(r"1\s*=\s*[A-G]", text))

    if has_key_sig or digit_count >= 5:
        return "jianpu"
    return "western"


# ── OCR extraction ───────────────────────────────────────────

def extract_jianpu_text(binary: np.ndarray) -> str:
    """Run Tesseract OCR on the binary image with digit-focused config."""
    try:
        import pytesseract
    except ImportError:
        logger.warning("pytesseract not installed — skipping jianpu OCR")
        return ""

    try:
        # PSM 6 = uniform block of text; whitelist ASCII + common jianpu chars
        config = (
            "--psm 6 "
            "-c tessedit_char_whitelist="
            "0123456789.-|/=()#bABCDEFG "
        )
        text: str = pytesseract.image_to_string(binary, config=config)
        logger.debug("Jianpu OCR raw text: %r", text[:200])
        return text.strip()
    except Exception:
        logger.warning("Tesseract OCR failed", exc_info=True)
        return ""


# ── Text parser ──────────────────────────────────────────────

def parse_jianpu_text(text: str) -> JianpuParseResult:
    """Parse OCR text into structured jianpu tokens."""
    result = JianpuParseResult()

    # Extract key signature: "1=F", "1 = D", "1=#F"
    ks_match = re.search(r"1\s*=\s*([#b]?[A-G])", text)
    if ks_match:
        result.key_sig = f"1={ks_match.group(1)}"

    # Extract time signature: "2/4", "4/4", "3/4"
    ts_match = re.search(r"([234])\s*/\s*([48])", text)
    if ts_match:
        result.time_sig = f"{ts_match.group(1)}/{ts_match.group(2)}"

    # Tokenize the main body
    # Remove key/time sig from text to avoid re-parsing
    body = text
    if ks_match:
        body = body[:ks_match.start()] + body[ks_match.end():]
    if ts_match:
        # Re-search in modified body
        ts_match2 = re.search(r"[234]\s*/\s*[48]", body)
        if ts_match2:
            body = body[:ts_match2.start()] + body[ts_match2.end():]

    i = 0
    while i < len(body):
        ch = body[i]

        if ch in "1234567":
            degree = int(ch)
            octave_shift = 0
            dotted = False

            # Look ahead for octave dots and rhythmic dot
            j = i + 1
            while j < len(body):
                if body[j] == ".":
                    # Heuristic: dot right after digit = rhythmic dot first time,
                    # then octave up on subsequent dots.
                    # In practice, a single "." after a digit is usually rhythmic.
                    if not dotted:
                        dotted = True
                    else:
                        octave_shift += 1
                    j += 1
                elif body[j] == "\u0307":  # combining dot above
                    octave_shift += 1
                    j += 1
                elif body[j] == "\u0323":  # combining dot below
                    octave_shift -= 1
                    j += 1
                else:
                    break

            result.tokens.append(JianpuToken(
                kind="note",
                degree=degree,
                octave_shift=octave_shift,
                dotted=dotted,
                underlines=0,  # default to quarter; underlines detected from image
            ))
            i = j

        elif ch == "0":
            result.tokens.append(JianpuToken(kind="rest"))
            i += 1

        elif ch == "-":
            result.tokens.append(JianpuToken(kind="extend"))
            i += 1

        elif ch == "|":
            result.tokens.append(JianpuToken(kind="barline"))
            i += 1

        else:
            # Skip whitespace and unrecognized chars
            i += 1

    return result


# ── Pitch conversion ─────────────────────────────────────────

def jianpu_to_pitch(degree: int, octave_shift: int, tonic: str) -> tuple[str, str]:
    """
    Convert jianpu degree + octave to (western_pitch, jianpu_label).

    Example: degree=6, octave_shift=0, tonic="F" → ("D5", "6")
    """
    # Clean tonic (handle sharps/flats in key sig like "#F")
    tonic_clean = tonic[-1] if len(tonic) > 1 else tonic
    base_midi = TONIC_MIDI.get(tonic_clean, 60)

    # Apply accidental from key sig
    if len(tonic) > 1 and tonic[0] == "#":
        base_midi += 1
    elif len(tonic) > 1 and tonic[0] == "b":
        base_midi -= 1

    interval = DEGREE_INTERVALS.get(degree, 0)
    midi = base_midi + interval + (octave_shift * 12)

    # Convert MIDI to pitch name
    note_name = NOTE_NAMES[midi % 12]
    octave = (midi // 12) - 1
    western = f"{note_name}{octave}"

    # Build jianpu display label with Unicode combining dots
    label = str(degree)
    if octave_shift > 0:
        label += "\u0307" * octave_shift  # dots above
    elif octave_shift < 0:
        label += "\u0323" * abs(octave_shift)  # dots below

    return western, label


# ── Measure builder ──────────────────────────────────────────

def build_jianpu_measures(
    tokens: list[JianpuToken],
    key_sig: str,
    time_sig: str,
) -> list[Measure]:
    """Group tokens into measures by barlines and assign beat positions."""
    # Parse tonic from key sig (e.g. "1=F" → "F")
    ks_match = re.match(r"1=([#b]?[A-G])", key_sig)
    tonic = ks_match.group(1) if ks_match else "C"

    # Parse beats per measure
    ts_parts = time_sig.split("/")
    beats_per_measure = int(ts_parts[0]) if len(ts_parts) == 2 else 4

    measures: list[Measure] = []
    current_notes: list[Note] = []
    current_beat = 1.0
    measure_num = 1

    for token in tokens:
        if token.kind == "barline":
            if current_notes:
                measures.append(Measure(
                    number=measure_num,
                    time_signature=time_sig,
                    notes=current_notes,
                ))
                measure_num += 1
                current_notes = []
                current_beat = 1.0
            continue

        if token.kind == "note":
            # Determine duration from underlines
            if token.underlines == 0:
                dur_name = "quarter"
                dur_beats = 1.0
            elif token.underlines == 1:
                dur_name = "eighth"
                dur_beats = 0.5
            else:
                dur_name = "sixteenth"
                dur_beats = 0.25

            if token.dotted:
                dur_beats *= 1.5

            western, jianpu_label = jianpu_to_pitch(
                token.degree, token.octave_shift, tonic
            )
            current_notes.append(Note(
                pitch=western,
                duration=dur_name,
                beat=current_beat,
                jianpu=jianpu_label,
            ))
            current_beat += dur_beats

        elif token.kind == "rest":
            # Rest = advance by one beat (quarter)
            current_beat += 1.0

        elif token.kind == "extend":
            # Extend previous note by one beat (dash = held note)
            current_beat += 1.0

    # Flush remaining notes as final measure
    if current_notes:
        measures.append(Measure(
            number=measure_num,
            time_signature=time_sig,
            notes=current_notes,
        ))

    return measures


# ── High-level entry point ───────────────────────────────────

def recognize_jianpu(binary: np.ndarray) -> tuple[list[Measure], str, str, float]:
    """
    Full jianpu recognition: OCR → parse → build measures.

    Returns (measures, key_sig, time_sig, confidence).
    """
    text = extract_jianpu_text(binary)
    if not text:
        return [], "1=C", "4/4", 0.0

    parsed = parse_jianpu_text(text)

    # Estimate confidence based on how many note tokens we found
    note_count = sum(1 for t in parsed.tokens if t.kind == "note")
    confidence = min(0.9, note_count / 50.0) if note_count > 0 else 0.0

    measures = build_jianpu_measures(
        parsed.tokens, parsed.key_sig, parsed.time_sig
    )

    logger.info(
        "Jianpu OCR: key=%s, time=%s, notes=%d, measures=%d, confidence=%.2f",
        parsed.key_sig, parsed.time_sig, note_count, len(measures), confidence,
    )

    return measures, parsed.key_sig, parsed.time_sig, confidence
