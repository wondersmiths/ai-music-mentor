"""
Jianpu (numbered musical notation) OCR + parser.

Detects jianpu vs western notation, extracts text via Tesseract OCR,
parses tokens (notes, rests, barlines), converts scale degrees to
western pitches, and builds Measure objects.

Duration inference: In printed jianpu, notes beamed together (underlined)
appear as digit groups without spaces.  The group size determines duration:
  - 1 digit alone  → quarter note  (1 beat)
  - 2-digit group  → eighth notes  (0.5 beat each)
  - 4-digit group  → sixteenth notes (0.25 beat each)
  - 3-digit group  → eighth-note triplet (0.33 beat each, approximated)
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


# ── Detection + recognition (single OCR pass) ───────────────

def try_jianpu(binary: np.ndarray, staff_lines: list) -> "ScoreResult | None":
    """Try to recognize jianpu notation; return ScoreResult or None.

    Runs OCR once — uses the result for both detection and parsing.
    Returns None if the image is not jianpu (caller falls through to
    western pipeline).
    """
    from ai.omr.models import ScoreResult  # local to avoid circular

    if len(staff_lines) >= 5:
        return None

    text = extract_jianpu_text(binary)
    if not text:
        return None

    # Quick check: enough digits 1-7 or key-sig pattern?
    digit_count = sum(1 for ch in text if ch in "1234567")
    has_key_sig = bool(re.search(r"1\s*=\s*[A-G]", text))
    if not has_key_sig and digit_count < 5:
        return None

    # It's jianpu — parse the already-extracted text
    parsed = parse_jianpu_text(text)
    note_count = sum(1 for t in parsed.tokens if t.kind == "note")
    confidence = min(0.9, note_count / 50.0) if note_count > 0 else 0.0

    measures = build_jianpu_measures(
        parsed.tokens, parsed.key_sig, parsed.time_sig
    )

    if not measures:
        return None

    logger.info(
        "Jianpu OCR: key=%s, time=%s, notes=%d, measures=%d, confidence=%.2f",
        parsed.key_sig, parsed.time_sig, note_count, len(measures), confidence,
    )

    return ScoreResult(
        title="Uploaded Score",
        confidence=confidence,
        is_mock=False,
        measures=measures,
        notation_type="jianpu",
        key_signature=parsed.key_sig,
    )


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
        logger.debug("Jianpu OCR raw text: %r", text[:500])
        return text.strip()
    except Exception:
        logger.warning("Tesseract OCR failed", exc_info=True)
        return ""


# ── Text cleaning ────────────────────────────────────────────

def _clean_ocr_text(text: str) -> str:
    """Remove non-musical noise from OCR output."""
    # Remove rehearsal / measure numbers in parentheses: (60), (70), (90)
    text = re.sub(r"\(\d+\)", "", text)
    # Remove dynamic markings
    text = re.sub(r"\b(pp|p|mp|mf|f|ff|sfz|cresc|dim|rit)\b", " ", text, flags=re.IGNORECASE)
    # Remove Chinese characters (performance directions like 拉奏, 拨奏, 渐强)
    text = re.sub(r"[\u4e00-\u9fff]+", " ", text)
    # Remove "Re" / "re" (common OCR artifact from repeat signs)
    text = re.sub(r"\bRe\b", " ", text)
    # Remove stray letters that aren't part of key sig (keep only near "1=")
    # But first protect key signature pattern
    ks_match = re.search(r"1\s*=\s*[#b]?[A-G]", text)
    ks_text = ""
    if ks_match:
        ks_text = ks_match.group(0)
    # Remove isolated letters not near digits
    text = re.sub(r"(?<![0-9=])[A-G](?![0-9=])", " ", text)
    # Re-insert key sig if we removed part of it
    if ks_text and ks_text not in text:
        text = ks_text + " " + text
    # Collapse multiple spaces
    text = re.sub(r"  +", " ", text)
    return text.strip()


# ── Text parser ──────────────────────────────────────────────

def parse_jianpu_text(text: str) -> JianpuParseResult:
    """Parse OCR text into structured jianpu tokens.

    Key improvement: infer note duration from digit grouping.
    Consecutive digits without space separation = beamed (shorter) notes.
    """
    result = JianpuParseResult()

    # Extract key signature: "1=F", "1 = D", "1=#F"
    ks_match = re.search(r"1\s*=\s*([#b]?[A-G])", text)
    if ks_match:
        result.key_sig = "1=%s" % ks_match.group(1)

    # Extract time signature: "2/4", "4/4", "3/4"
    ts_match = re.search(r"([234])\s*/\s*([48])", text)
    if ts_match:
        result.time_sig = "%s/%s" % (ts_match.group(1), ts_match.group(2))

    # Clean the text body
    body = _clean_ocr_text(text)

    # Remove key/time sig from body to avoid re-parsing digits
    if ks_match:
        body = re.sub(r"1\s*=\s*[#b]?[A-G]", " ", body, count=1)
    if ts_match:
        body = re.sub(r"[234]\s*/\s*[48]", " ", body, count=1)

    # Process line by line (OCR preserves line structure)
    for line in body.split("\n"):
        line = line.strip()
        if not line:
            continue
        _parse_line(line, result.tokens)

    return result


def _parse_line(line: str, tokens: list) -> None:
    """Parse a single line of cleaned OCR text into tokens.

    Splits on barlines first, then on spaces within each segment
    to identify digit groups.
    """
    # Split on barline characters
    segments = re.split(r"\|", line)

    for seg_idx, segment in enumerate(segments):
        # Add barline between segments (not before first)
        if seg_idx > 0:
            tokens.append(JianpuToken(kind="barline"))

        segment = segment.strip()
        if not segment:
            continue

        # Split segment into space-separated groups
        groups = segment.split()

        for group in groups:
            _parse_group(group, tokens)


def _parse_group(group: str, tokens: list) -> None:
    """Parse a space-separated group into tokens.

    A group like "3235" = 4 beamed notes (sixteenths).
    A group like "35" = 2 beamed notes (eighths).
    A group like "6." = dotted quarter.
    A group like "6" = quarter note.
    A group like "0" = rest.
    A group like "-" = extend.
    """
    # Strip non-musical chars
    group = group.strip()
    if not group:
        return

    # Pure extend dashes
    if re.fullmatch(r"-+", group):
        for _ in group:
            tokens.append(JianpuToken(kind="extend"))
        return

    # Check for dotted note: single digit followed by dot, e.g. "6."
    dot_match = re.fullmatch(r"([0-7])\.+", group)
    if dot_match:
        d = int(dot_match.group(1))
        if d == 0:
            tokens.append(JianpuToken(kind="rest"))
        else:
            tokens.append(JianpuToken(kind="note", degree=d, dotted=True, underlines=0))
        return

    # Extract only digits and zeros from the group
    digits = [ch for ch in group if ch in "01234567"]

    if not digits:
        return

    # Determine underlines (duration) from group size
    n = len(digits)
    if n == 1:
        underlines = 0  # quarter
    elif n == 2:
        underlines = 1  # eighth
    elif n == 3:
        underlines = 1  # treat triplet as eighths (approximate)
    elif n >= 4:
        underlines = 2  # sixteenth
    else:
        underlines = 0

    for ch in digits:
        d = int(ch)
        if d == 0:
            tokens.append(JianpuToken(kind="rest", underlines=underlines))
        elif 1 <= d <= 7:
            tokens.append(JianpuToken(kind="note", degree=d, underlines=underlines))
        # Skip 8, 9 (OCR noise)


# ── Pitch conversion ─────────────────────────────────────────

def jianpu_to_pitch(degree: int, octave_shift: int, tonic: str) -> Tuple[str, str]:
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
    western = "%s%d" % (note_name, octave)

    # Build jianpu display label with Unicode combining dots
    label = str(degree)
    if octave_shift > 0:
        label += "\u0307" * octave_shift  # dots above
    elif octave_shift < 0:
        label += "\u0323" * abs(octave_shift)  # dots below

    return western, label


# ── Measure builder ──────────────────────────────────────────

def build_jianpu_measures(
    tokens: list,
    key_sig: str,
    time_sig: str,
) -> List[Measure]:
    """Group tokens into measures by barlines and assign beat positions."""
    # Parse tonic from key sig (e.g. "1=F" → "F")
    ks_match = re.match(r"1=([#b]?[A-G])", key_sig)
    tonic = ks_match.group(1) if ks_match else "C"

    # Parse beats per measure
    ts_parts = time_sig.split("/")
    beats_per_measure = int(ts_parts[0]) if len(ts_parts) == 2 else 4

    measures = []  # type: List[Measure]
    current_notes = []  # type: List[Note]
    current_beat = 1.0
    measure_num = 1

    def _flush():
        nonlocal measure_num, current_notes, current_beat
        if current_notes:
            measures.append(Measure(
                number=measure_num,
                time_signature=time_sig,
                notes=current_notes,
            ))
            measure_num += 1
            current_notes = []
            current_beat = 1.0

    for token in tokens:
        if token.kind == "barline":
            _flush()
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
                beat=round(current_beat, 4),
                jianpu=jianpu_label,
            ))
            current_beat += dur_beats

        elif token.kind == "rest":
            # Rest duration matches the context underlines
            if token.underlines == 0:
                current_beat += 1.0
            elif token.underlines == 1:
                current_beat += 0.5
            else:
                current_beat += 0.25

        elif token.kind == "extend":
            # Extend previous note by one beat (dash = held note)
            current_beat += 1.0

    # Flush remaining notes as final measure
    _flush()

    return measures


