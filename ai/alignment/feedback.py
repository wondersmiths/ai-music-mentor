"""
Practice plan generator — turns raw performance issues into an
encouraging, structured practice plan in JSON.

Takes an AnalysisResult and the practice BPM, identifies priority
areas, and produces measure-specific drills with tempo and repetition
suggestions. Tone: supportive music teacher.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

from ai.alignment.analyzer import AnalysisResult, Issue, IssueType, Severity


# ── Output structures ───────────────────────────────────────

@dataclass
class MeasureDrill:
    """Practice instructions for a single measure."""

    measure: int
    priority: str          # "high" | "medium" | "low"
    issue_summary: str     # what went wrong, teacher-friendly
    suggested_tempo: int   # BPM to practice at
    repetitions: int       # how many times to repeat
    tip: str               # specific advice


@dataclass
class PracticePlan:
    """Complete structured practice plan."""

    summary: str                  # overall encouragement + assessment
    accuracy_pct: int
    rhythm_pct: int
    priority_measures: list[int]  # measures to focus on, in order
    drills: list[MeasureDrill]
    warmup: str                   # suggested warmup
    closing: str                  # closing encouragement

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "accuracy_pct": self.accuracy_pct,
            "rhythm_pct": self.rhythm_pct,
            "priority_measures": self.priority_measures,
            "drills": [
                {
                    "measure": d.measure,
                    "priority": d.priority,
                    "issue_summary": d.issue_summary,
                    "suggested_tempo": d.suggested_tempo,
                    "repetitions": d.repetitions,
                    "tip": d.tip,
                }
                for d in self.drills
            ],
            "warmup": self.warmup,
            "closing": self.closing,
        }


# ── Generator ───────────────────────────────────────────────

def generate_plan(
    result: AnalysisResult,
    practice_bpm: float = 120.0,
    total_measures: Optional[int] = None,
) -> PracticePlan:
    """
    Generate a practice plan from an analysis result.

    Parameters
    ----------
    result         : output of analyze()
    practice_bpm   : the BPM the student was playing at
    total_measures : total measures in the score (for context).
                     If None, inferred from issues.
    """
    accuracy_pct = round(result.accuracy * 100)
    rhythm_pct = round(result.rhythm_score * 100)

    # Group issues by measure
    by_measure: dict[int, list[Issue]] = defaultdict(list)
    for issue in result.issues:
        if issue.type == IssueType.EXTRA_NOTE:
            continue  # don't drill extra notes
        by_measure[issue.measure].append(issue)

    # Score each measure by severity weight
    measure_scores: dict[int, float] = {}
    for measure, issues in by_measure.items():
        score = 0.0
        for issue in issues:
            if issue.severity == Severity.ERROR:
                score += 3.0
            elif issue.severity == Severity.WARNING:
                score += 1.0
        measure_scores[measure] = score

    # Sort measures by severity (worst first)
    ranked = sorted(measure_scores.keys(), key=lambda m: -measure_scores[m])

    # Build drills for problematic measures
    drills: list[MeasureDrill] = []
    for measure in ranked:
        issues = by_measure[measure]
        severity_score = measure_scores[measure]

        priority = _priority(severity_score)
        tempo = _suggest_tempo(practice_bpm, priority)
        reps = _suggest_reps(priority)
        summary = _summarize_issues(issues)
        tip = _generate_tip(issues, practice_bpm)

        drills.append(MeasureDrill(
            measure=measure,
            priority=priority,
            issue_summary=summary,
            suggested_tempo=tempo,
            repetitions=reps,
            tip=tip,
        ))

    # Overall summary
    summary = _overall_summary(accuracy_pct, rhythm_pct, len(ranked), result.total_notes)
    warmup = _warmup_suggestion(result, practice_bpm)
    closing = _closing_message(accuracy_pct, rhythm_pct)

    return PracticePlan(
        summary=summary,
        accuracy_pct=accuracy_pct,
        rhythm_pct=rhythm_pct,
        priority_measures=ranked,
        drills=drills,
        warmup=warmup,
        closing=closing,
    )


# ── Helpers ─────────────────────────────────────────────────

def _priority(severity_score: float) -> str:
    if severity_score >= 4.0:
        return "high"
    if severity_score >= 2.0:
        return "medium"
    return "low"


def _suggest_tempo(practice_bpm: float, priority: str) -> int:
    """Slow down proportionally to the difficulty."""
    factors = {"high": 0.50, "medium": 0.70, "low": 0.85}
    return max(40, round(practice_bpm * factors[priority]))


def _suggest_reps(priority: str) -> int:
    return {"high": 8, "medium": 5, "low": 3}[priority]


def _summarize_issues(issues: list[Issue]) -> str:
    """One-line summary of what went wrong in a measure."""
    types = {i.type for i in issues}
    parts: list[str] = []

    if IssueType.MISSED_NOTE in types:
        missed = [i for i in issues if i.type == IssueType.MISSED_NOTE]
        pitches = ", ".join(i.expected_pitch for i in missed)
        parts.append(f"missed {_pluralize(len(missed), 'note')}: {pitches}")

    if IssueType.WRONG_PITCH in types:
        wrong = [i for i in issues if i.type == IssueType.WRONG_PITCH]
        descs = [f"{i.expected_pitch} played as {i.actual_pitch}" for i in wrong]
        noun = "pitch" if len(wrong) == 1 else "pitches"
        parts.append(f"wrong {len(wrong)} {noun}: {'; '.join(descs)}")

    if IssueType.RHYTHM_DEVIATION in types:
        rhythms = [i for i in issues if i.type == IssueType.RHYTHM_DEVIATION]
        parts.append(f"rhythm {_pluralize(len(rhythms), 'issue')}")

    return "; ".join(parts) if parts else "minor issues"


def _generate_tip(issues: list[Issue], bpm: float) -> str:
    """Context-specific practice advice."""
    types = {i.type for i in issues}

    if IssueType.MISSED_NOTE in types and IssueType.RHYTHM_DEVIATION in types:
        return (
            "This measure needs the most attention. Play each note slowly and "
            "deliberately, counting out loud. Add one note at a time until "
            "you can play the full measure smoothly."
        )

    if IssueType.MISSED_NOTE in types:
        missed = [i for i in issues if i.type == IssueType.MISSED_NOTE]
        pitches = " and ".join(i.expected_pitch for i in missed[:2])
        return (
            f"Focus on the fingering for {pitches}. Isolate just the tricky "
            f"spot and repeat it slowly until it feels natural, then play "
            f"the full measure."
        )

    if IssueType.WRONG_PITCH in types:
        wrong = [i for i in issues if i.type == IssueType.WRONG_PITCH]
        if any(i.severity == Severity.ERROR for i in wrong):
            return (
                "Double-check the notes in your sheet music. Play this "
                "measure very slowly, listening carefully to each pitch. "
                "Sing the melody first if that helps."
            )
        return (
            "You're very close! The pitch is just slightly off — check your "
            "intonation or fingering. Playing slowly with a tuner can help "
            "lock in the correct pitches."
        )

    if IssueType.RHYTHM_DEVIATION in types:
        lates = [i for i in issues if i.type == IssueType.RHYTHM_DEVIATION
                 and i.detail and "late" in i.detail]
        earlys = [i for i in issues if i.type == IssueType.RHYTHM_DEVIATION
                  and i.detail and "early" in i.detail]
        if lates and not earlys:
            return (
                "You're dragging a bit here. Try practicing with a metronome "
                "and really lock in to the click. Subdivide the beat mentally."
            )
        if earlys and not lates:
            return (
                "You're rushing this section. Take a breath, relax, and let "
                "the metronome guide you. It often helps to tap your foot."
            )
        return (
            "The rhythm is a bit uneven here. Practice with a metronome at "
            "a slower tempo until the timing feels steady, then gradually "
            "speed up."
        )

    return "Keep practicing this measure — you're almost there!"


def _overall_summary(accuracy: int, rhythm: int, problem_count: int, total: int) -> str:
    if accuracy >= 95 and rhythm >= 95:
        return (
            f"Excellent work! You nailed {accuracy}% of the notes with "
            f"{rhythm}% rhythm accuracy. Just a few small details to polish."
        )
    if accuracy >= 80 and rhythm >= 80:
        measures_word = "measure" if problem_count == 1 else "measures"
        return (
            f"Good job! You hit {accuracy}% of the notes and your rhythm "
            f"scored {rhythm}%. Let's tighten up {problem_count} "
            f"{measures_word} to make it even better."
        )
    if accuracy >= 60:
        measures_word = "measure" if problem_count == 1 else "measures"
        return (
            f"Nice effort — {accuracy}% note accuracy and {rhythm}% rhythm. "
            f"There are {problem_count} {measures_word} "
            f"that need some focused practice. You'll get there!"
        )
    return (
        f"This is a challenging piece! You got {accuracy}% of the notes "
        f"and {rhythm}% rhythm. Don't worry — let's break it down into "
        f"small sections and build it up step by step."
    )


def _warmup_suggestion(result: AnalysisResult, bpm: float) -> str:
    has_pitch_issues = any(
        i.type == IssueType.WRONG_PITCH for i in result.issues
    )
    has_rhythm_issues = any(
        i.type == IssueType.RHYTHM_DEVIATION for i in result.issues
    )

    if has_pitch_issues and has_rhythm_issues:
        return (
            f"Start with a slow scale or arpeggio at {max(40, round(bpm * 0.4))} BPM "
            f"to warm up your fingers and ears. Then tap the rhythm of the "
            f"tricky measures on your knee before playing them."
        )
    if has_pitch_issues:
        return (
            f"Warm up with a chromatic scale at {max(40, round(bpm * 0.5))} BPM, "
            f"listening carefully to each note. This will sharpen your "
            f"intonation for the practice session."
        )
    if has_rhythm_issues:
        return (
            f"Set your metronome to {max(40, round(bpm * 0.5))} BPM and clap "
            f"the rhythm of the piece before playing. This separates the "
            f"rhythm challenge from the notes."
        )
    return (
        f"Do a quick warm-up scale at {max(40, round(bpm * 0.5))} BPM to "
        f"get your fingers ready."
    )


def _closing_message(accuracy: int, rhythm: int) -> str:
    if accuracy >= 90 and rhythm >= 90:
        return (
            "You're really close to performance-ready. A few more focused "
            "repetitions and you'll have it down solid. Great work!"
        )
    if accuracy >= 70:
        return (
            "You've got a solid foundation. Focus on the priority measures "
            "in this plan, and you'll hear a big difference in your next "
            "run-through. Keep it up!"
        )
    return (
        "Remember — every musician starts by practicing slowly. Be patient "
        "with yourself, celebrate the small wins, and trust the process. "
        "You're making progress!"
    )


def _pluralize(n: int, word: str) -> str:
    return f"{n} {word}{'s' if n != 1 else ''}"
