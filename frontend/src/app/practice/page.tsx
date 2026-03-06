"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { usePitchDetector } from "@/audio/pitch/usePitchDetector";
import { useSessionRecorder } from "@/audio/recorder/useSessionRecorder";
import { useStabilityAnalyzer } from "@/audio/stability/useStabilityAnalyzer";
import { useCursorEngine } from "@/audio/cursor/useCursorEngine";
import { useJianpuCurve } from "@/audio/jianpu/useJianpuCurve";
import { useMetronome } from "@/audio/metronome/useMetronome";
import { evaluatePractice, listScores, ApiError } from "@/lib/api";
import type { SavedScore } from "@/lib/api";
import type { PitchFrame } from "@/audio/pitch/types";
import type { JianpuNote } from "@/audio/jianpu/types";
import type { EvaluateResult } from "@/lib/api";

// ── Constants ────────────────────────────────────────────────

type Phase = "selecting" | "starting" | "countdown" | "recording" | "evaluating" | "results";
type ExerciseType = "long_tone" | "scale" | "melody";

const NOTE_FREQUENCIES: Record<string, number> = {
  D4: 293.66, "D#4": 311.13, E4: 329.63, F4: 349.23, "F#4": 369.99,
  G4: 392.00, "G#4": 415.30, A4: 440.00, "A#4": 466.16, B4: 493.88,
  C5: 523.25, "C#5": 554.37, D5: 587.33, "D#5": 622.25, E5: 659.26,
  F5: 698.46, "F#5": 739.99, G5: 783.99, "G#5": 830.61, A5: 880.00,
  "A#5": 932.33, B5: 987.77, C6: 1046.50, "C#6": 1108.73, D6: 1174.66,
};

const TARGET_NOTES = [
  "D4", "E4", "F4", "G4", "A4", "B4",
  "C5", "D5", "E5", "F5", "G5", "A5", "B5",
  "C6", "D6",
];

const SCALE_PRESETS: Record<string, string> = {
  "D Major": "1 2 3 4 5 6 7 1̇",
  "Pentatonic": "1 2 3 5 6 1̇",
  "Descending": "1̇ 7 6 5 4 3 2 1",
  "Up & Down": "1 2 3 4 5 6 7 1̇ | 1̇ 7 6 5 4 3 2 1",
};

const MELODY_PRESETS: Record<string, string> = {
  "Twinkle": "1 1 5 5 | 6 6 5 - | 4 4 3 3 | 2 2 1 -",
  "Mo Li Hua": "3 3 5 6 | 1̇ 6 5 - | 5 3 5 6 | 5 - - -",
};

const FALLBACK_INSTRUMENTS = [
  { name: "erhu", display_name: "Erhu (二胡)" },
  { name: "violin", display_name: "Violin" },
  { name: "flute", display_name: "Flute" },
  { name: "voice", display_name: "Voice" },
  { name: "guzheng", display_name: "Guzheng (古筝)" },
];

// All 12 semitone names for frequency-to-note conversion
const SEMITONE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

function frequencyToNoteName(freq: number): { note: string; cents: number } {
  if (freq <= 0) return { note: "--", cents: 0 };
  // Semitones above C0 (16.35 Hz)
  const semitones = 12 * Math.log2(freq / 16.3516);
  const rounded = Math.round(semitones);
  const cents = Math.round((semitones - rounded) * 100);
  const octave = Math.floor(rounded / 12);
  const noteIndex = ((rounded % 12) + 12) % 12;
  return { note: `${SEMITONE_NAMES[noteIndex]}${octave}`, cents };
}

// ── Jianpu display helpers ────────────────────────────────────

/** Convert a JianpuNote to its display character. */
function jianpuToDisplayChar(note: JianpuNote): string {
  if (note.degree === -1) return "\u2212"; // sustain → minus sign
  if (note.degree === 0) return "0"; // rest
  let ch = String(note.degree);
  if (note.octaveShift > 0) ch += "\u0307"; // combining dot above
  if (note.octaveShift < 0) ch += "\u0323"; // combining dot below
  return ch;
}

/** Map parsed notes to display positions with bar/beat info. */
function computeNotePositions(
  notes: JianpuNote[],
  beatsPerMeasure: number,
): { char: string; bar: number; beat: number; totalBeatStart: number; totalBeatEnd: number }[] {
  const positions: { char: string; bar: number; beat: number; totalBeatStart: number; totalBeatEnd: number }[] = [];
  let totalBeats = 0;

  for (const note of notes) {
    const bar = 1 + Math.floor(totalBeats / beatsPerMeasure);
    const beat = 1 + (totalBeats % beatsPerMeasure);
    positions.push({
      char: jianpuToDisplayChar(note),
      bar,
      beat,
      totalBeatStart: totalBeats,
      totalBeatEnd: totalBeats + note.beats,
    });
    totalBeats += note.beats;
  }

  return positions;
}

// ── Component ────────────────────────────────────────────────

export default function PracticePage() {
  // Phase
  const [phase, setPhase] = useState<Phase>("selecting");

  // Selection state
  const [exerciseType, setExerciseType] = useState<ExerciseType>("long_tone");
  const [instrument, setInstrument] = useState("erhu");
  const [instruments, setInstruments] = useState(FALLBACK_INSTRUMENTS);
  const [bpm, setBpm] = useState(120);
  const [bpmInput, setBpmInput] = useState("120");
  const [targetNote, setTargetNote] = useState("D5");
  const [scalePreset, setScalePreset] = useState("D Major");
  const [melodyPreset, setMelodyPreset] = useState("Twinkle");
  const [customJianpu, setCustomJianpu] = useState("");

  // Countdown state
  const [countdownValue, setCountdownValue] = useState(0);

  // Error state
  const [error, setError] = useState("");

  // Results
  const [result, setResult] = useState<EvaluateResult | null>(null);

  // Score library
  const [libraryScores, setLibraryScores] = useState<SavedScore[]>([]);
  const [showLibrary, setShowLibrary] = useState(false);
  const [libraryLoading, setLibraryLoading] = useState(false);

  // Inject CSS keyframes
  useEffect(() => {
    const id = "practice-keyframes";
    if (document.getElementById(id)) return;
    const style = document.createElement("style");
    style.id = id;
    style.textContent = `
      @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
    `;
    document.head.appendChild(style);
  }, []);

  // Fetch instruments
  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
    fetch(`${apiUrl}/instruments`)
      .then((r) => r.json())
      .then((data) => {
        if (data.instruments?.length) {
          setInstruments(data.instruments);
        }
      })
      .catch(() => {
        // use fallback
      });
  }, []);

  // Jianpu input for the current exercise
  const jianpuInput =
    exerciseType === "scale"
      ? SCALE_PRESETS[scalePreset] || ""
      : exerciseType === "melody"
        ? (melodyPreset === "Custom" ? customJianpu : MELODY_PRESETS[melodyPreset] || "")
        : "";

  // Target frequency for long tone
  const targetFrequency = NOTE_FREQUENCIES[targetNote] || 587.33;

  // ── Hooks ──────────────────────────────────────────────────

  const recorder = useSessionRecorder({ exerciseType });

  const stabilityAnalyzer = useStabilityAnalyzer({
    targetFrequency,
    enabled: exerciseType === "long_tone" && phase === "recording",
  });

  const cursor = useCursorEngine({
    config: { bpm, beatsPerMeasure: 4 },
    animationLoop: phase === "recording" && exerciseType !== "long_tone",
  });

  const jianpuCurve = useJianpuCurve({
    input: jianpuInput,
    config: { bpm, tonic: "D" },
  });

  const metronome = useMetronome({
    bpm,
    beatsPerMeasure: 4,
    enabled: phase === "recording" && exerciseType !== "long_tone",
  });

  // ── Callbacks ──────────────────────────────────────────────

  const phaseRef = useRef(phase);
  phaseRef.current = phase;

  const handlePitchFrame = useCallback(
    (frame: PitchFrame) => {
      if (phaseRef.current !== "recording") return;
      recorder.pushFrame(frame);
      if (exerciseType === "long_tone") {
        stabilityAnalyzer.pushFrame(frame);
      }
    },
    [recorder, stabilityAnalyzer, exerciseType],
  );

  const pitchDetector = usePitchDetector({ onPitch: handlePitchFrame });

  const handleBrowseLibrary = useCallback(async () => {
    if (showLibrary) {
      setShowLibrary(false);
      return;
    }
    setLibraryLoading(true);
    try {
      const scores = await listScores();
      setLibraryScores(scores);
    } catch {
      // ignore
    }
    setLibraryLoading(false);
    setShowLibrary(true);
  }, [showLibrary]);

  const handleSelectLibraryScore = useCallback((score: SavedScore) => {
    setCustomJianpu(score.jianpu_notation);
    if (exerciseType === "melody") {
      setMelodyPreset("Custom");
    } else {
      setExerciseType("melody");
      setMelodyPreset("Custom");
    }
    setShowLibrary(false);
  }, [exerciseType]);

  const handleStopRecording = useCallback(async () => {
    // Cancel countdown if still running
    if (countdownRef.current) {
      clearInterval(countdownRef.current);
      countdownRef.current = null;
    }
    if (phaseRef.current !== "recording") return;
    setPhase("evaluating");
    pitchDetector.stop();
    recorder.stop();
    cursor.stop();

    const session = recorder.getSession();
    if (!session || session.frames.length === 0) {
      setError("No pitch data — make sure your instrument is audible");
      setPhase("selecting");
      return;
    }

    try {
      const req = {
        exercise_type: exerciseType,
        frames: session.frames.map((f) => ({
          time: f.time,
          frequency: f.frequency,
          confidence: f.confidence,
        })),
        duration: session.duration,
        target_frequency: exerciseType === "long_tone" ? targetFrequency : undefined,
        reference_curve:
          exerciseType !== "long_tone" && jianpuCurve.curve.length > 0
            ? jianpuCurve.curve.map((p) => ({ time: p.time, frequency: p.frequency }))
            : undefined,
        bpm,
      };
      const evalResult = await evaluatePractice(req);
      setResult(evalResult);
      setPhase("results");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`Evaluation failed: ${err.detail}`);
      } else {
        setError(`Evaluation failed: ${(err as Error).message || "Unknown error"}`);
      }
      setPhase("selecting");
    }
  }, [pitchDetector, recorder, cursor, exerciseType, targetFrequency, jianpuCurve, bpm]);

  // Auto-stop when recorder reaches 60s limit
  useEffect(() => {
    if (recorder.state === "stopped" && phase === "recording") {
      handleStopRecording();
    }
  }, [recorder.state, phase, handleStopRecording]);

  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const handleStartRecording = useCallback(async () => {
    setError("");
    setResult(null);
    setPhase("starting");

    try {
      await pitchDetector.start();
    } catch {
      setError("Microphone access denied");
      setPhase("selecting");
      return;
    }

    // Check if pitch detector actually started
    if (pitchDetector.error) {
      setError(pitchDetector.error || "Microphone access denied");
      setPhase("selecting");
      return;
    }

    // Start countdown (4 beats at the selected BPM)
    const beatInterval = 60000 / bpm; // ms per beat
    const totalBeats = 4;
    let remaining = totalBeats;
    setCountdownValue(remaining);
    setPhase("countdown");

    countdownRef.current = setInterval(() => {
      remaining--;
      if (remaining <= 0) {
        // Countdown finished — start recording
        if (countdownRef.current) clearInterval(countdownRef.current);
        countdownRef.current = null;
        setCountdownValue(0);

        recorder.reset();
        stabilityAnalyzer.reset();
        recorder.start();
        if (exerciseType !== "long_tone") {
          cursor.start();
        }
        setPhase("recording");
      } else {
        setCountdownValue(remaining);
      }
    }, beatInterval);
  }, [pitchDetector, recorder, stabilityAnalyzer, cursor, exerciseType, bpm]);

  const handleTryAgain = useCallback(() => {
    setResult(null);
    setError("");
    recorder.reset();
    stabilityAnalyzer.reset();
    setPhase("selecting");
  }, [recorder, stabilityAnalyzer]);

  const handleNewExercise = useCallback(() => {
    setResult(null);
    setError("");
    recorder.reset();
    stabilityAnalyzer.reset();
    setExerciseType("long_tone");
    setTargetNote("D5");
    setScalePreset("D Major");
    setMelodyPreset("Twinkle");
    setCustomJianpu("");
    setBpm(120);
    setPhase("selecting");
  }, [recorder, stabilityAnalyzer]);

  // ── Render helpers ─────────────────────────────────────────

  const scoreColor = (score: number) =>
    score >= 80 ? "#22c55e" : score >= 60 ? "#eab308" : "#ef4444";

  // ── Phase: Selecting ───────────────────────────────────────

  if (phase === "countdown") {
    return (
      <div style={styles.app}>
        <header style={styles.header}>
          <h1 style={styles.h1}>
            {exerciseType === "long_tone"
              ? `Long Tone — ${targetNote}`
              : exerciseType === "scale"
                ? `Scale — ${scalePreset}`
                : `Melody — ${melodyPreset}`}
          </h1>
        </header>

        {/* Show the music sheet so students can preview */}
        {exerciseType !== "long_tone" && jianpuCurve.notes.length > 0 && (
          <JianpuStrip
            notes={jianpuCurve.notes}
            currentBar={1}
            currentBeat={0}
            beatsPerMeasure={4}
          />
        )}

        {exerciseType === "long_tone" && (
          <div style={styles.pitchDisplay}>
            <div style={styles.pitchNote}>{targetNote}</div>
            <div style={styles.pitchFreq}>
              {Math.round(NOTE_FREQUENCIES[targetNote])} Hz
            </div>
          </div>
        )}

        {/* Countdown overlay */}
        <div style={styles.countdownContainer}>
          <div style={styles.countdownNumber}>{countdownValue}</div>
          <div style={styles.countdownLabel}>Get ready...</div>
          <button
            style={{ ...styles.stopBtnFull, maxWidth: 200, marginTop: 24 }}
            onClick={() => {
              if (countdownRef.current) clearInterval(countdownRef.current);
              countdownRef.current = null;
              pitchDetector.stop();
              setPhase("selecting");
            }}
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  if (phase === "selecting" || phase === "starting") {
    return (
      <div style={styles.app}>
        <header style={styles.header}>
          <a href="/" style={styles.backLink}>&larr; Home</a>
          <h1 style={styles.h1}>Practice Session</h1>
        </header>

        {error && <div style={styles.error}>{error}</div>}

        {/* Exercise type cards */}
        <div style={styles.cardRow}>
          {(["long_tone", "scale", "melody"] as ExerciseType[]).map((type) => (
            <button
              key={type}
              style={{
                ...styles.exerciseCard,
                ...(exerciseType === type ? styles.exerciseCardActive : {}),
              }}
              onClick={() => setExerciseType(type)}
              disabled={phase === "starting"}
            >
              <div style={styles.exerciseIcon}>
                {type === "long_tone" ? "🎵" : type === "scale" ? "🎼" : "🎶"}
              </div>
              <div style={styles.exerciseLabel}>
                {type === "long_tone" ? "Long Tone" : type === "scale" ? "Scale" : "Melody"}
              </div>
            </button>
          ))}
        </div>

        {/* Settings */}
        <div style={styles.settingsGrid}>
          {/* Instrument */}
          <label style={styles.fieldLabel}>
            Instrument
            <select
              value={instrument}
              onChange={(e) => setInstrument(e.target.value)}
              style={styles.select}
              disabled={phase === "starting"}
            >
              {instruments.map((inst) => (
                <option key={inst.name} value={inst.name}>
                  {inst.display_name}
                </option>
              ))}
            </select>
          </label>

          {/* BPM */}
          <label style={styles.fieldLabel}>
            BPM
            <input
              type="number"
              min={40}
              max={240}
              step={1}
              value={bpmInput}
              onChange={(e) => setBpmInput(e.target.value)}
              onBlur={() => {
                const n = Math.max(40, Math.min(240, Math.round(Number(bpmInput) || 120)));
                setBpm(n);
                setBpmInput(String(n));
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") (e.target as HTMLInputElement).blur();
              }}
              style={styles.bpmInput}
              disabled={phase === "starting"}
            />
          </label>

          {/* Target note (long_tone only) */}
          {exerciseType === "long_tone" && (
            <label style={styles.fieldLabel}>
              Target Note
              <select
                value={targetNote}
                onChange={(e) => setTargetNote(e.target.value)}
                style={styles.select}
                disabled={phase === "starting"}
              >
                {TARGET_NOTES.map((n) => (
                  <option key={n} value={n}>
                    {n} ({Math.round(NOTE_FREQUENCIES[n])} Hz)
                  </option>
                ))}
              </select>
            </label>
          )}

          {/* Scale preset */}
          {exerciseType === "scale" && (
            <label style={styles.fieldLabel}>
              Scale
              <select
                value={scalePreset}
                onChange={(e) => setScalePreset(e.target.value)}
                style={styles.select}
                disabled={phase === "starting"}
              >
                {Object.keys(SCALE_PRESETS).map((k) => (
                  <option key={k} value={k}>{k}</option>
                ))}
              </select>
            </label>
          )}

          {/* Melody preset */}
          {exerciseType === "melody" && (
            <label style={styles.fieldLabel}>
              Melody
              <select
                value={melodyPreset}
                onChange={(e) => setMelodyPreset(e.target.value)}
                style={styles.select}
                disabled={phase === "starting"}
              >
                {Object.keys(MELODY_PRESETS).map((k) => (
                  <option key={k} value={k}>{k}</option>
                ))}
                <option value="Custom">Custom jianpu</option>
              </select>
            </label>
          )}
        </div>

        {/* Custom jianpu input */}
        {exerciseType === "melody" && melodyPreset === "Custom" && (
          <div style={{ marginBottom: 16 }}>
            <label style={styles.fieldLabel}>
              Jianpu notation
              <input
                type="text"
                value={customJianpu}
                onChange={(e) => setCustomJianpu(e.target.value)}
                placeholder="e.g. 1 2 3 5 | 6 6 5 -"
                style={styles.textInput}
                disabled={phase === "starting"}
              />
            </label>
          </div>
        )}

        {/* Browse Library */}
        <div style={{ marginBottom: 16 }}>
          <button
            style={styles.libraryBtn}
            onClick={handleBrowseLibrary}
            disabled={phase === "starting" || libraryLoading}
          >
            {libraryLoading ? "Loading..." : showLibrary ? "Hide Library" : "Browse Library"}
          </button>
        </div>

        {showLibrary && libraryScores.length > 0 && (
          <div style={styles.libraryPanel}>
            {libraryScores.map((s) => (
              <div key={s.id} style={styles.libraryCard}>
                <div>
                  <div style={styles.libraryTitle}>{s.title}</div>
                  <div style={styles.libraryMeta}>
                    {s.key_signature || "—"} {s.is_builtin ? "(built-in)" : ""}
                  </div>
                </div>
                <button
                  style={styles.librarySelectBtn}
                  onClick={() => handleSelectLibraryScore(s)}
                >
                  Select
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Start button */}
        <button
          style={{
            ...styles.startBtnFull,
            ...(phase === "starting" ? styles.btnDisabled : {}),
          }}
          onClick={handleStartRecording}
          disabled={phase === "starting"}
        >
          {phase === "starting" ? "Starting..." : "Start Practice"}
        </button>
      </div>
    );
  }

  // ── Phase: Recording ───────────────────────────────────────

  if (phase === "recording") {
    const noteInfo = pitchDetector.latestPitch
      ? frequencyToNoteName(pitchDetector.latestPitch.frequency)
      : null;

    const deviationCents = stabilityAnalyzer.stability?.current_deviation_cents ?? 0;
    const deviationClamped = Math.max(-50, Math.min(50, deviationCents));
    const deviationPct = ((deviationClamped + 50) / 100) * 100;

    const progressPct = Math.min((recorder.elapsed / 60) * 100, 100);

    return (
      <div style={styles.app}>
        <header style={styles.header}>
          <h1 style={styles.h1}>
            {exerciseType === "long_tone"
              ? `Long Tone — ${targetNote}`
              : exerciseType === "scale"
                ? `Scale — ${scalePreset}`
                : `Melody — ${melodyPreset}`}
          </h1>
        </header>

        {/* Pitch display */}
        <div style={styles.pitchDisplay}>
          <div style={styles.pitchNote}>
            {noteInfo?.note ?? "--"}
          </div>
          <div style={styles.pitchFreq}>
            {pitchDetector.latestPitch
              ? `${pitchDetector.latestPitch.frequency.toFixed(1)} Hz`
              : "—"}
          </div>
          <div
            style={{
              ...styles.pitchCents,
              color: noteInfo
                ? Math.abs(noteInfo.cents) <= 10
                  ? "#22c55e"
                  : Math.abs(noteInfo.cents) <= 25
                    ? "#eab308"
                    : "#ef4444"
                : "#94a3b8",
            }}
          >
            {noteInfo
              ? `${noteInfo.cents >= 0 ? "+" : ""}${noteInfo.cents} cents`
              : "—"}
          </div>
        </div>

        {/* Stability meter (long_tone only) */}
        {exerciseType === "long_tone" && stabilityAnalyzer.stability && (
          <div style={styles.stabilitySection}>
            <div style={styles.stabilityHeader}>
              <span style={styles.fieldLabel}>Stability</span>
              <span style={{
                fontWeight: 700,
                fontSize: 14,
                color: scoreColor(stabilityAnalyzer.stability.stability_score),
              }}>
                {Math.round(stabilityAnalyzer.stability.stability_score)}%
              </span>
            </div>
            <div style={styles.scoreBarTrack}>
              <div style={{
                ...styles.scoreBarFill,
                width: `${stabilityAnalyzer.stability.stability_score}%`,
                backgroundColor: scoreColor(stabilityAnalyzer.stability.stability_score),
              }} />
            </div>
            <div style={styles.stabilityMeta}>
              <span>{stabilityAnalyzer.stability.drift_direction === "sharp" ? "Sharp ↑" : stabilityAnalyzer.stability.drift_direction === "flat" ? "Flat ↓" : "Stable ●"}</span>
              <span>Mean: {stabilityAnalyzer.stability.mean_deviation_cents.toFixed(1)} cents</span>
            </div>
          </div>
        )}

        {/* Deviation bar */}
        <div style={styles.deviationSection}>
          <div style={styles.deviationLabels}>
            <span style={styles.deviationLabel}>-50c</span>
            <span style={styles.deviationLabel}>0</span>
            <span style={styles.deviationLabel}>+50c</span>
          </div>
          <div style={styles.deviationTrack}>
            <div style={styles.deviationCenter} />
            <div style={{
              ...styles.deviationMarker,
              left: `${deviationPct}%`,
            }} />
          </div>
        </div>

        {/* Metronome beat pulse (scale/melody only) */}
        {exerciseType !== "long_tone" && metronome.currentBeat > 0 && (
          <div style={styles.beatPulseRow}>
            {Array.from({ length: 4 }, (_, i) => (
              <div
                key={i}
                style={{
                  ...styles.beatDot,
                  backgroundColor:
                    metronome.currentBeat === i + 1
                      ? metronome.isAccent
                        ? "#3b82f6"
                        : "#60a5fa"
                      : "#e2e8f0",
                  transform: metronome.currentBeat === i + 1 ? "scale(1.3)" : "scale(1)",
                }}
              />
            ))}
          </div>
        )}

        {/* Jianpu strip + cursor position (scale/melody only) */}
        {exerciseType !== "long_tone" && (
          <>
            {jianpuCurve.notes.length > 0 && (
              <JianpuStrip
                notes={jianpuCurve.notes}
                currentBar={cursor.position.currentBar}
                currentBeat={cursor.position.currentBeat}
                beatsPerMeasure={4}
              />
            )}
            <div style={styles.cursorInfo}>
              Bar {cursor.position.currentBar}, Beat {cursor.position.currentBeat.toFixed(1)}
            </div>
          </>
        )}

        {/* Progress timer */}
        <div style={styles.progressSection}>
          <div style={styles.progressLabels}>
            <span>{recorder.elapsed.toFixed(1)}s / 60s</span>
            <span style={styles.frameCount}>{recorder.frameCount} frames</span>
          </div>
          <div style={styles.progressTrack}>
            <div style={{ ...styles.progressFill, width: `${progressPct}%` }} />
          </div>
        </div>

        {/* Stop button */}
        <button style={styles.stopBtnFull} onClick={handleStopRecording}>
          Stop Recording
        </button>
      </div>
    );
  }

  // ── Phase: Evaluating ──────────────────────────────────────

  if (phase === "evaluating") {
    return (
      <div style={styles.app}>
        <div style={styles.evaluatingContainer}>
          <div style={styles.spinner} />
          <p style={styles.evaluatingText}>Evaluating your performance...</p>
        </div>
      </div>
    );
  }

  // ── Phase: Results ─────────────────────────────────────────

  if (phase === "results" && result) {
    return (
      <div style={styles.app}>
        <header style={styles.header}>
          <a href="/" style={styles.backLink}>&larr; Home</a>
          <h1 style={styles.h1}>Results</h1>
        </header>

        {/* Overall score */}
        <div style={styles.overallScoreContainer}>
          <div style={{
            ...styles.overallScore,
            color: scoreColor(result.overall_score),
          }}>
            {Math.round(result.overall_score)}
          </div>
          <div style={styles.overallLabel}>Overall Score</div>
        </div>

        {/* Sub-score bars (2x2 grid) */}
        <div style={styles.subScoreGrid}>
          <ScoreBar label="Pitch" pct={result.pitch_score} />
          <ScoreBar label="Stability" pct={result.stability_score} />
          <ScoreBar label="Slide" pct={result.slide_score} />
          <ScoreBar label="Rhythm" pct={result.rhythm_score} />
        </div>

        {/* Textual feedback */}
        <div style={styles.feedbackBox}>
          <p style={styles.feedbackText}>{result.textual_feedback}</p>
        </div>

        {/* Recommended next */}
        {result.recommended_training_type && (
          <div style={styles.recommendedSection}>
            <span style={styles.recommendedLabel}>Recommended next:</span>
            <span style={styles.recommendedBadge}>
              {result.recommended_training_type.replace("_", " ")}
            </span>
          </div>
        )}

        {/* Action buttons */}
        <div style={styles.actionRow}>
          <button style={styles.tryAgainBtn} onClick={handleTryAgain}>
            Try Again
          </button>
          <button style={styles.newExerciseBtn} onClick={handleNewExercise}>
            New Exercise
          </button>
        </div>
      </div>
    );
  }

  // Fallback (shouldn't happen)
  return (
    <div style={styles.app}>
      <a href="/" style={styles.backLink}>&larr; Home</a>
    </div>
  );
}

// ── Score Bar ─────────────────────────────────────────────────

function ScoreBar({ label, pct }: { label: string; pct: number }) {
  const color = pct >= 80 ? "#22c55e" : pct >= 60 ? "#eab308" : "#ef4444";
  return (
    <div style={styles.scoreBarContainer}>
      <div style={styles.scoreBarLabel}>
        <span>{label}</span>
        <span style={{ fontWeight: 700 }}>{Math.round(pct)}%</span>
      </div>
      <div style={styles.scoreBarTrack}>
        <div style={{
          ...styles.scoreBarFill,
          width: `${pct}%`,
          backgroundColor: color,
        }} />
      </div>
    </div>
  );
}

// ── Jianpu Strip ──────────────────────────────────────────────

function JianpuStrip({
  notes,
  currentBar,
  currentBeat,
  beatsPerMeasure,
}: {
  notes: JianpuNote[];
  currentBar: number;
  currentBeat: number;
  beatsPerMeasure: number;
}) {
  const positions = computeNotePositions(notes, beatsPerMeasure);
  if (positions.length === 0) return null;

  const cursorTotalBeats = (currentBar - 1) * beatsPerMeasure + (currentBeat - 1);
  const activeIndex = positions.findIndex(
    (p) => cursorTotalBeats >= p.totalBeatStart && cursorTotalBeats < p.totalBeatEnd,
  );

  const elements: React.ReactNode[] = [];
  let lastBar = 0;

  for (let i = 0; i < positions.length; i++) {
    const p = positions[i];
    if (p.bar !== lastBar && lastBar > 0) {
      elements.push(
        <span key={`bar-${lastBar}`} style={styles.jianpuBarLine}>|</span>,
      );
    }
    lastBar = p.bar;

    const isPast = activeIndex >= 0 && i < activeIndex;
    const isActive = i === activeIndex;

    elements.push(
      <span
        key={i}
        style={{
          ...styles.jianpuChar,
          ...(isActive ? styles.jianpuCharActive : {}),
          ...(isPast ? styles.jianpuCharPast : {}),
        }}
      >
        {p.char}
      </span>,
    );
  }

  return <div style={styles.jianpuStrip}>{elements}</div>;
}

// ── Styles ────────────────────────────────────────────────────

const styles: Record<string, React.CSSProperties> = {
  app: {
    maxWidth: 960,
    margin: "0 auto",
    padding: "24px 16px",
    fontFamily: "Inter, system-ui, sans-serif",
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: 16,
    marginBottom: 24,
  },
  h1: {
    fontSize: 22,
    fontWeight: 700,
    color: "#1e293b",
    margin: 0,
  },
  backLink: {
    fontSize: 14,
    color: "#3b82f6",
    textDecoration: "none",
    fontWeight: 500,
  },

  // Error
  error: {
    padding: "8px 12px",
    backgroundColor: "#fef2f2",
    color: "#dc2626",
    borderRadius: 6,
    marginBottom: 16,
    fontSize: 14,
  },

  // Exercise type cards
  cardRow: {
    display: "flex",
    gap: 12,
    marginBottom: 24,
  },
  exerciseCard: {
    flex: 1,
    padding: "16px 12px",
    borderRadius: 12,
    border: "1px solid #e2e8f0",
    backgroundColor: "#fff",
    cursor: "pointer",
    textAlign: "center" as const,
    transition: "border-color 0.15s",
  },
  exerciseCardActive: {
    borderColor: "#3b82f6",
    backgroundColor: "#eff6ff",
  },
  exerciseIcon: {
    fontSize: 28,
    marginBottom: 8,
  },
  exerciseLabel: {
    fontSize: 14,
    fontWeight: 600,
    color: "#1e293b",
  },

  // Settings
  settingsGrid: {
    display: "flex",
    gap: 16,
    flexWrap: "wrap" as const,
    marginBottom: 24,
  },
  fieldLabel: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 4,
    fontSize: 13,
    fontWeight: 500,
    color: "#475569",
  },
  select: {
    padding: "6px 10px",
    border: "1px solid #cbd5e1",
    borderRadius: 6,
    fontSize: 14,
    outline: "none",
    minWidth: 140,
  },
  bpmInput: {
    width: 80,
    padding: "6px 10px",
    border: "1px solid #cbd5e1",
    borderRadius: 6,
    fontSize: 14,
    textAlign: "center" as const,
    outline: "none",
  },
  textInput: {
    padding: "6px 10px",
    border: "1px solid #cbd5e1",
    borderRadius: 6,
    fontSize: 14,
    outline: "none",
    width: "100%",
    marginTop: 4,
  },

  // Start button
  startBtnFull: {
    width: "100%",
    padding: "12px 16px",
    backgroundColor: "#22c55e",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    fontSize: 16,
    fontWeight: 600,
    cursor: "pointer",
  },
  btnDisabled: {
    opacity: 0.5,
    pointerEvents: "none" as const,
  },

  // ── Recording phase ──
  pitchDisplay: {
    textAlign: "center" as const,
    padding: "24px 0",
    marginBottom: 16,
  },
  pitchNote: {
    fontSize: 48,
    fontWeight: 700,
    color: "#1e293b",
    lineHeight: 1,
    marginBottom: 4,
  },
  pitchFreq: {
    fontSize: 16,
    color: "#64748b",
    marginBottom: 4,
  },
  pitchCents: {
    fontSize: 14,
    fontWeight: 600,
  },

  // Stability
  stabilitySection: {
    marginBottom: 16,
    padding: 12,
    backgroundColor: "#fafafa",
    borderRadius: 8,
    border: "1px solid #e2e8f0",
  },
  stabilityHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 6,
  },
  stabilityMeta: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: 12,
    color: "#64748b",
    marginTop: 6,
  },

  // Deviation bar
  deviationSection: {
    marginBottom: 16,
  },
  deviationLabels: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: 11,
    color: "#94a3b8",
    marginBottom: 4,
  },
  deviationLabel: {},
  deviationTrack: {
    position: "relative" as const,
    height: 12,
    backgroundColor: "#e2e8f0",
    borderRadius: 6,
    overflow: "hidden" as const,
  },
  deviationCenter: {
    position: "absolute" as const,
    left: "50%",
    top: 0,
    bottom: 0,
    width: 2,
    backgroundColor: "#94a3b8",
    transform: "translateX(-1px)",
  },
  deviationMarker: {
    position: "absolute" as const,
    top: 1,
    width: 10,
    height: 10,
    borderRadius: "50%",
    backgroundColor: "#3b82f6",
    transform: "translateX(-5px)",
    transition: "left 0.1s ease-out",
  },

  // Jianpu strip
  jianpuStrip: {
    display: "flex",
    flexDirection: "row" as const,
    gap: 2,
    overflowX: "auto" as const,
    justifyContent: "center",
    padding: 12,
    border: "1px solid #e2e8f0",
    borderRadius: 8,
    backgroundColor: "#fff",
    marginBottom: 12,
  },
  jianpuChar: {
    fontSize: 20,
    fontWeight: 600,
    padding: "4px 6px",
    borderRadius: 4,
    color: "#1e293b",
  },
  jianpuCharActive: {
    backgroundColor: "#dbeafe",
    color: "#2563eb",
  },
  jianpuCharPast: {
    color: "#94a3b8",
  },
  jianpuBarLine: {
    color: "#cbd5e1",
    margin: "0 4px",
    fontSize: 20,
    fontWeight: 400,
    display: "flex",
    alignItems: "center",
  },

  // Cursor info
  cursorInfo: {
    padding: "8px 12px",
    backgroundColor: "#eff6ff",
    color: "#2563eb",
    borderRadius: 6,
    marginBottom: 16,
    fontSize: 14,
    fontWeight: 500,
    textAlign: "center" as const,
  },

  // Progress
  progressSection: {
    marginBottom: 20,
  },
  progressLabels: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: 13,
    color: "#475569",
    marginBottom: 4,
  },
  frameCount: {
    color: "#94a3b8",
  },
  progressTrack: {
    height: 6,
    backgroundColor: "#e2e8f0",
    borderRadius: 3,
    overflow: "hidden",
  },
  progressFill: {
    height: "100%",
    backgroundColor: "#3b82f6",
    borderRadius: 3,
    transition: "width 0.3s ease",
  },

  // Stop button
  stopBtnFull: {
    width: "100%",
    padding: "12px 16px",
    backgroundColor: "#ef4444",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    fontSize: 16,
    fontWeight: 600,
    cursor: "pointer",
  },

  // ── Countdown phase ──
  countdownContainer: {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    justifyContent: "center",
    padding: "32px 0",
  },
  countdownNumber: {
    fontSize: 96,
    fontWeight: 700,
    color: "#3b82f6",
    lineHeight: 1,
    marginBottom: 8,
    animation: "pulse 0.5s ease-in-out infinite",
  },
  countdownLabel: {
    fontSize: 18,
    color: "#64748b",
    fontWeight: 500,
  },

  // ── Evaluating phase ──
  evaluatingContainer: {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    justifyContent: "center",
    padding: "80px 0",
  },
  spinner: {
    width: 40,
    height: 40,
    border: "4px solid #e2e8f0",
    borderTopColor: "#3b82f6",
    borderRadius: "50%",
    animation: "spin 0.8s linear infinite",
    marginBottom: 16,
  },
  evaluatingText: {
    fontSize: 16,
    color: "#475569",
    fontWeight: 500,
  },

  // ── Results phase ──
  overallScoreContainer: {
    textAlign: "center" as const,
    padding: "24px 0",
    marginBottom: 24,
  },
  overallScore: {
    fontSize: 64,
    fontWeight: 700,
    lineHeight: 1,
    marginBottom: 4,
  },
  overallLabel: {
    fontSize: 14,
    color: "#64748b",
    fontWeight: 500,
  },

  // Sub-score grid
  subScoreGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: 16,
    marginBottom: 24,
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

  // Feedback
  feedbackBox: {
    padding: "12px 16px",
    backgroundColor: "#fafafa",
    borderRadius: 8,
    border: "1px solid #e2e8f0",
    marginBottom: 16,
  },
  feedbackText: {
    fontSize: 14,
    color: "#475569",
    lineHeight: 1.6,
    margin: 0,
  },

  // Recommended
  recommendedSection: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    marginBottom: 24,
  },
  recommendedLabel: {
    fontSize: 13,
    color: "#64748b",
  },
  recommendedBadge: {
    padding: "4px 10px",
    backgroundColor: "#eff6ff",
    color: "#2563eb",
    borderRadius: 12,
    fontSize: 13,
    fontWeight: 500,
    textTransform: "capitalize" as const,
  },

  // Action buttons
  actionRow: {
    display: "flex",
    gap: 12,
  },
  tryAgainBtn: {
    flex: 1,
    padding: "10px 16px",
    backgroundColor: "#22c55e",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    fontSize: 14,
    fontWeight: 500,
    cursor: "pointer",
  },
  newExerciseBtn: {
    flex: 1,
    padding: "10px 16px",
    backgroundColor: "#3b82f6",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    fontSize: 14,
    fontWeight: 500,
    cursor: "pointer",
  },

  // Library
  libraryBtn: {
    padding: "8px 16px",
    backgroundColor: "#f8fafc",
    color: "#475569",
    border: "1px solid #cbd5e1",
    borderRadius: 6,
    fontSize: 14,
    fontWeight: 500,
    cursor: "pointer",
    width: "100%",
  },
  libraryPanel: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 8,
    marginBottom: 16,
    padding: 12,
    backgroundColor: "#fafafa",
    borderRadius: 8,
    border: "1px solid #e2e8f0",
    maxHeight: 240,
    overflowY: "auto" as const,
  },
  libraryCard: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "8px 12px",
    backgroundColor: "#fff",
    borderRadius: 6,
    border: "1px solid #e2e8f0",
  },
  libraryTitle: {
    fontSize: 14,
    fontWeight: 600,
    color: "#1e293b",
  },
  libraryMeta: {
    fontSize: 12,
    color: "#94a3b8",
    marginTop: 2,
  },
  librarySelectBtn: {
    padding: "4px 12px",
    backgroundColor: "#3b82f6",
    color: "#fff",
    border: "none",
    borderRadius: 4,
    fontSize: 12,
    fontWeight: 500,
    cursor: "pointer",
  },

  // Beat pulse
  beatPulseRow: {
    display: "flex",
    justifyContent: "center",
    gap: 12,
    marginBottom: 12,
  },
  beatDot: {
    width: 16,
    height: 16,
    borderRadius: "50%",
    transition: "all 0.1s ease",
  },
};
