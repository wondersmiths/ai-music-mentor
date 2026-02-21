"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import ScoreViewer, { Score } from "@/score/ScoreViewer";
import { CursorController } from "@/score/CursorController";
import { parseScore, ApiError, StopResult } from "@/lib/api";
import { usePractice } from "@/hooks/usePractice";

const DEMO_SCORE: Score = {
  title: "C Major Scale",
  measures: [
    {
      number: 1,
      time_signature: "4/4",
      notes: [
        { pitch: "C4", duration: "quarter", beat: 1 },
        { pitch: "D4", duration: "quarter", beat: 2 },
        { pitch: "E4", duration: "quarter", beat: 3 },
        { pitch: "F4", duration: "quarter", beat: 4 },
      ],
    },
    {
      number: 2,
      time_signature: "4/4",
      notes: [
        { pitch: "G4", duration: "quarter", beat: 1 },
        { pitch: "A4", duration: "quarter", beat: 2 },
        { pitch: "B4", duration: "quarter", beat: 3 },
        { pitch: "C5", duration: "quarter", beat: 4 },
      ],
    },
  ],
};

export default function Home() {
  const [score, setScore] = useState<Score>(DEMO_SCORE);
  const [activeMeasure, setActiveMeasure] = useState(0);
  const [activeBeat, setActiveBeat] = useState(0);
  const [opacity, setOpacity] = useState(1);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const cursorRef = useRef<CursorController | null>(null);

  useEffect(() => {
    const ctrl = new CursorController();
    ctrl.setRenderCallback((pos) => {
      const measure = Math.floor(pos.position) + 1;
      const beat = (pos.position % 1) * 4 + 1;
      setActiveMeasure(measure);
      setActiveBeat(beat);
      setOpacity(pos.opacity);
    });
    cursorRef.current = ctrl;
    return () => ctrl.stop();
  }, []);

  // Practice hook — needs the score in ScoreResult shape
  const scoreForApi = {
    title: score.title,
    confidence: 1,
    is_mock: false,
    measures: score.measures,
  };
  const practice = usePractice(scoreForApi, cursorRef);

  const handleUpload = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      setUploading(true);
      setUploadError("");

      try {
        const data = await parseScore(file);
        setScore({ title: data.title, measures: data.measures });
      } catch (err) {
        if (err instanceof ApiError) {
          setUploadError(err.detail);
        } else {
          setUploadError("Upload failed — check your connection");
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
              onChange={handleUpload}
              style={{ display: "none" }}
              disabled={uploading || isPracticing || isBusy}
            />
          </label>
        </div>
      </header>

      {/* Status indicators */}
      {isPracticing && (
        <div style={styles.status}>
          <span style={styles.statusDot} />
          Listening... ({practice.elapsed.toFixed(1)}s)
        </div>
      )}
      {practice.state === "stopping" && (
        <div style={styles.statusAnalyzing}>Analyzing your performance...</div>
      )}

      {combinedError && <div style={styles.error}>{combinedError}</div>}

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
