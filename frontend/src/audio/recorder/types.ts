import type { PitchFrame } from "../pitch/types";

export type { PitchFrame };

export type RecorderState = "idle" | "recording" | "stopped";

export interface RecordedFrame {
  time: number;        // seconds since recording start
  frequency: number;   // Hz
  confidence: number;  // 0–1
}

export interface PracticeSession {
  id: string;                    // crypto.randomUUID()
  exerciseType: string;          // e.g. "long_tone", "scale", "melody"
  startedAt: string;             // ISO 8601 timestamp
  duration: number;              // actual duration in seconds
  frameCount: number;            // total accepted frames
  framesPerSecond: number;       // configured fps
  frames: RecordedFrame[];       // the pitch curve
}

export interface RecorderConfig {
  maxDuration: number;           // seconds
  framesPerSecond: number;       // informational, for export metadata
  minConfidence: number;         // 0.0 — record all frames by default
}
