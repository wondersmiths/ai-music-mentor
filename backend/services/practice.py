"""
Practice session orchestration — manages in-memory sessions with
ErhuScoreAligner, ErhuOnsetDetector, and accumulated pitch data.

Each session flows: start → process frames → stop (analyze + plan).
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import dataclass, field

import numpy as np

from ai.alignment.analyzer import AnalysisResult, Issue, IssueType, Severity
from ai.alignment.erhu_analyzer import (
    ErhuAnalysisResult,
    ErhuIssueType,
    ErhuSeverity,
    PitchSample,
    erhu_analyze,
)
from ai.alignment.erhu_follower import (
    AlignmentState,
    ErhuScoreAligner,
    ScoreNote,
    _linearize_score,
)
from ai.alignment.feedback import generate_plan
from ai.omr.models import ScoreResult
from ai.pitch.detector import detect_pitch
from ai.pitch.erhu_onset import ErhuOnsetDetector
from ai.pitch.notes import freq_to_midi
from backend.config import settings
from backend.dsp.audio import load_wav_bytes, resample
from backend.schemas.practice import (
    DrillDetail,
    ErhuAnalysis,
    FrameAlignmentUpdate,
    FrameResponse,
    IssueDetail,
    PracticePlanResult,
    StartRequest,
    StartResponse,
    StopResponse,
)
from backend.schemas.analysis import OnsetEvent, PitchEvent

logger = logging.getLogger(__name__)

# ── Limits ───────────────────────────────────────────────────

SESSION_TTL_S = 600       # 10 minutes inactive
MAX_SESSIONS = 50


# ── Session dataclass ────────────────────────────────────────

@dataclass
class PracticeSession:
    session_id: str
    score: ScoreResult
    bpm: float
    aligner: ErhuScoreAligner
    onset_detector: ErhuOnsetDetector
    notes: list[ScoreNote]
    pitch_curve: list[PitchSample] = field(default_factory=list)
    onset_times: list[float] = field(default_factory=list)
    elapsed_s: float = 0.0
    last_active: float = field(default_factory=time.time)


# ── In-memory session store ──────────────────────────────────

_sessions: dict[str, PracticeSession] = {}


def _cleanup_expired() -> None:
    """Lazily remove sessions older than TTL."""
    now = time.time()
    expired = [
        sid for sid, sess in _sessions.items()
        if now - sess.last_active > SESSION_TTL_S
    ]
    for sid in expired:
        del _sessions[sid]
        logger.info("Expired session %s", sid)


# ── Public API ───────────────────────────────────────────────

def start_session(req: StartRequest) -> StartResponse:
    """Create a new practice session with aligner + onset detector."""
    _cleanup_expired()

    if len(_sessions) >= MAX_SESSIONS:
        raise RuntimeError(
            f"Too many active sessions ({MAX_SESSIONS}). Try again later."
        )

    # Convert backend schema measures to ai/omr model measures via dicts
    # (they have identical fields but are different Pydantic classes)
    score = ScoreResult(
        title=req.title,
        confidence=1.0,
        is_mock=False,
        measures=[m.model_dump() for m in req.measures],
    )

    aligner = ErhuScoreAligner(score, bpm=req.bpm)
    onset_det = ErhuOnsetDetector(
        sample_rate=settings.TARGET_SAMPLE_RATE,
        frame_size=settings.FRAME_SIZE,
    )
    notes = _linearize_score(score, req.bpm)

    session_id = uuid.uuid4().hex[:12]
    _sessions[session_id] = PracticeSession(
        session_id=session_id,
        score=score,
        bpm=req.bpm,
        aligner=aligner,
        onset_detector=onset_det,
        notes=notes,
    )

    total_notes = len(notes)
    total_measures = len(req.measures)

    logger.info(
        "Started session %s: %d notes, %d measures, %.0f BPM",
        session_id, total_notes, total_measures, req.bpm,
    )

    return StartResponse(
        session_id=session_id,
        total_notes=total_notes,
        total_measures=total_measures,
    )


def process_frame(session_id: str, wav_bytes: bytes) -> FrameResponse:
    """Process a WAV audio chunk through the practice pipeline."""
    _cleanup_expired()

    sess = _sessions.get(session_id)
    if sess is None:
        raise KeyError(f"Session '{session_id}' not found or expired")

    sess.last_active = time.time()

    # Load and resample
    samples, sr = load_wav_bytes(wav_bytes)
    sr_target = settings.TARGET_SAMPLE_RATE
    if sr != sr_target:
        samples = resample(samples, sr, sr_target)
        sr = sr_target

    frame_size = settings.FRAME_SIZE
    chunk_duration = len(samples) / sr

    pitches: list[PitchEvent] = []
    onsets: list[OnsetEvent] = []

    for pos in range(0, len(samples) - frame_size + 1, frame_size):
        frame = samples[pos: pos + frame_size]
        timestamp = sess.elapsed_s + pos / sr

        # Pitch detection (separate from onset detector's internal tracker)
        pr = detect_pitch(frame, sample_rate=sr)

        if pr.note:
            pitches.append(PitchEvent(
                time=round(timestamp, 4),
                note=pr.note,
                frequency=round(pr.frequency, 2),
                cents_off=pr.cents_off,
                confidence=round(pr.confidence, 3),
            ))

        # Feed pitch to aligner
        midi_val = freq_to_midi(pr.frequency) if pr.frequency > 0 else 0.0
        sess.aligner.on_frame(timestamp, midi_val, pr.confidence)

        # Accumulate pitch curve for post-analysis
        sess.pitch_curve.append(PitchSample(
            time=timestamp,
            midi=midi_val,
            confidence=pr.confidence,
        ))

        # Onset detection — detector maintains its own persistent frame
        # counter, so onset.time is already session-global
        onset = sess.onset_detector.feed(frame)
        if onset:
            sess.aligner.on_onset(onset.time, onset.confidence)
            sess.onset_times.append(onset.time)
            onsets.append(OnsetEvent(
                time=round(onset.time, 4),
                strength=round(onset.confidence, 3),
            ))

    sess.elapsed_s += chunk_duration

    # Build alignment update
    state = sess.aligner.state()
    is_complete = state.current_note_index >= len(sess.notes) - 1 and state.confidence > 0.3

    # Look up the beat from the linearized notes
    if sess.notes and state.current_note_index < len(sess.notes):
        current_beat = sess.notes[state.current_note_index].beat
    else:
        current_beat = 1.0

    alignment = FrameAlignmentUpdate(
        current_measure=state.current_measure,
        current_beat=current_beat,
        confidence=state.confidence,
        is_complete=is_complete,
    )

    return FrameResponse(
        alignment=alignment,
        pitches=pitches,
        onsets=onsets,
        elapsed_s=round(sess.elapsed_s, 3),
    )


def stop_session(session_id: str) -> StopResponse:
    """Stop a session, run analysis + plan generation, and clean up."""
    sess = _sessions.pop(session_id, None)
    if sess is None:
        raise KeyError(f"Session '{session_id}' not found or expired")

    logger.info(
        "Stopping session %s: %.1fs audio, %d pitch samples, %d onsets",
        session_id, sess.elapsed_s, len(sess.pitch_curve), len(sess.onset_times),
    )

    # Run Erhu-aware analysis
    erhu_result = erhu_analyze(
        sess.score,
        sess.pitch_curve,
        sess.onset_times,
        bpm=sess.bpm,
    )

    # Adapt ErhuAnalysisResult → generic AnalysisResult for feedback.generate_plan
    generic_issues = _adapt_issues(erhu_result)
    generic_result = AnalysisResult(
        issues=generic_issues,
        total_notes=erhu_result.total_notes,
        notes_hit=erhu_result.notes_reached,
        accuracy=erhu_result.accuracy,
        rhythm_score=erhu_result.phrase_rhythm_score,
    )

    # Generate practice plan
    plan = generate_plan(
        generic_result,
        practice_bpm=sess.bpm,
        total_measures=len(sess.score.measures),
    )

    # Build response
    erhu_analysis = ErhuAnalysis(
        issues=[
            IssueDetail(
                type=i.type.value,
                severity=i.severity.value,
                measure=i.measure,
                detail=i.detail,
            )
            for i in erhu_result.issues
        ],
        accuracy=erhu_result.accuracy,
        rhythm_score=erhu_result.phrase_rhythm_score,
    )

    practice_plan = PracticePlanResult(
        summary=plan.summary,
        accuracy_pct=plan.accuracy_pct,
        rhythm_pct=plan.rhythm_pct,
        priority_measures=plan.priority_measures,
        drills=[
            DrillDetail(
                measure=d.measure,
                priority=d.priority,
                issue_summary=d.issue_summary,
                suggested_tempo=d.suggested_tempo,
                repetitions=d.repetitions,
                tip=d.tip,
            )
            for d in plan.drills
        ],
        warmup=plan.warmup,
        closing=plan.closing,
    )

    return StopResponse(
        erhu_analysis=erhu_analysis,
        practice_plan=practice_plan,
    )


# ── Helpers ──────────────────────────────────────────────────

_ISSUE_TYPE_MAP = {
    ErhuIssueType.MISSED_NOTE: IssueType.MISSED_NOTE,
    ErhuIssueType.INTONATION: IssueType.WRONG_PITCH,
    ErhuIssueType.RHYTHM: IssueType.RHYTHM_DEVIATION,
}

_SEVERITY_MAP = {
    ErhuSeverity.INFO: Severity.INFO,
    ErhuSeverity.WARNING: Severity.WARNING,
    ErhuSeverity.ERROR: Severity.ERROR,
}


_PITCH_RE = re.compile(r":\s+([A-G]#?\d)")


def _extract_pitch(detail: str) -> str:
    """Extract pitch name (e.g. 'D4') from ErhuIssue detail string."""
    m = _PITCH_RE.search(detail)
    return m.group(1) if m else ""


def _adapt_issues(erhu_result: ErhuAnalysisResult) -> list[Issue]:
    """Convert ErhuIssue list to generic Issue list for feedback generator."""
    issues: list[Issue] = []
    for ei in erhu_result.issues:
        issue_type = _ISSUE_TYPE_MAP.get(ei.type, IssueType.MISSED_NOTE)
        severity = _SEVERITY_MAP.get(ei.severity, Severity.WARNING)
        pitch = _extract_pitch(ei.detail)
        issues.append(Issue(
            type=issue_type,
            severity=severity,
            measure=ei.measure,
            beat=0.0,
            expected_pitch=pitch,
            actual_pitch="",
            detail=ei.detail,
        ))
    return issues
