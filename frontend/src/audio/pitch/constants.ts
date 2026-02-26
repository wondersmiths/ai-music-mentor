import type { PitchDetectorConfig } from "./types";

/** Erhu sounding range with margin for tuning variation */
export const ERHU_FREQ_MIN = 260; // just below D4 (293 Hz)
export const ERHU_FREQ_MAX = 2400; // just above D7 (2349 Hz)

/** Pre-emphasis coefficient (first-order highpass to attenuate bow rumble) */
export const PRE_EMPHASIS = 0.97;

export const DEFAULT_CONFIG: PitchDetectorConfig = {
  sampleRate: 16000,
  frameSize: 2048,
  hopSize: 320,
  yinThreshold: 0.12,
  freqMin: ERHU_FREQ_MIN,
  freqMax: ERHU_FREQ_MAX,
  medianWindow: 5,
  emaAlpha: 0.35,
  silenceThreshold: -50, // dB
  confidenceFloor: 0.65,
};
