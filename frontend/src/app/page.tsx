"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import ScoreViewer, { Score } from "@/score/ScoreViewer";
import { CursorController } from "@/score/CursorController";
import { parseScore, parseScoreMulti, ApiError, StopResult } from "@/lib/api";
import { usePractice, PracticeMode } from "@/hooks/usePractice";

// 赛马 (Horse Racing) — 黄海怀 / 沈利群
// Jianpu: 1=F (F major), 2/4 time, ~130 BPM
// Pitch mapping: 1=F4 2=G4 3=A4 5=C5 6=D5 7=E5
const DEMO_SCORE: Score = {
  title: "赛马 (Horse Racing)",
  notation_type: "jianpu",
  key_signature: "1=F",
  measures: [
    // ── Opening theme: 6. 35 repeated ──
    { number: 1, time_signature: "2/4", notes: [
      { pitch: "D5", duration: "quarter", beat: 1, jianpu: "6" },
      { pitch: "A4", duration: "eighth", beat: 2, jianpu: "3" },
      { pitch: "C5", duration: "eighth", beat: 2.5, jianpu: "5" },
    ]},
    { number: 2, time_signature: "2/4", notes: [
      { pitch: "D5", duration: "quarter", beat: 1, jianpu: "6" },
      { pitch: "A4", duration: "eighth", beat: 2, jianpu: "3" },
      { pitch: "C5", duration: "eighth", beat: 2.5, jianpu: "5" },
    ]},
    { number: 3, time_signature: "2/4", notes: [
      { pitch: "D5", duration: "quarter", beat: 1, jianpu: "6" },
      { pitch: "A4", duration: "eighth", beat: 2, jianpu: "3" },
      { pitch: "C5", duration: "eighth", beat: 2.5, jianpu: "5" },
    ]},
    { number: 4, time_signature: "2/4", notes: [
      { pitch: "D5", duration: "quarter", beat: 1, jianpu: "6" },
      { pitch: "A4", duration: "eighth", beat: 2, jianpu: "3" },
      { pitch: "C5", duration: "eighth", beat: 2.5, jianpu: "5" },
    ]},
    // ── Running sixteenth figures: 0535 ──
    { number: 5, time_signature: "2/4", notes: [
      { pitch: "C5", duration: "sixteenth", beat: 1, jianpu: "5" },
      { pitch: "A4", duration: "sixteenth", beat: 1.25, jianpu: "3" },
      { pitch: "C5", duration: "sixteenth", beat: 1.5, jianpu: "5" },
      { pitch: "A4", duration: "sixteenth", beat: 1.75, jianpu: "3" },
      { pitch: "C5", duration: "sixteenth", beat: 2, jianpu: "5" },
      { pitch: "A4", duration: "sixteenth", beat: 2.25, jianpu: "3" },
      { pitch: "C5", duration: "sixteenth", beat: 2.5, jianpu: "5" },
      { pitch: "A4", duration: "sixteenth", beat: 2.75, jianpu: "3" },
    ]},
    { number: 6, time_signature: "2/4", notes: [
      { pitch: "C5", duration: "sixteenth", beat: 1, jianpu: "5" },
      { pitch: "A4", duration: "sixteenth", beat: 1.25, jianpu: "3" },
      { pitch: "C5", duration: "sixteenth", beat: 1.5, jianpu: "5" },
      { pitch: "A4", duration: "sixteenth", beat: 1.75, jianpu: "3" },
      { pitch: "C5", duration: "sixteenth", beat: 2, jianpu: "5" },
      { pitch: "A4", duration: "sixteenth", beat: 2.25, jianpu: "3" },
      { pitch: "C5", duration: "sixteenth", beat: 2.5, jianpu: "5" },
      { pitch: "A4", duration: "sixteenth", beat: 2.75, jianpu: "3" },
    ]},
    // ── 6 56 pattern ──
    { number: 7, time_signature: "2/4", notes: [
      { pitch: "D5", duration: "eighth", beat: 1, jianpu: "6" },
      { pitch: "C5", duration: "eighth", beat: 1.5, jianpu: "5" },
      { pitch: "D5", duration: "eighth", beat: 2, jianpu: "6" },
      { pitch: "C5", duration: "eighth", beat: 2.5, jianpu: "5" },
    ]},
    { number: 8, time_signature: "2/4", notes: [
      { pitch: "D5", duration: "eighth", beat: 1, jianpu: "6" },
      { pitch: "C5", duration: "eighth", beat: 1.5, jianpu: "5" },
      { pitch: "D5", duration: "eighth", beat: 2, jianpu: "6" },
      { pitch: "C5", duration: "eighth", beat: 2.5, jianpu: "5" },
    ]},
    // ── Descending run: 6316̣ ──
    { number: 9, time_signature: "2/4", notes: [
      { pitch: "D5", duration: "eighth", beat: 1, jianpu: "6" },
      { pitch: "A4", duration: "eighth", beat: 1.5, jianpu: "3" },
      { pitch: "F4", duration: "eighth", beat: 2, jianpu: "1" },
      { pitch: "D4", duration: "eighth", beat: 2.5, jianpu: "6\u0323" },
    ]},
    // ── 3653 ascending ──
    { number: 10, time_signature: "2/4", notes: [
      { pitch: "A4", duration: "eighth", beat: 1, jianpu: "3" },
      { pitch: "D5", duration: "eighth", beat: 1.5, jianpu: "6" },
      { pitch: "C5", duration: "eighth", beat: 2, jianpu: "5" },
      { pitch: "A4", duration: "eighth", beat: 2.5, jianpu: "3" },
    ]},
    // ── 2321 pattern (galloping rhythm) ──
    { number: 11, time_signature: "2/4", notes: [
      { pitch: "G4", duration: "sixteenth", beat: 1, jianpu: "2" },
      { pitch: "A4", duration: "sixteenth", beat: 1.25, jianpu: "3" },
      { pitch: "G4", duration: "sixteenth", beat: 1.5, jianpu: "2" },
      { pitch: "F4", duration: "sixteenth", beat: 1.75, jianpu: "1" },
      { pitch: "G4", duration: "sixteenth", beat: 2, jianpu: "2" },
      { pitch: "A4", duration: "sixteenth", beat: 2.25, jianpu: "3" },
      { pitch: "G4", duration: "sixteenth", beat: 2.5, jianpu: "2" },
      { pitch: "F4", duration: "sixteenth", beat: 2.75, jianpu: "1" },
    ]},
    { number: 12, time_signature: "2/4", notes: [
      { pitch: "G4", duration: "sixteenth", beat: 1, jianpu: "2" },
      { pitch: "A4", duration: "sixteenth", beat: 1.25, jianpu: "3" },
      { pitch: "G4", duration: "sixteenth", beat: 1.5, jianpu: "2" },
      { pitch: "F4", duration: "sixteenth", beat: 1.75, jianpu: "1" },
      { pitch: "G4", duration: "sixteenth", beat: 2, jianpu: "2" },
      { pitch: "A4", duration: "sixteenth", beat: 2.25, jianpu: "3" },
      { pitch: "G4", duration: "sixteenth", beat: 2.5, jianpu: "2" },
      { pitch: "F4", duration: "sixteenth", beat: 2.75, jianpu: "1" },
    ]},
    // ── 6316̣ again ──
    { number: 13, time_signature: "2/4", notes: [
      { pitch: "D5", duration: "eighth", beat: 1, jianpu: "6" },
      { pitch: "A4", duration: "eighth", beat: 1.5, jianpu: "3" },
      { pitch: "F4", duration: "eighth", beat: 2, jianpu: "1" },
      { pitch: "D4", duration: "eighth", beat: 2.5, jianpu: "6\u0323" },
    ]},
    // ── 3653 ──
    { number: 14, time_signature: "2/4", notes: [
      { pitch: "A4", duration: "eighth", beat: 1, jianpu: "3" },
      { pitch: "D5", duration: "eighth", beat: 1.5, jianpu: "6" },
      { pitch: "C5", duration: "eighth", beat: 2, jianpu: "5" },
      { pitch: "A4", duration: "eighth", beat: 2.5, jianpu: "3" },
    ]},
    // ── More 2321 ──
    { number: 15, time_signature: "2/4", notes: [
      { pitch: "G4", duration: "sixteenth", beat: 1, jianpu: "2" },
      { pitch: "A4", duration: "sixteenth", beat: 1.25, jianpu: "3" },
      { pitch: "G4", duration: "sixteenth", beat: 1.5, jianpu: "2" },
      { pitch: "F4", duration: "sixteenth", beat: 1.75, jianpu: "1" },
      { pitch: "G4", duration: "sixteenth", beat: 2, jianpu: "2" },
      { pitch: "A4", duration: "sixteenth", beat: 2.25, jianpu: "3" },
      { pitch: "G4", duration: "sixteenth", beat: 2.5, jianpu: "2" },
      { pitch: "F4", duration: "sixteenth", beat: 2.75, jianpu: "1" },
    ]},
    { number: 16, time_signature: "2/4", notes: [
      { pitch: "G4", duration: "sixteenth", beat: 1, jianpu: "2" },
      { pitch: "A4", duration: "sixteenth", beat: 1.25, jianpu: "3" },
      { pitch: "G4", duration: "sixteenth", beat: 1.5, jianpu: "2" },
      { pitch: "F4", duration: "sixteenth", beat: 1.75, jianpu: "1" },
      { pitch: "G4", duration: "sixteenth", beat: 2, jianpu: "2" },
      { pitch: "A4", duration: "sixteenth", beat: 2.25, jianpu: "3" },
      { pitch: "G4", duration: "sixteenth", beat: 2.5, jianpu: "2" },
      { pitch: "F4", duration: "sixteenth", beat: 2.75, jianpu: "1" },
    ]},
    // ── Sustained 2. 61 section ──
    { number: 17, time_signature: "2/4", notes: [
      { pitch: "G4", duration: "quarter", beat: 1, jianpu: "2" },
      { pitch: "D5", duration: "eighth", beat: 2, jianpu: "6" },
      { pitch: "F4", duration: "eighth", beat: 2.5, jianpu: "1" },
    ]},
    { number: 18, time_signature: "2/4", notes: [
      { pitch: "G4", duration: "quarter", beat: 1, jianpu: "2" },
      { pitch: "D5", duration: "eighth", beat: 2, jianpu: "6" },
      { pitch: "F4", duration: "eighth", beat: 2.5, jianpu: "1" },
    ]},
    { number: 19, time_signature: "2/4", notes: [
      { pitch: "G4", duration: "quarter", beat: 1, jianpu: "2" },
      { pitch: "D5", duration: "eighth", beat: 2, jianpu: "6" },
      { pitch: "F4", duration: "eighth", beat: 2.5, jianpu: "1" },
    ]},
    { number: 20, time_signature: "2/4", notes: [
      { pitch: "G4", duration: "quarter", beat: 1, jianpu: "2" },
      { pitch: "D5", duration: "eighth", beat: 2, jianpu: "6" },
      { pitch: "F4", duration: "eighth", beat: 2.5, jianpu: "1" },
    ]},
    // ── Final 2321 run + cadence ──
    { number: 21, time_signature: "2/4", notes: [
      { pitch: "G4", duration: "sixteenth", beat: 1, jianpu: "2" },
      { pitch: "A4", duration: "sixteenth", beat: 1.25, jianpu: "3" },
      { pitch: "G4", duration: "sixteenth", beat: 1.5, jianpu: "2" },
      { pitch: "F4", duration: "sixteenth", beat: 1.75, jianpu: "1" },
      { pitch: "G4", duration: "sixteenth", beat: 2, jianpu: "2" },
      { pitch: "A4", duration: "sixteenth", beat: 2.25, jianpu: "3" },
      { pitch: "G4", duration: "sixteenth", beat: 2.5, jianpu: "2" },
      { pitch: "F4", duration: "sixteenth", beat: 2.75, jianpu: "1" },
    ]},
    // ── Cadential measures ──
    { number: 22, time_signature: "2/4", notes: [
      { pitch: "D5", duration: "quarter", beat: 1, jianpu: "6" },
      { pitch: "C5", duration: "quarter", beat: 2, jianpu: "5" },
    ]},
    { number: 23, time_signature: "2/4", notes: [
      { pitch: "A4", duration: "quarter", beat: 1, jianpu: "3" },
      { pitch: "C5", duration: "quarter", beat: 2, jianpu: "5" },
    ]},
    { number: 24, time_signature: "2/4", notes: [
      { pitch: "D5", duration: "quarter", beat: 1, jianpu: "6" },
      { pitch: "A4", duration: "eighth", beat: 2, jianpu: "3" },
      { pitch: "C5", duration: "eighth", beat: 2.5, jianpu: "5" },
    ]},
    { number: 25, time_signature: "2/4", notes: [
      { pitch: "D5", duration: "half", beat: 1, jianpu: "6" },
    ]},
  ],
};

export default function Home() {
  const [score, setScore] = useState<Score>(DEMO_SCORE);
  const [isMock, setIsMock] = useState(true);
  const [activeMeasure, setActiveMeasure] = useState(0);
  const [activeBeat, setActiveBeat] = useState(0);
  const [opacity, setOpacity] = useState(1);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [uploadSuccess, setUploadSuccess] = useState("");
  const [bpm, setBpm] = useState(120);
  const [practiceMode, setPracticeMode] = useState<PracticeMode>("follow");
  const cursorRef = useRef<CursorController | null>(null);

  // Parse beats-per-measure from time signature (e.g. "2/4" → 2)
  const beatsPerMeasure =
    score.measures[0]?.time_signature
      ? parseInt(score.measures[0].time_signature.split("/")[0], 10) || 4
      : 4;

  useEffect(() => {
    const ctrl = new CursorController();
    ctrl.setRenderCallback((pos) => {
      const measure = Math.floor(pos.position) + 1;
      const beat = (pos.position % 1) * beatsPerMeasure + 1;
      setActiveMeasure(measure);
      setActiveBeat(beat);
      setOpacity(pos.opacity);
    });
    cursorRef.current = ctrl;
    return () => ctrl.stop();
  }, [beatsPerMeasure]);

  // Practice hook — needs the score in ScoreResult shape
  const scoreForApi = {
    title: score.title,
    confidence: 1,
    is_mock: false,
    measures: score.measures,
  };
  const practice = usePractice(scoreForApi, cursorRef, bpm, practiceMode);

  const handleUpload = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const fileList = e.target.files;
      if (!fileList || fileList.length === 0) return;

      setUploading(true);
      setUploadError("");
      setUploadSuccess("");

      try {
        const data = fileList.length > 1
          ? await parseScoreMulti(Array.from(fileList))
          : await parseScore(fileList[0]);

        setScore({
          title: data.title,
          measures: data.measures,
          notation_type: data.notation_type,
          key_signature: data.key_signature,
          page_count: data.page_count,
        });
        setIsMock(data.is_mock);

        const notationType = data.notation_type === "jianpu" ? "jianpu" : "western";
        const pageInfo = (data.page_count ?? 1) > 1 ? `, ${data.page_count} pages` : "";

        if (data.is_mock) {
          setUploadSuccess(
            `Score recognition confidence too low — showing demo score "${data.title}" (${data.measures.length} measures, ${notationType} notation).`
          );
        } else {
          setUploadSuccess(
            `Loaded "${data.title}" — ${data.measures.length} measures, ${notationType} notation (confidence: ${Math.round(data.confidence * 100)}%${pageInfo})`
          );
        }
      } catch (err) {
        if (err instanceof ApiError) {
          setUploadError(`Upload failed: ${err.detail}`);
        } else {
          setUploadError(`Upload failed: ${(err as Error).message || "check your connection"}`);
        }
      } finally {
        setUploading(false);
      }
    },
    [],
  );

  const isPracticing = practice.state === "practicing";
  const isBusy = practice.state === "starting" || practice.state === "stopping";
  const combinedError = uploadError || practice.error;

  return (
    <div style={styles.app}>
      <header style={styles.header}>
        <h1 style={styles.h1}>AI Music Mentor</h1>
        <div style={styles.headerActions}>
          {/* Practice button */}
          {isPracticing ? (
            <button
              style={styles.stopBtn}
              onClick={practice.stop}
              disabled={isBusy}
            >
              Stop Practice
            </button>
          ) : (
            <button
              style={styles.startBtn}
              onClick={practice.start}
              disabled={isBusy || uploading}
            >
              {practice.state === "starting"
                ? "Starting..."
                : practice.state === "stopping"
                  ? "Analyzing..."
                  : "Start Practice"}
            </button>
          )}

          {/* Upload score */}
          <label
            style={{
              ...styles.uploadBtn,
              ...(isPracticing || isBusy ? styles.btnDisabled : {}),
            }}
          >
            {uploading ? "Uploading..." : "Upload Score"}
            <input
              type="file"
              accept="image/*,.pdf"
              multiple
              onChange={handleUpload}
              style={{ display: "none" }}
              disabled={uploading || isPracticing || isBusy}
            />
          </label>
        </div>
      </header>

      {/* Practice controls */}
      <div style={styles.practiceControls}>
        <label style={styles.bpmLabel}>
          BPM:
          <input
            type="number"
            min={40}
            max={240}
            step={1}
            value={bpm}
            onChange={(e) => setBpm(Math.max(40, Math.min(240, Number(e.target.value) || 40)))}
            disabled={isPracticing || isBusy}
            style={{
              ...styles.bpmInput,
              ...(isPracticing || isBusy ? styles.controlDisabled : {}),
            }}
          />
        </label>
        <div style={styles.modeToggle}>
          <button
            style={{
              ...styles.modeBtn,
              ...(practiceMode === "follow" ? styles.modeBtnActive : {}),
              ...(isPracticing || isBusy ? styles.controlDisabled : {}),
            }}
            onClick={() => setPracticeMode("follow")}
            disabled={isPracticing || isBusy}
          >
            Follow
          </button>
          <button
            style={{
              ...styles.modeBtn,
              ...(practiceMode === "guided" ? styles.modeBtnActiveGuided : {}),
              ...(isPracticing || isBusy ? styles.controlDisabled : {}),
            }}
            onClick={() => setPracticeMode("guided")}
            disabled={isPracticing || isBusy}
          >
            Guided
          </button>
        </div>
      </div>

      {/* Status indicators */}
      {isPracticing && (
        <div style={styles.status}>
          <span style={styles.statusDot} />
          {practiceMode === "guided"
            ? `Guided... (${bpm} BPM, ${practice.elapsed.toFixed(1)}s)`
            : `Listening... (Follow, ${bpm} BPM, ${practice.elapsed.toFixed(1)}s)`}
        </div>
      )}
      {practice.state === "stopping" && (
        <div style={styles.statusAnalyzing}>Analyzing your performance...</div>
      )}

      {combinedError && <div style={styles.error}>{combinedError}</div>}
      {uploadSuccess && <div style={styles.success}>{uploadSuccess}</div>}

      <ScoreViewer
        score={score}
        activeMeasure={activeMeasure}
        activeBeat={activeBeat}
        highlightOpacity={opacity}
      />

      {/* Feedback panel */}
      {practice.state === "done" && practice.feedback && (
        <FeedbackPanel feedback={practice.feedback} />
      )}
    </div>
  );
}

// ── Feedback Panel ──────────────────────────────────────────

function FeedbackPanel({ feedback }: { feedback: StopResult }) {
  const { erhu_analysis, practice_plan } = feedback;

  return (
    <div style={styles.feedbackContainer}>
      <h2 style={styles.feedbackTitle}>Practice Report</h2>

      {/* Summary */}
      <p style={styles.feedbackSummary}>{practice_plan.summary}</p>

      {/* Score bars */}
      <div style={styles.scoreRow}>
        <ScoreBar label="Accuracy" pct={practice_plan.accuracy_pct} />
        <ScoreBar label="Rhythm" pct={practice_plan.rhythm_pct} />
      </div>

      {/* Warmup */}
      <div style={styles.warmup}>
        <strong>Warmup: </strong>{practice_plan.warmup}
      </div>

      {/* Issues by measure */}
      {erhu_analysis.issues.length > 0 && (
        <div style={styles.issuesSection}>
          <h3 style={styles.sectionTitle}>Issues Found</h3>
          {erhu_analysis.issues.map((issue, i) => (
            <div key={i} style={styles.issueRow}>
              <span
                style={{
                  ...styles.issueBadge,
                  backgroundColor:
                    issue.severity === "error"
                      ? "#fecaca"
                      : issue.severity === "warning"
                        ? "#fef3c7"
                        : "#e0e7ff",
                  color:
                    issue.severity === "error"
                      ? "#dc2626"
                      : issue.severity === "warning"
                        ? "#d97706"
                        : "#4f46e5",
                }}
              >
                M{issue.measure}
              </span>
              <span style={styles.issueDetail}>{issue.detail}</span>
            </div>
          ))}
        </div>
      )}

      {/* Drills */}
      {practice_plan.drills.length > 0 && (
        <div style={styles.drillsSection}>
          <h3 style={styles.sectionTitle}>Practice Drills</h3>
          {practice_plan.drills.map((drill, i) => (
            <div key={i} style={styles.drillCard}>
              <div style={styles.drillHeader}>
                <span style={styles.drillMeasure}>Measure {drill.measure}</span>
                <span
                  style={{
                    ...styles.priorityBadge,
                    backgroundColor:
                      drill.priority === "high"
                        ? "#fecaca"
                        : drill.priority === "medium"
                          ? "#fef3c7"
                          : "#dcfce7",
                    color:
                      drill.priority === "high"
                        ? "#dc2626"
                        : drill.priority === "medium"
                          ? "#d97706"
                          : "#16a34a",
                  }}
                >
                  {drill.priority}
                </span>
              </div>
              <p style={styles.drillSummary}>{drill.issue_summary}</p>
              <p style={styles.drillTip}>{drill.tip}</p>
              <div style={styles.drillMeta}>
                <span>Tempo: {drill.suggested_tempo} BPM</span>
                <span>Reps: {drill.repetitions}x</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Closing */}
      <p style={styles.closing}>{practice_plan.closing}</p>
    </div>
  );
}

// ── Score Bar ───────────────────────────────────────────────

function ScoreBar({ label, pct }: { label: string; pct: number }) {
  const color =
    pct >= 80 ? "#22c55e" : pct >= 60 ? "#eab308" : "#ef4444";
  return (
    <div style={styles.scoreBarContainer}>
      <div style={styles.scoreBarLabel}>
        <span>{label}</span>
        <span style={{ fontWeight: 700 }}>{pct}%</span>
      </div>
      <div style={styles.scoreBarTrack}>
        <div
          style={{
            ...styles.scoreBarFill,
            width: `${pct}%`,
            backgroundColor: color,
          }}
        />
      </div>
    </div>
  );
}

// ── Styles ──────────────────────────────────────────────────

const styles: Record<string, React.CSSProperties> = {
  app: {
    maxWidth: 960,
    margin: "0 auto",
    padding: "24px 16px",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 24,
  },
  h1: {
    fontSize: 22,
    fontWeight: 700,
    color: "#1e293b",
    margin: 0,
  },
  headerActions: {
    display: "flex",
    gap: 8,
    alignItems: "center",
  },
  startBtn: {
    padding: "8px 16px",
    backgroundColor: "#22c55e",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    fontSize: 14,
    fontWeight: 500,
    cursor: "pointer",
  },
  stopBtn: {
    padding: "8px 16px",
    backgroundColor: "#ef4444",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    fontSize: 14,
    fontWeight: 500,
    cursor: "pointer",
  },
  uploadBtn: {
    padding: "8px 16px",
    backgroundColor: "#3b82f6",
    color: "#fff",
    borderRadius: 6,
    fontSize: 14,
    fontWeight: 500,
    cursor: "pointer",
  },
  btnDisabled: {
    opacity: 0.5,
    pointerEvents: "none" as const,
  },
  practiceControls: {
    display: "flex",
    alignItems: "center",
    gap: 16,
    marginBottom: 16,
  },
  bpmLabel: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    fontSize: 14,
    fontWeight: 500,
    color: "#475569",
  },
  bpmInput: {
    width: 64,
    padding: "4px 8px",
    border: "1px solid #cbd5e1",
    borderRadius: 6,
    fontSize: 14,
    textAlign: "center" as const,
    outline: "none",
  },
  modeToggle: {
    display: "flex",
    borderRadius: 6,
    overflow: "hidden",
    border: "1px solid #cbd5e1",
  },
  modeBtn: {
    padding: "4px 14px",
    fontSize: 13,
    fontWeight: 500,
    border: "none",
    backgroundColor: "#fff",
    color: "#64748b",
    cursor: "pointer",
  },
  modeBtnActive: {
    backgroundColor: "#22c55e",
    color: "#fff",
  },
  modeBtnActiveGuided: {
    backgroundColor: "#8b5cf6",
    color: "#fff",
  },
  controlDisabled: {
    opacity: 0.5,
    cursor: "default",
  },
  status: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "8px 12px",
    backgroundColor: "#f0fdf4",
    color: "#16a34a",
    borderRadius: 6,
    marginBottom: 16,
    fontSize: 14,
    fontWeight: 500,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: "50%",
    backgroundColor: "#22c55e",
    animation: "pulse 1.5s infinite",
  },
  statusAnalyzing: {
    padding: "8px 12px",
    backgroundColor: "#eff6ff",
    color: "#2563eb",
    borderRadius: 6,
    marginBottom: 16,
    fontSize: 14,
    fontWeight: 500,
  },
  error: {
    padding: "8px 12px",
    backgroundColor: "#fef2f2",
    color: "#dc2626",
    borderRadius: 6,
    marginBottom: 16,
    fontSize: 14,
  },
  success: {
    padding: "8px 12px",
    backgroundColor: "#f0fdf4",
    color: "#16a34a",
    borderRadius: 6,
    marginBottom: 16,
    fontSize: 14,
  },
  // Feedback panel
  feedbackContainer: {
    marginTop: 24,
    padding: 20,
    backgroundColor: "#fafafa",
    borderRadius: 12,
    border: "1px solid #e2e8f0",
  },
  feedbackTitle: {
    fontSize: 18,
    fontWeight: 700,
    color: "#1e293b",
    margin: "0 0 12px 0",
  },
  feedbackSummary: {
    fontSize: 14,
    color: "#475569",
    lineHeight: 1.6,
    margin: "0 0 16px 0",
  },
  scoreRow: {
    display: "flex",
    gap: 16,
    marginBottom: 16,
  },
  scoreBarContainer: {
    flex: 1,
  },
  scoreBarLabel: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: 13,
    color: "#475569",
    marginBottom: 4,
  },
  scoreBarTrack: {
    height: 8,
    backgroundColor: "#e2e8f0",
    borderRadius: 4,
    overflow: "hidden",
  },
  scoreBarFill: {
    height: "100%",
    borderRadius: 4,
    transition: "width 0.5s ease",
  },
  warmup: {
    fontSize: 13,
    color: "#64748b",
    backgroundColor: "#f1f5f9",
    padding: "8px 12px",
    borderRadius: 6,
    marginBottom: 16,
    lineHeight: 1.5,
  },
  issuesSection: {
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: 600,
    color: "#1e293b",
    margin: "0 0 8px 0",
  },
  issueRow: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "6px 0",
    borderBottom: "1px solid #f1f5f9",
    fontSize: 13,
  },
  issueBadge: {
    padding: "2px 8px",
    borderRadius: 4,
    fontSize: 12,
    fontWeight: 600,
    flexShrink: 0,
  },
  issueDetail: {
    color: "#475569",
  },
  drillsSection: {
    marginBottom: 16,
  },
  drillCard: {
    backgroundColor: "#fff",
    border: "1px solid #e2e8f0",
    borderRadius: 8,
    padding: 12,
    marginBottom: 8,
  },
  drillHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 6,
  },
  drillMeasure: {
    fontSize: 14,
    fontWeight: 600,
    color: "#1e293b",
  },
  priorityBadge: {
    padding: "2px 8px",
    borderRadius: 4,
    fontSize: 11,
    fontWeight: 600,
    textTransform: "uppercase" as const,
  },
  drillSummary: {
    fontSize: 13,
    color: "#475569",
    margin: "0 0 4px 0",
  },
  drillTip: {
    fontSize: 13,
    color: "#64748b",
    fontStyle: "italic",
    margin: "0 0 8px 0",
    lineHeight: 1.5,
  },
  drillMeta: {
    display: "flex",
    gap: 16,
    fontSize: 12,
    color: "#94a3b8",
  },
  closing: {
    fontSize: 14,
    color: "#475569",
    fontStyle: "italic",
    lineHeight: 1.6,
    margin: 0,
  },
};
