"""Claude Vision-based score recognition.

Sends the score image to Claude Sonnet's vision API and parses
the structured JSON response into a ScoreResult.
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

from ai.omr.models import Measure, Note, ScoreResult

logger = logging.getLogger(__name__)

_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}

_PROMPT = """\
You are an expert music score reader. Analyze this music score image and return \
a JSON object with the following structure. Return ONLY valid JSON, no markdown \
fences, no explanation.

{
  "title": "<title if visible, else 'Uploaded Score'>",
  "notation_type": "western" or "jianpu",
  "key_signature": "<e.g. 'C major', '1=F' for jianpu, or null>",
  "time_signature": "<e.g. '4/4'>",
  "measures": [
    {
      "number": 1,
      "time_signature": "4/4",
      "notes": [
        {
          "pitch": "<scientific pitch, e.g. 'C4', 'D5', 'rest'>",
          "duration": "<whole|half|quarter|eighth|sixteenth>",
          "beat": 1.0,
          "jianpu": "<jianpu label if applicable, e.g. '1', '6̇', else null>"
        }
      ]
    }
  ]
}

Rules:
- Use scientific pitch notation (C4 = middle C).
- For rests, set pitch to "rest".
- beat is the beat position within the measure (1-based, can be fractional).
- duration must be one of: whole, half, quarter, eighth, sixteenth.
- If you cannot determine a value, use reasonable defaults (e.g. "4/4" for time).
- Number measures sequentially starting at 1.
- For jianpu notation, still provide the scientific pitch AND the jianpu label.
"""


def recognize_with_vision(file_path: str) -> ScoreResult | None:
    """Attempt to recognize a score using Claude Vision.

    Returns a ScoreResult on success, or None on any failure
    (missing API key, bad response, network error, etc.).
    """
    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic package not installed; skipping vision OMR")
        return None

    from backend.config import settings

    api_key = settings.ANTHROPIC_API_KEY
    if not api_key:
        return None

    try:
        path = Path(file_path)
        suffix = path.suffix.lower()
        media_type = _MEDIA_TYPES.get(suffix)
        if media_type is None:
            logger.warning("Unsupported file type for vision OMR: %s", suffix)
            return None

        image_data = base64.standard_b64encode(path.read_bytes()).decode("ascii")

        # Determine the correct source type for the API
        if media_type == "application/pdf":
            source_block = {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": image_data,
                },
            }
        else:
            source_block = {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": image_data,
                },
            }

        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        source_block,
                        {"type": "text", "text": _PROMPT},
                    ],
                }
            ],
        )

        raw_text = message.content[0].text.strip()

        # Strip markdown fences if the model included them despite instructions
        if raw_text.startswith("```"):
            # Remove first line (```json or ```) and last line (```)
            lines = raw_text.split("\n")
            raw_text = "\n".join(lines[1:-1]).strip()

        data = json.loads(raw_text)

        return _parse_vision_response(data)

    except Exception:
        logger.exception("Vision OMR failed; falling back to CV pipeline")
        return None


def _parse_vision_response(data: dict) -> ScoreResult:
    """Convert the raw JSON dict from Claude into a ScoreResult."""
    measures = []
    default_ts = data.get("time_signature", "4/4")

    for m in data.get("measures", []):
        notes = []
        for n in m.get("notes", []):
            notes.append(
                Note(
                    pitch=n.get("pitch", "C4"),
                    duration=n.get("duration", "quarter"),
                    beat=float(n.get("beat", 1.0)),
                    jianpu=n.get("jianpu"),
                )
            )
        measures.append(
            Measure(
                number=int(m.get("number", len(measures) + 1)),
                time_signature=m.get("time_signature", default_ts),
                notes=notes,
            )
        )

    return ScoreResult(
        title=data.get("title", "Uploaded Score"),
        confidence=0.95,
        is_mock=False,
        measures=measures,
        notation_type=data.get("notation_type", "western"),
        key_signature=data.get("key_signature"),
    )
