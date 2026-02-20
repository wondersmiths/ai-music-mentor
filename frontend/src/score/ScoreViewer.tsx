/**
 * ScoreViewer — renders a structured score JSON as a simple visual
 * grid of measures and notes, with current-measure highlighting.
 *
 * Not engraving-quality — this is a functional practice view that
 * shows measure numbers, note names, durations, and beat positions
 * with clear visual feedback for the active measure.
 */

import React, { useEffect, useRef } from "react";

// ── Types matching the backend score JSON ──────────────────

export interface ScoreNote {
  pitch: string;    // e.g. "C4"
  duration: string; // e.g. "quarter"
  beat: number;     // beat position in the measure
}

export interface ScoreMeasure {
  number: number;
  time_signature: string; // e.g. "4/4"
  notes: ScoreNote[];
}

export interface Score {
  title: string;
  measures: ScoreMeasure[];
}

export interface ScoreViewerProps {
  /** The structured score to render */
  score: Score;
  /** 1-based measure number to highlight (0 or undefined = none) */
  activeMeasure?: number;
  /** Current beat within the active measure (for beat cursor) */
  activeBeat?: number;
  /** Opacity of the active-measure highlight (from CursorController) */
  highlightOpacity?: number;
}

// ── Duration → visual width mapping ────────────────────────

const DURATION_WIDTHS: Record<string, number> = {
  whole: 4,
  half: 2,
  quarter: 1,
  eighth: 0.5,
  sixteenth: 0.25,
};

const DURATION_SYMBOLS: Record<string, string> = {
  whole: "\u{1D15D}",
  half: "\u{1D15E}",
  quarter: "\u{1D15F}",
  eighth: "\u{1D160}",
  sixteenth: "\u{1D161}",
};

// ── Component ──────────────────────────────────────────────

const ScoreViewer: React.FC<ScoreViewerProps> = ({
  score,
  activeMeasure = 0,
  activeBeat = 0,
  highlightOpacity = 1,
}) => {
  const activeRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to keep the active measure visible
  useEffect(() => {
    if (activeRef.current) {
      activeRef.current.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
        inline: "center",
      });
    }
  }, [activeMeasure]);

  if (!score || !score.measures.length) {
    return <div style={styles.empty}>No score loaded</div>;
  }

  return (
    <div style={styles.container}>
      <h2 style={styles.title}>{score.title || "Untitled Score"}</h2>

      <div style={styles.measuresRow}>
        {score.measures.map((measure) => {
          const isActive = measure.number === activeMeasure;
          const beatsPerMeasure = parseTimeSig(measure.time_signature);

          return (
            <div
              key={measure.number}
              ref={isActive ? activeRef : undefined}
              style={{
                ...styles.measure,
                ...(isActive
                  ? {
                      ...styles.measureActive,
                      borderColor: `rgba(59, 130, 246, ${highlightOpacity})`,
                      backgroundColor: `rgba(59, 130, 246, ${highlightOpacity * 0.08})`,
                    }
                  : {}),
              }}
            >
              {/* Measure header */}
              <div style={styles.measureHeader}>
                <span style={styles.measureNumber}>{measure.number}</span>
                <span style={styles.timeSig}>{measure.time_signature}</span>
              </div>

              {/* Beat grid */}
              <div
                style={{
                  ...styles.beatGrid,
                  gridTemplateColumns: `repeat(${beatsPerMeasure}, 1fr)`,
                }}
              >
                {Array.from({ length: beatsPerMeasure }, (_, i) => {
                  const beatNum = i + 1;
                  const isBeatActive =
                    isActive && activeBeat >= beatNum && activeBeat < beatNum + 1;

                  return (
                    <div
                      key={beatNum}
                      style={{
                        ...styles.beatSlot,
                        ...(isBeatActive ? styles.beatSlotActive : {}),
                      }}
                    >
                      <span style={styles.beatLabel}>{beatNum}</span>
                    </div>
                  );
                })}
              </div>

              {/* Notes */}
              <div style={styles.notesList}>
                {measure.notes.map((note, idx) => {
                  const width = DURATION_WIDTHS[note.duration] ?? 1;
                  const symbol = DURATION_SYMBOLS[note.duration] ?? "";
                  const isBeatActive =
                    isActive &&
                    activeBeat >= note.beat &&
                    activeBeat < note.beat + width;

                  return (
                    <div
                      key={idx}
                      style={{
                        ...styles.note,
                        flex: `${width} 0 0`,
                        ...(isBeatActive ? styles.noteActive : {}),
                      }}
                    >
                      <span style={styles.notePitch}>{note.pitch}</span>
                      <span style={styles.noteDuration}>
                        {symbol || note.duration}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ScoreViewer;

// ── Helpers ────────────────────────────────────────────────

function parseTimeSig(ts: string): number {
  const parts = ts.split("/");
  return parts.length === 2 ? parseInt(parts[0], 10) || 4 : 4;
}

// ── Styles (inline for zero-dependency portability) ────────

const styles: Record<string, React.CSSProperties> = {
  container: {
    fontFamily: "'Inter', 'Segoe UI', system-ui, sans-serif",
    padding: 16,
    maxWidth: "100%",
    overflowX: "auto",
  },
  title: {
    fontSize: 18,
    fontWeight: 600,
    margin: "0 0 12px 0",
    color: "#1e293b",
  },
  measuresRow: {
    display: "flex",
    gap: 8,
    overflowX: "auto",
    paddingBottom: 8,
  },
  measure: {
    border: "2px solid #e2e8f0",
    borderRadius: 8,
    padding: 10,
    minWidth: 160,
    flexShrink: 0,
    transition: "border-color 0.3s, background-color 0.3s",
    backgroundColor: "#fff",
  },
  measureActive: {
    borderWidth: 2,
    boxShadow: "0 0 0 1px rgba(59, 130, 246, 0.2)",
  },
  measureHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
  },
  measureNumber: {
    fontSize: 12,
    fontWeight: 700,
    color: "#64748b",
  },
  timeSig: {
    fontSize: 11,
    color: "#94a3b8",
  },
  beatGrid: {
    display: "grid",
    gap: 2,
    marginBottom: 8,
  },
  beatSlot: {
    height: 4,
    backgroundColor: "#e2e8f0",
    borderRadius: 2,
    transition: "background-color 0.15s",
  },
  beatSlotActive: {
    backgroundColor: "#3b82f6",
  },
  beatLabel: {
    fontSize: 0,  // visually hidden but accessible
  },
  notesList: {
    display: "flex",
    gap: 4,
  },
  note: {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    padding: "6px 4px",
    borderRadius: 6,
    backgroundColor: "#f8fafc",
    border: "1px solid #e2e8f0",
    transition: "background-color 0.15s, border-color 0.15s",
    minWidth: 36,
  },
  noteActive: {
    backgroundColor: "#eff6ff",
    borderColor: "#93c5fd",
  },
  notePitch: {
    fontSize: 14,
    fontWeight: 600,
    color: "#1e293b",
  },
  noteDuration: {
    fontSize: 11,
    color: "#94a3b8",
    marginTop: 2,
  },
  empty: {
    padding: 32,
    textAlign: "center" as const,
    color: "#94a3b8",
    fontSize: 14,
  },
};
