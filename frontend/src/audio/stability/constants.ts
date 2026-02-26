import type { StabilityAnalyzerConfig } from "./types";

export const DEFAULT_STABILITY_CONFIG: Omit<StabilityAnalyzerConfig, "targetFrequency"> = {
  windowDuration: 2.0,
  framesPerSecond: 50,
  minConfidence: 0.5,
  inclusionRadiusCents: 150,
  stableBandCents: 15,
};

/** Scoring weights */
export const DRIFT_WEIGHT = 0.65;
export const VARIANCE_WEIGHT = 0.35;

/** Drift score: linear ramp from 10 to 80 cents */
export const DRIFT_FLOOR_CENTS = 10;
export const DRIFT_CEIL_CENTS = 80;

/** Variance score: linear ramp from 450 to 2500 cents² */
export const VARIANCE_FLOOR = 450;
export const VARIANCE_CEIL = 2500;
