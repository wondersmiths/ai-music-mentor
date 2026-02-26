import type { PitchFrame, StabilityResult, StabilityAnalyzerConfig, DriftDirection } from "./types";
import {
  DEFAULT_STABILITY_CONFIG,
  DRIFT_WEIGHT,
  VARIANCE_WEIGHT,
  DRIFT_FLOOR_CENTS,
  DRIFT_CEIL_CENTS,
  VARIANCE_FLOOR,
  VARIANCE_CEIL,
} from "./constants";

function clamp01(x: number): number {
  return Math.min(1, Math.max(0, x));
}

/**
 * Convert detected frequency to cents deviation from a target frequency.
 * Positive = sharp, negative = flat.
 */
export function frequencyToCents(detected: number, target: number): number {
  return 1200 * Math.log2(detected / target);
}

export class StabilityAnalyzer {
  private config: StabilityAnalyzerConfig;
  private bufferSize: number;

  // Circular buffer of cents deviations
  private buffer: number[];
  private head = 0;
  private count = 0;

  // Running sums for O(1) mean/variance
  private sum = 0;
  private sumSq = 0;

  // Last raw deviation for instantaneous readout
  private lastCents = 0;

  constructor(config: Partial<StabilityAnalyzerConfig> & { targetFrequency: number }) {
    this.config = { ...DEFAULT_STABILITY_CONFIG, ...config };
    this.bufferSize = Math.round(this.config.windowDuration * this.config.framesPerSecond);
    this.buffer = new Array<number>(this.bufferSize).fill(0);
  }

  /** Push a pitch frame from the detector. Returns the updated result if frame was accepted. */
  pushFrame(frame: PitchFrame): StabilityResult | null {
    // Gate: reject low-confidence or zero-frequency frames
    if (frame.frequency <= 0 || frame.confidence < this.config.minConfidence) {
      return this.count > 0 ? this.computeResult() : null;
    }

    const cents = frequencyToCents(frame.frequency, this.config.targetFrequency);

    // Gate: reject outliers beyond inclusion radius
    if (Math.abs(cents) > this.config.inclusionRadiusCents) {
      return this.count > 0 ? this.computeResult() : null;
    }

    this.lastCents = cents;
    this.addToBuffer(cents);
    return this.computeResult();
  }

  /** Get the current result without pushing a new frame. */
  getResult(): StabilityResult | null {
    return this.count > 0 ? this.computeResult() : null;
  }

  /** Clear the analysis window. */
  reset(): void {
    this.head = 0;
    this.count = 0;
    this.sum = 0;
    this.sumSq = 0;
    this.lastCents = 0;
    this.buffer.fill(0);
  }

  /** Update the target frequency and reset the window. */
  setTargetFrequency(freq: number): void {
    this.config.targetFrequency = freq;
    this.reset();
  }

  private addToBuffer(cents: number): void {
    if (this.count === this.bufferSize) {
      // Evict oldest value
      const old = this.buffer[this.head];
      this.sum -= old;
      this.sumSq -= old * old;
    } else {
      this.count++;
    }

    this.buffer[this.head] = cents;
    this.sum += cents;
    this.sumSq += cents * cents;
    this.head = (this.head + 1) % this.bufferSize;
  }

  private computeResult(): StabilityResult {
    const mean = this.sum / this.count;
    const variance = this.sumSq / this.count - mean * mean;

    // Drift score: penalizes sustained offset from target
    const driftScore = 100 * (1 - clamp01((Math.abs(mean) - DRIFT_FLOOR_CENTS) / (DRIFT_CEIL_CENTS - DRIFT_FLOOR_CENTS)));

    // Variance score: penalizes spread beyond normal vibrato range
    const varianceScore = 100 * (1 - clamp01((variance - VARIANCE_FLOOR) / (VARIANCE_CEIL - VARIANCE_FLOOR)));

    const score = DRIFT_WEIGHT * driftScore + VARIANCE_WEIGHT * varianceScore;

    // Drift direction
    let driftDirection: DriftDirection;
    if (Math.abs(mean) < this.config.stableBandCents) {
      driftDirection = "stable";
    } else {
      driftDirection = mean > 0 ? "sharp" : "flat";
    }

    return {
      stability_score: Math.round(score * 100) / 100,
      current_deviation_cents: Math.round(this.lastCents * 100) / 100,
      drift_direction: driftDirection,
      mean_deviation_cents: Math.round(mean * 100) / 100,
      variance_cents: Math.round(variance * 100) / 100,
      window_frame_count: this.count,
    };
  }
}
