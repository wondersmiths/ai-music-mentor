"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import ScoreViewer, { Score } from "@/score/ScoreViewer";
import { CursorController } from "@/score/CursorController";
import { analyzeAudio, parseScore, ApiError } from "@/lib/api";

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
  const [error, setError] = useState("");
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

  const handleUpload = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      setUploading(true);
      setError("");

      try {
        const data = await parseScore(file);
        setScore({ title: data.title, measures: data.measures });
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.detail);
        } else {
          setError("Upload failed — check your connection");
        }
      } finally {
        setUploading(false);
      }
    },
    [],
  );

  return (
    <div style={styles.app}>
      <header style={styles.header}>
        <h1 style={styles.h1}>AI Music Mentor</h1>
        <label style={styles.uploadBtn}>
          {uploading ? "Uploading..." : "Upload Score"}
          <input
            type="file"
            accept="image/*,.pdf"
            onChange={handleUpload}
            style={{ display: "none" }}
            disabled={uploading}
          />
        </label>
      </header>

      {error && <div style={styles.error}>{error}</div>}

      <ScoreViewer
        score={score}
        activeMeasure={activeMeasure}
        activeBeat={activeBeat}
        highlightOpacity={opacity}
      />
    </div>
  );
}

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
  uploadBtn: {
    padding: "8px 16px",
    backgroundColor: "#3b82f6",
    color: "#fff",
    borderRadius: 6,
    fontSize: 14,
    fontWeight: 500,
    cursor: "pointer",
  },
  error: {
    padding: "8px 12px",
    backgroundColor: "#fef2f2",
    color: "#dc2626",
    borderRadius: 6,
    marginBottom: 16,
    fontSize: 14,
  },
};
