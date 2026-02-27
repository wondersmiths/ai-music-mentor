/**
 * Types for the Jianpu → continuous pitch curve converter (F5).
 */

/** A single point in the continuous pitch curve. */
export interface PitchPoint {
  time: number;       // seconds from start
  frequency: number;  // Hz (0 = rest/silence)
}

/** A parsed jianpu token before curve generation. */
export interface JianpuNote {
  degree: number;       // 1–7 scale degree (0 = rest)
  octaveShift: number;  // +1 = dot above, -1 = dot below
  beats: number;        // duration in beats
}

/** Configuration for curve generation. */
export interface JianpuCurveConfig {
  /** Tonic note name, e.g. "D", "C", "F". Default "D". */
  tonic: string;
  /** Base octave for degree 1. Default 4 (middle octave). */
  baseOctave: number;
  /** BPM for timing. Default 120. */
  bpm: number;
  /** Frames per second in output curve. Default 50. */
  framesPerSecond: number;
  /** Time signature numerator (beats per measure). Default 4. */
  beatsPerMeasure: number;
}

/** Result of parsing + converting a jianpu string. */
export interface JianpuCurveResult {
  /** The continuous pitch curve (time, frequency). */
  curve: PitchPoint[];
  /** Total duration in seconds. */
  duration: number;
  /** Number of measures parsed. */
  measureCount: number;
  /** The parsed notes (for debugging/display). */
  notes: JianpuNote[];
}
