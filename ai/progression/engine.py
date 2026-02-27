"""
P1: Progression Engine.

Rule-based skill progression that examines a user's SkillProgress records
and recommends the next exercise type, difficulty notes, and focus areas.

Progression rules:
- If any skill area < 60: recommend that area's primary exercise
- If all skills 60–80: recommend the weakest area
- If all skills > 80: recommend melody (most demanding) or advance difficulty
- Ties broken by exercise_count (prefer less-practiced areas)
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SkillSnapshot:
    """A snapshot of one skill area for progression decisions."""
    skill_area: str     # pitch, stability, slide, rhythm
    score: float        # 0–100 (EMA)
    exercise_count: int


@dataclass
class ProgressionRecommendation:
    """Output of the progression engine."""
    recommended_exercise: str       # long_tone, scale, melody, rhythm_drill
    focus_areas: list[str]          # e.g. ["stability", "pitch"]
    difficulty: str                 # beginner, intermediate, advanced
    message: str                    # human-friendly recommendation
    skill_summary: dict[str, float] = field(default_factory=dict)


# ── Mapping: skill area → best exercise for improvement ──

SKILL_TO_EXERCISE = {
    "stability": "long_tone",
    "pitch": "scale",
    "rhythm": "rhythm_drill",
    "slide": "scale",   # scales with slides
}

# ── Difficulty thresholds ──────────────────────────────────

BEGINNER_CEILING = 60.0
INTERMEDIATE_CEILING = 80.0


def recommend(
    skills: list[SkillSnapshot],
    total_sessions: int = 0,
) -> ProgressionRecommendation:
    """
    Given a user's current skill scores, recommend the next exercise.

    Args:
        skills: list of SkillSnapshot (from SkillProgress table)
        total_sessions: total training sessions completed

    Returns:
        ProgressionRecommendation with exercise type, focus, difficulty, message.
    """
    if not skills:
        return _first_time_recommendation(total_sessions)

    skill_map = {s.skill_area: s for s in skills}
    scores = {s.skill_area: s.score for s in skills}
    skill_summary = dict(scores)

    # Sort by score ascending, then by exercise_count ascending (prefer less practiced)
    sorted_skills = sorted(skills, key=lambda s: (s.score, s.exercise_count))

    weakest = sorted_skills[0]
    strongest = sorted_skills[-1]

    # ── Determine difficulty tier ──────────────────────────
    avg_score = sum(s.score for s in skills) / len(skills)

    if avg_score < BEGINNER_CEILING:
        difficulty = "beginner"
    elif avg_score < INTERMEDIATE_CEILING:
        difficulty = "intermediate"
    else:
        difficulty = "advanced"

    # ── Find weak areas (below 60) ─────────────────────────
    weak_areas = [s for s in sorted_skills if s.score < BEGINNER_CEILING]

    if weak_areas:
        # Focus on the weakest area
        focus = weak_areas[0]
        exercise = SKILL_TO_EXERCISE.get(focus.skill_area, "long_tone")
        focus_areas = [s.skill_area for s in weak_areas[:2]]

        message = (
            f"Your {focus.skill_area} needs attention (score: {focus.score:.0f}/100). "
            f"Practice {_exercise_name(exercise)} to strengthen it."
        )
        return ProgressionRecommendation(
            recommended_exercise=exercise,
            focus_areas=focus_areas,
            difficulty=difficulty,
            message=message,
            skill_summary=skill_summary,
        )

    # ── All skills 60–80: work on weakest ──────────────────
    mid_areas = [s for s in sorted_skills if s.score < INTERMEDIATE_CEILING]

    if mid_areas:
        focus = mid_areas[0]
        exercise = SKILL_TO_EXERCISE.get(focus.skill_area, "scale")
        focus_areas = [s.skill_area for s in mid_areas[:2]]

        message = (
            f"Good progress! Focus on {focus.skill_area} (score: {focus.score:.0f}/100) "
            f"to reach the next level. Try {_exercise_name(exercise)}."
        )
        return ProgressionRecommendation(
            recommended_exercise=exercise,
            focus_areas=focus_areas,
            difficulty=difficulty,
            message=message,
            skill_summary=skill_summary,
        )

    # ── All skills > 80: advanced practice ─────────────────
    exercise = "melody"
    focus_areas = [weakest.skill_area]

    message = (
        "Excellent skills across the board! "
        "Challenge yourself with melody practice to maintain your edge."
    )
    return ProgressionRecommendation(
        recommended_exercise=exercise,
        focus_areas=focus_areas,
        difficulty="advanced",
        message=message,
        skill_summary=skill_summary,
    )


def _first_time_recommendation(total_sessions: int) -> ProgressionRecommendation:
    """Recommendation for users with no skill data yet."""
    if total_sessions == 0:
        return ProgressionRecommendation(
            recommended_exercise="long_tone",
            focus_areas=["stability", "pitch"],
            difficulty="beginner",
            message="Welcome! Start with long tone exercises to build a stable foundation.",
            skill_summary={},
        )

    return ProgressionRecommendation(
        recommended_exercise="long_tone",
        focus_areas=["stability", "pitch"],
        difficulty="beginner",
        message="Try a long tone exercise to start building your skill profile.",
        skill_summary={},
    )


def _exercise_name(exercise_type: str) -> str:
    """Human-friendly exercise name."""
    names = {
        "long_tone": "long tone exercises",
        "scale": "scale practice",
        "melody": "melody practice",
        "rhythm_drill": "rhythm drills",
    }
    return names.get(exercise_type, exercise_type)
