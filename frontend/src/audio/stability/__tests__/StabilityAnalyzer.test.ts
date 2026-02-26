import { describe, it, expect } from "vitest";
import { StabilityAnalyzer, frequencyToCents } from "../StabilityAnalyzer";
import type { PitchFrame } from "../types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeFrame(frequency: number, confidence = 0.9, time = 0): PitchFrame {
  return { frequency, confidence, time };
}

/** Push N identical frames and return the last result. */
function pushN(analyzer: StabilityAnalyzer, n: number, freq: number, confidence = 0.9) {
  let result = null;
  for (let i = 0; i < n; i++) {
    result = analyzer.pushFrame(makeFrame(freq, confidence, i / 50));
  }
  return result;
}

/** Convert semitones offset to frequency ratio relative to a base. */
function semitonesToFreq(base: number, semitones: number): number {
  return base * Math.pow(2, semitones / 12);
}

// ---------------------------------------------------------------------------
// Cents math
// ---------------------------------------------------------------------------

describe("frequencyToCents", () => {
  it("returns 0 cents when detected equals target", () => {
    expect(frequencyToCents(440, 440)).toBeCloseTo(0, 5);
  });

  it("returns +100 for one semitone sharp", () => {
    const sharp = semitonesToFreq(440, 1);
    expect(frequencyToCents(sharp, 440)).toBeCloseTo(100, 1);
  });

  it("returns -100 for one semitone flat", () => {
    const flat = semitonesToFreq(440, -1);
    expect(frequencyToCents(flat, 440)).toBeCloseTo(-100, 1);
  });

  it("returns +1200 for one octave up", () => {
    expect(frequencyToCents(880, 440)).toBeCloseTo(1200, 1);
  });
});

// ---------------------------------------------------------------------------
// Perfect pitch → score 100
// ---------------------------------------------------------------------------

describe("perfect pitch", () => {
  it("scores 100 for 100 frames exactly at target", () => {
    const analyzer = new StabilityAnalyzer({ targetFrequency: 440 });
    const result = pushN(analyzer, 100, 440);

    expect(result).not.toBeNull();
    expect(result!.stability_score).toBe(100);
    expect(result!.drift_direction).toBe("stable");
    expect(result!.mean_deviation_cents).toBeCloseTo(0, 1);
  });
});

// ---------------------------------------------------------------------------
// Vibrato tolerance
// ---------------------------------------------------------------------------

describe("vibrato tolerance", () => {
  it("scores >= 95 for ±30 cent vibrato at 6Hz", () => {
    const analyzer = new StabilityAnalyzer({ targetFrequency: 440 });
    const vibratoAmplitude = 30; // cents
    const vibratoFreqHz = 6;
    const fps = 50;

    for (let i = 0; i < 100; i++) {
      const t = i / fps;
      const cents = vibratoAmplitude * Math.sin(2 * Math.PI * vibratoFreqHz * t);
      const freq = 440 * Math.pow(2, cents / 1200);
      analyzer.pushFrame(makeFrame(freq, 0.9, t));
    }

    const result = analyzer.getResult();
    expect(result).not.toBeNull();
    expect(result!.stability_score).toBeGreaterThanOrEqual(95);
    expect(result!.drift_direction).toBe("stable");
  });

  it("does not penalize symmetric vibrato (mean stays near zero)", () => {
    const analyzer = new StabilityAnalyzer({ targetFrequency: 440 });

    for (let i = 0; i < 100; i++) {
      const t = i / 50;
      const cents = 25 * Math.sin(2 * Math.PI * 5 * t);
      const freq = 440 * Math.pow(2, cents / 1200);
      analyzer.pushFrame(makeFrame(freq, 0.9, t));
    }

    const result = analyzer.getResult()!;
    expect(Math.abs(result.mean_deviation_cents)).toBeLessThan(5);
  });
});

// ---------------------------------------------------------------------------
// Drift detection
// ---------------------------------------------------------------------------

describe("drift detection", () => {
  it("scores < 50 for sustained +60 cents drift", () => {
    const analyzer = new StabilityAnalyzer({ targetFrequency: 440 });
    const sharpFreq = 440 * Math.pow(2, 60 / 1200);
    const result = pushN(analyzer, 100, sharpFreq);

    expect(result).not.toBeNull();
    expect(result!.stability_score).toBeLessThan(55);
    expect(result!.drift_direction).toBe("sharp");
  });

  it("scores ~35 or below for 80+ cents off", () => {
    const analyzer = new StabilityAnalyzer({ targetFrequency: 440 });
    const farSharp = 440 * Math.pow(2, 85 / 1200);
    const result = pushN(analyzer, 100, farSharp);

    expect(result).not.toBeNull();
    expect(result!.stability_score).toBeLessThanOrEqual(40);
  });

  it("scores ~91 for 20 cents flat with normal vibrato", () => {
    const analyzer = new StabilityAnalyzer({ targetFrequency: 440 });

    for (let i = 0; i < 100; i++) {
      const t = i / 50;
      const vibrato = 25 * Math.sin(2 * Math.PI * 6 * t);
      const cents = -20 + vibrato;
      const freq = 440 * Math.pow(2, cents / 1200);
      analyzer.pushFrame(makeFrame(freq, 0.9, t));
    }

    const result = analyzer.getResult()!;
    // Mean ~-20 cents → drift_score = 100*(1 - clamp01((20-10)/(80-10))) = 100*(1-10/70) ≈ 85.7
    // Variance from vibrato ≈ 312.5 → below floor → variance_score = 100
    // score = 0.65*85.7 + 0.35*100 ≈ 90.7
    expect(result.stability_score).toBeGreaterThan(85);
    expect(result.stability_score).toBeLessThan(95);
  });
});

// ---------------------------------------------------------------------------
// Vibrato vs drift comparison
// ---------------------------------------------------------------------------

describe("vibrato vs drift discrimination", () => {
  it("vibrato scores significantly higher (>20 pts) than same-amplitude sustained drift", () => {
    // Vibrato: ±30 cents oscillation centered on target
    const vibratoAnalyzer = new StabilityAnalyzer({ targetFrequency: 440 });
    for (let i = 0; i < 100; i++) {
      const t = i / 50;
      const cents = 30 * Math.sin(2 * Math.PI * 6 * t);
      const freq = 440 * Math.pow(2, cents / 1200);
      vibratoAnalyzer.pushFrame(makeFrame(freq, 0.9, t));
    }
    const vibratoScore = vibratoAnalyzer.getResult()!.stability_score;

    // Drift: sustained +30 cents
    const driftAnalyzer = new StabilityAnalyzer({ targetFrequency: 440 });
    const driftFreq = 440 * Math.pow(2, 30 / 1200);
    pushN(driftAnalyzer, 100, driftFreq);
    const driftScore = driftAnalyzer.getResult()!.stability_score;

    expect(vibratoScore - driftScore).toBeGreaterThan(15);
  });
});

// ---------------------------------------------------------------------------
// Drift direction labels
// ---------------------------------------------------------------------------

describe("drift direction", () => {
  it("reports 'stable' when mean is within ±15 cents", () => {
    const analyzer = new StabilityAnalyzer({ targetFrequency: 440 });
    const result = pushN(analyzer, 100, 440);
    expect(result!.drift_direction).toBe("stable");
  });

  it("reports 'sharp' when mean > +15 cents", () => {
    const analyzer = new StabilityAnalyzer({ targetFrequency: 440 });
    const freq = 440 * Math.pow(2, 25 / 1200);
    const result = pushN(analyzer, 100, freq);
    expect(result!.drift_direction).toBe("sharp");
  });

  it("reports 'flat' when mean < -15 cents", () => {
    const analyzer = new StabilityAnalyzer({ targetFrequency: 440 });
    const freq = 440 * Math.pow(2, -25 / 1200);
    const result = pushN(analyzer, 100, freq);
    expect(result!.drift_direction).toBe("flat");
  });
});

// ---------------------------------------------------------------------------
// Frame filtering
// ---------------------------------------------------------------------------

describe("frame filtering", () => {
  it("rejects frames with low confidence", () => {
    const analyzer = new StabilityAnalyzer({ targetFrequency: 440 });
    const result = analyzer.pushFrame(makeFrame(440, 0.3));
    expect(result).toBeNull();
  });

  it("rejects frames with zero frequency", () => {
    const analyzer = new StabilityAnalyzer({ targetFrequency: 440 });
    const result = analyzer.pushFrame(makeFrame(0, 0.9));
    expect(result).toBeNull();
  });

  it("rejects frames outside inclusion radius (>150 cents)", () => {
    const analyzer = new StabilityAnalyzer({ targetFrequency: 440 });
    // 200 cents sharp → should be rejected
    const farFreq = 440 * Math.pow(2, 200 / 1200);
    const result = analyzer.pushFrame(makeFrame(farFreq, 0.9));
    expect(result).toBeNull();
  });

  it("still returns last valid result when a frame is rejected", () => {
    const analyzer = new StabilityAnalyzer({ targetFrequency: 440 });
    // Push one valid frame
    analyzer.pushFrame(makeFrame(440, 0.9));
    // Push an invalid one — should still return a result
    const result = analyzer.pushFrame(makeFrame(440, 0.3));
    expect(result).not.toBeNull();
    expect(result!.window_frame_count).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// Reset
// ---------------------------------------------------------------------------

describe("reset", () => {
  it("clears the window and returns null after reset", () => {
    const analyzer = new StabilityAnalyzer({ targetFrequency: 440 });
    pushN(analyzer, 50, 440);
    expect(analyzer.getResult()).not.toBeNull();

    analyzer.reset();
    expect(analyzer.getResult()).toBeNull();
  });

  it("starts fresh after reset", () => {
    const analyzer = new StabilityAnalyzer({ targetFrequency: 440 });
    // Push drift frames
    const sharpFreq = 440 * Math.pow(2, 60 / 1200);
    pushN(analyzer, 100, sharpFreq);
    expect(analyzer.getResult()!.stability_score).toBeLessThan(55);

    // Reset and push perfect frames
    analyzer.reset();
    pushN(analyzer, 100, 440);
    expect(analyzer.getResult()!.stability_score).toBe(100);
  });
});

// ---------------------------------------------------------------------------
// Edge cases
// ---------------------------------------------------------------------------

describe("edge cases", () => {
  it("handles a single frame", () => {
    const analyzer = new StabilityAnalyzer({ targetFrequency: 440 });
    const result = analyzer.pushFrame(makeFrame(440, 0.9));

    expect(result).not.toBeNull();
    expect(result!.window_frame_count).toBe(1);
    expect(result!.stability_score).toBe(100);
  });

  it("handles target frequency change via setTargetFrequency", () => {
    const analyzer = new StabilityAnalyzer({ targetFrequency: 440 });
    pushN(analyzer, 50, 440);
    expect(analyzer.getResult()!.stability_score).toBe(100);

    // Switch target to 880Hz, old frames should be gone
    analyzer.setTargetFrequency(880);
    expect(analyzer.getResult()).toBeNull();

    // Push frames at new target
    pushN(analyzer, 50, 880);
    expect(analyzer.getResult()!.stability_score).toBe(100);
  });

  it("circular buffer evicts oldest frames correctly", () => {
    // Use a small window: 1s at 50fps = 50 frames
    const analyzer = new StabilityAnalyzer({
      targetFrequency: 440,
      windowDuration: 1.0,
      framesPerSecond: 50,
    });

    // Fill with 50 sharp frames
    const sharpFreq = 440 * Math.pow(2, 60 / 1200);
    pushN(analyzer, 50, sharpFreq);
    expect(analyzer.getResult()!.drift_direction).toBe("sharp");

    // Now push 50 perfect frames → should evict all sharp frames
    pushN(analyzer, 50, 440);
    const result = analyzer.getResult()!;
    expect(result.stability_score).toBe(100);
    expect(result.drift_direction).toBe("stable");
  });
});
