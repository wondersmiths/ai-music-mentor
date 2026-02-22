/**
 * ScoreViewer — renders a structured score JSON as a visual music sheet
 * with wrapping rows, staff-like layout, and a visible moving cursor.
 */

import React, { useEffect, useRef } from "react";

// ── Types matching the backend score JSON ──────────────────

export interface ScoreNote {
  pitch: string;
  duration: string;
  beat: number;
}

export interface ScoreMeasure {
  number: number;
  time_signature: string;
  notes: ScoreNote[];
}

export interface Score {
  title: string;
  measures: ScoreMeasure[];
}

export interface ScoreViewerProps {
  score: Score;
  activeMeasure?: number;
  activeBeat?: number;
  highlightOpacity?: number;
}

// ── Duration helpers ────────────────────────────────────────

const DURATION_BEATS: Record<string, number> = {
  whole: 4, half: 2, quarter: 1, eighth: 0.5, sixteenth: 0.25,
};

const DURATION_LABELS: Record<string, string> = {
  whole: "w", half: "h", quarter: "q", eighth: "8th", sixteenth: "16th",
};

// Map pitch to a vertical staff position (higher pitch = higher on staff)
const PITCH_CLASSES: Record<string, number> = {
  C: 0, D: 1, E: 2, F: 3, G: 4, A: 5, B: 6,
};

function pitchToStaffY(pitch: string): number {
  const match = pitch.match(/^([A-G]#?)(\d)$/);
  if (!match) return 50;
  const name = match[1][0];
  const octave = parseInt(match[2], 10);
  const pc = PITCH_CLASSES[name] ?? 0;
  const semitonePos = octave * 7 + pc;
  // Map to a percentage: C3=low, C6=high
  const low = 3 * 7; // C3
  const high = 6 * 7; // C6
  const pct = ((semitonePos - low) / (high - low)) * 100;
  return 100 - Math.max(5, Math.min(95, pct)); // invert: high pitch = low Y
}

// ── Component ──────────────────────────────────────────────

const MEASURES_PER_ROW = 4;

const ScoreViewer: React.FC<ScoreViewerProps> = ({
  score,
  activeMeasure = 0,
  activeBeat = 0,
  highlightOpacity = 1,
}) => {
  const activeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (activeRef.current) {
      activeRef.current.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
      });
    }
  }, [activeMeasure]);

  if (!score || !score.measures.length) {
    return <div style={s.empty}>No score loaded</div>;
  }

  // Split measures into rows
  const rows: ScoreMeasure[][] = [];
  for (let i = 0; i < score.measures.length; i += MEASURES_PER_ROW) {
    rows.push(score.measures.slice(i, i + MEASURES_PER_ROW));
  }

  return (
    <div style={s.container}>
      <div style={s.titleRow}>
        <h2 style={s.title}>{score.title || "Untitled Score"}</h2>
        <span style={s.measureCount}>{score.measures.length} measures</span>
      </div>

      {rows.map((row, rowIdx) => (
        <div key={rowIdx} style={s.staffRow}>
          {/* Staff lines */}
          <div style={s.staffLines}>
            {[0, 1, 2, 3, 4].map((i) => (
              <div key={i} style={{ ...s.staffLine, top: `${20 + i * 15}%` }} />
            ))}
          </div>

          {row.map((measure) => {
            const isActive = measure.number === activeMeasure;
            const beatsPerMeasure = parseTimeSig(measure.time_signature);

            return (
              <div
                key={measure.number}
                ref={isActive ? activeRef : undefined}
                style={{
                  ...s.measure,
                  ...(isActive ? {
                    backgroundColor: `rgba(59, 130, 246, ${highlightOpacity * 0.06})`,
                  } : {}),
                }}
              >
                {/* Measure number */}
                <div style={s.measureNum}>{measure.number}</div>

                {/* Time signature (first measure of each row) */}
                {measure.number === row[0].number && (
                  <div style={s.timeSig}>{measure.time_signature}</div>
                )}

                {/* Notes on the staff */}
                <div style={s.noteArea}>
                  {measure.notes.map((note, idx) => {
                    const width = DURATION_BEATS[note.duration] ?? 1;
                    const leftPct = ((note.beat - 1) / beatsPerMeasure) * 100;
                    const widthPct = (width / beatsPerMeasure) * 100;
                    const topPct = pitchToStaffY(note.pitch);
                    const isNoteActive =
                      isActive &&
                      activeBeat >= note.beat &&
                      activeBeat < note.beat + width;

                    return (
                      <div
                        key={idx}
                        style={{
                          ...s.noteContainer,
                          left: `${leftPct}%`,
                          width: `${widthPct}%`,
                          top: `${topPct}%`,
                        }}
                      >
                        {/* Note head */}
                        <div
                          style={{
                            ...s.noteHead,
                            ...(isNoteActive ? s.noteHeadActive : {}),
                            ...(width >= 2 ? s.noteHeadLarge : {}),
                          }}
                        />
                        {/* Pitch label */}
                        <div
                          style={{
                            ...s.noteLabel,
                            ...(isNoteActive ? s.noteLabelActive : {}),
                          }}
                        >
                          {note.pitch}
                        </div>
                        {/* Duration label */}
                        <div style={s.durLabel}>
                          {DURATION_LABELS[note.duration] || note.duration}
                        </div>
                      </div>
                    );
                  })}

                  {/* Cursor / playhead */}
                  {isActive && highlightOpacity > 0.1 && (
                    <div
                      style={{
                        ...s.cursor,
                        left: `${((activeBeat - 1) / beatsPerMeasure) * 100}%`,
                        opacity: highlightOpacity,
                      }}
                    />
                  )}
                </div>

                {/* Beat ticks below */}
                <div style={s.beatTicks}>
                  {Array.from({ length: beatsPerMeasure }, (_, i) => {
                    const beatNum = i + 1;
                    const isBeatActive =
                      isActive && activeBeat >= beatNum && activeBeat < beatNum + 1;
                    return (
                      <div
                        key={beatNum}
                        style={{
                          ...s.beatTick,
                          ...(isBeatActive ? s.beatTickActive : {}),
                        }}
                      >
                        {beatNum}
                      </div>
                    );
                  })}
                </div>

                {/* Right barline */}
                <div style={s.barline} />
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
};

export default ScoreViewer;

// ── Helpers ────────────────────────────────────────────────

function parseTimeSig(ts: string): number {
  const parts = ts.split("/");
  return parts.length === 2 ? parseInt(parts[0], 10) || 4 : 4;
}

// ── Styles ─────────────────────────────────────────────────

const s: Record<string, React.CSSProperties> = {
  container: {
    fontFamily: "'Inter', 'Segoe UI', system-ui, sans-serif",
    padding: "8px 0",
    maxWidth: "100%",
  },
  titleRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "baseline",
    marginBottom: 12,
    padding: "0 4px",
  },
  title: {
    fontSize: 18,
    fontWeight: 600,
    margin: 0,
    color: "#1e293b",
  },
  measureCount: {
    fontSize: 12,
    color: "#94a3b8",
  },
  empty: {
    padding: 32,
    textAlign: "center" as const,
    color: "#94a3b8",
    fontSize: 14,
  },

  // Staff row — one horizontal line of measures
  staffRow: {
    display: "flex",
    position: "relative" as const,
    borderLeft: "2px solid #94a3b8",
    marginBottom: 16,
    minHeight: 120,
  },
  staffLines: {
    position: "absolute" as const,
    inset: 0,
    pointerEvents: "none" as const,
    zIndex: 0,
  },
  staffLine: {
    position: "absolute" as const,
    left: 0,
    right: 0,
    height: 1,
    backgroundColor: "#e2e8f0",
  },

  // Individual measure
  measure: {
    flex: 1,
    position: "relative" as const,
    minHeight: 120,
    padding: "4px 0",
    transition: "background-color 0.2s",
    zIndex: 1,
  },
  measureNum: {
    position: "absolute" as const,
    top: -2,
    left: 4,
    fontSize: 10,
    fontWeight: 700,
    color: "#94a3b8",
    zIndex: 2,
  },
  timeSig: {
    position: "absolute" as const,
    top: -2,
    left: 20,
    fontSize: 10,
    color: "#b0b8c4",
    zIndex: 2,
  },
  barline: {
    position: "absolute" as const,
    top: 0,
    right: 0,
    bottom: 0,
    width: 2,
    backgroundColor: "#94a3b8",
  },

  // Note area (staff body where notes sit)
  noteArea: {
    position: "relative" as const,
    height: 80,
    marginTop: 14,
    marginBottom: 4,
  },

  // Note positioning
  noteContainer: {
    position: "absolute" as const,
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    transform: "translate(0, -50%)",
    zIndex: 3,
  },
  noteHead: {
    width: 14,
    height: 10,
    borderRadius: "50%",
    backgroundColor: "#1e293b",
    border: "2px solid #1e293b",
    transition: "all 0.15s",
    flexShrink: 0,
  },
  noteHeadActive: {
    backgroundColor: "#3b82f6",
    borderColor: "#3b82f6",
    width: 18,
    height: 13,
    boxShadow: "0 0 8px rgba(59, 130, 246, 0.5)",
  },
  noteHeadLarge: {
    backgroundColor: "transparent",
  },
  noteLabel: {
    fontSize: 11,
    fontWeight: 600,
    color: "#475569",
    marginTop: 2,
    whiteSpace: "nowrap" as const,
    transition: "color 0.15s",
  },
  noteLabelActive: {
    color: "#2563eb",
    fontWeight: 700,
  },
  durLabel: {
    fontSize: 9,
    color: "#94a3b8",
    marginTop: 1,
  },

  // Cursor / playhead
  cursor: {
    position: "absolute" as const,
    top: 0,
    bottom: 0,
    width: 3,
    backgroundColor: "#3b82f6",
    borderRadius: 2,
    zIndex: 4,
    transition: "left 0.12s ease-out",
    boxShadow: "0 0 6px rgba(59, 130, 246, 0.4)",
  },

  // Beat indicators
  beatTicks: {
    display: "flex",
    position: "relative" as const,
    zIndex: 2,
    padding: "0 2px",
  },
  beatTick: {
    flex: 1,
    textAlign: "center" as const,
    fontSize: 9,
    color: "#cbd5e1",
    borderTop: "1px solid #e2e8f0",
    paddingTop: 2,
    transition: "color 0.15s, border-color 0.15s",
  },
  beatTickActive: {
    color: "#3b82f6",
    fontWeight: 700,
    borderTopColor: "#3b82f6",
    borderTopWidth: 2,
  },
};
