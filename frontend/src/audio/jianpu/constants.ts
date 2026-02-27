import type { JianpuCurveConfig } from "./types";

export const DEFAULT_JIANPU_CONFIG: JianpuCurveConfig = {
  tonic: "D",
  baseOctave: 4,
  bpm: 120,
  framesPerSecond: 50,
  beatsPerMeasure: 4,
};

/**
 * Semitone intervals for scale degrees 1–7 in a major scale.
 * Degree 1 = unison, 2 = whole step, 3 = major third, etc.
 */
export const DEGREE_INTERVALS: Record<number, number> = {
  1: 0,
  2: 2,
  3: 4,
  4: 5,
  5: 7,
  6: 9,
  7: 11,
};

/**
 * MIDI note numbers for tonic notes at octave 4.
 * Used as the base for degree→frequency conversion.
 */
export const TONIC_MIDI: Record<string, number> = {
  C: 60,
  "C#": 61,
  D: 62,
  "D#": 63,
  E: 64,
  F: 65,
  "F#": 66,
  G: 67,
  "G#": 68,
  A: 69,
  "A#": 70,
  B: 71,
};

/** A4 = 440 Hz, MIDI 69. frequency = 440 * 2^((midi - 69) / 12) */
export const A4_FREQUENCY = 440;
export const A4_MIDI = 69;
