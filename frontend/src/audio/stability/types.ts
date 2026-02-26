import type { PitchFrame } from "../pitch/types";

export type { PitchFrame };

export type DriftDirection = "sharp" | "flat" | "stable";

export interface StabilityResult {
  /** Overall stability score, 0–100 */
  stability_score: number;
  /** Instantaneous deviation in cents (positive = sharp, negative = flat) */
  current_deviation_cents: number;
  /** Drift direction based on rolling mean */
  drift_direction: DriftDirection;
  /** Rolling mean deviation in cents */
  mean_deviation_cents: number;
  /** Rolling variance in cents squared */
  variance_cents: number;
  /** Number of accepted frames currently in the analysis window */
  window_frame_count: number;
}

export interface StabilityAnalyzerConfig {
  /** Target frequency in Hz */
  targetFrequency: number;
  /** Analysis window duration in seconds */
  windowDuration: number;
  /** Expected frames per second from pitch detector */
  framesPerSecond: number;
  /** Minimum confidence to accept a frame */
  minConfidence: number;
  /** Reject frames with |cents| > this value (matches backend intonation_inclusion_st) */
  inclusionRadiusCents: number;
  /** Cents threshold below which drift is labeled "stable" */
  stableBandCents: number;
}
