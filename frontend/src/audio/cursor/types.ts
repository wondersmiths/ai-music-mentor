/**
 * Types for the local BPM-based cursor engine (F4).
 */

export type CursorEngineState = "idle" | "playing" | "paused" | "finished";

/** The current position of the cursor in musical time. */
export interface CursorPosition {
  /** Wall-clock elapsed time in seconds since start. */
  currentTime: number;
  /** Current bar/measure number (1-based). */
  currentBar: number;
  /** Current beat within the bar (1-based, fractional). */
  currentBeat: number;
  /** Total beats elapsed since start. */
  totalBeats: number;
}

/** Configuration for the cursor engine. */
export interface CursorEngineConfig {
  /** Beats per minute. Default 120. */
  bpm: number;
  /** Beats per measure (time signature numerator). Default 4. */
  beatsPerMeasure: number;
  /** Total number of measures (0 = unlimited). Default 0. */
  totalMeasures: number;
  /** Count-in beats before starting (0 = no count-in). Default 0. */
  countInBeats: number;
}
