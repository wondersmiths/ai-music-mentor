export interface PitchFrame {
  time: number;
  frequency: number;
  confidence: number;
}

export interface PitchDetectorConfig {
  sampleRate: number;
  frameSize: number;
  hopSize: number;
  yinThreshold: number;
  freqMin: number;
  freqMax: number;
  medianWindow: number;
  emaAlpha: number;
  silenceThreshold: number; // dB
  confidenceFloor: number;
}

export type PitchDetectorState = "idle" | "starting" | "running" | "error";
