/**
 * Unit tests for YIN pitch detection algorithm.
 *
 * These tests duplicate the pure-math YIN functions from
 * pitch-processor.js as TypeScript, since the AudioWorklet
 * processor can't be imported directly in Node.
 */
import { describe, it, expect } from "vitest";

// ── YIN functions (duplicated from pitch-processor.js) ──────

function differenceFn(frame: Float32Array, maxLag: number): Float32Array {
  const n = frame.length;
  const diff = new Float32Array(maxLag + 1);
  diff[0] = 0;

  for (let tau = 1; tau <= maxLag; tau++) {
    let sum = 0;
    const w = n - tau;
    for (let j = 0; j < w; j++) {
      const delta = frame[j] - frame[j + tau];
      sum += delta * delta;
    }
    diff[tau] = sum;
  }

  return diff;
}

function cmnd(diff: Float32Array): Float32Array {
  const result = new Float32Array(diff.length);
  result[0] = 1.0;
  let runningSum = 0;

  for (let tau = 1; tau < diff.length; tau++) {
    runningSum += diff[tau];
    result[tau] = runningSum > 0 ? (diff[tau] * tau) / runningSum : 1.0;
  }

  return result;
}

function absoluteThreshold(cmndArr: Float32Array, threshold: number): number {
  let tau = 2;
  while (tau < cmndArr.length - 1) {
    if (cmndArr[tau] < threshold) {
      while (tau + 1 < cmndArr.length && cmndArr[tau + 1] < cmndArr[tau]) {
        tau++;
      }
      return tau;
    }
    tau++;
  }
  return 0;
}

function parabolicInterp(cmndArr: Float32Array, tau: number): number {
  if (tau <= 0 || tau >= cmndArr.length - 1) {
    return tau;
  }

  const alpha = cmndArr[tau - 1];
  const beta = cmndArr[tau];
  const gamma = cmndArr[tau + 1];

  const denom = 2.0 * (alpha - 2.0 * beta + gamma);
  if (Math.abs(denom) < 1e-12) {
    return tau;
  }

  return tau + (alpha - gamma) / denom;
}

// ── Helper: full YIN pipeline ───────────────────────────────

function yinPitch(
  frame: Float32Array,
  sampleRate: number,
  threshold: number,
  freqMin: number,
  freqMax: number
): { frequency: number; confidence: number } {
  const n = frame.length;
  const minLag = Math.max(2, Math.floor(sampleRate / freqMax));
  const maxLag = Math.min(Math.floor(n / 2), Math.floor(sampleRate / freqMin));

  if (maxLag <= minLag) {
    return { frequency: 0, confidence: 0 };
  }

  // Silence gate
  let sumSq = 0;
  for (let i = 0; i < n; i++) {
    sumSq += frame[i] * frame[i];
  }
  const rms = Math.sqrt(sumSq / n);
  if (rms < 1e-4) {
    return { frequency: 0, confidence: 0 };
  }

  const diff = differenceFn(frame, maxLag);
  const dPrime = cmnd(diff);

  // Mask out lags below freq_max
  for (let i = 0; i < minLag; i++) {
    dPrime[i] = 1.0;
  }

  const tau = absoluteThreshold(dPrime, threshold);
  if (tau === 0) {
    return { frequency: 0, confidence: 0 };
  }

  const refinedTau = parabolicInterp(dPrime, tau);
  if (refinedTau <= 0) {
    return { frequency: 0, confidence: 0 };
  }

  const freq = sampleRate / refinedTau;
  const confidence = 1.0 - dPrime[tau];

  if (freq < freqMin || freq > freqMax) {
    return { frequency: 0, confidence: 0 };
  }

  return {
    frequency: freq,
    confidence: Math.max(0, Math.min(1, confidence)),
  };
}

// ── Helper: generate a sine wave ────────────────────────────

function generateSine(
  freq: number,
  sampleRate: number,
  duration: number,
  amplitude = 0.8
): Float32Array {
  const n = Math.floor(sampleRate * duration);
  const buf = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    buf[i] = amplitude * Math.sin((2 * Math.PI * freq * i) / sampleRate);
  }
  return buf;
}

// ── Tests ───────────────────────────────────────────────────

const SR = 16000;
const THRESHOLD = 0.12;
const FRAME = 2048;

describe("YIN pitch detection", () => {
  it("detects 440Hz (A4) accurately with high confidence", () => {
    const signal = generateSine(440, SR, FRAME / SR);
    const result = yinPitch(signal, SR, THRESHOLD, 50, 4000);

    expect(result.frequency).toBeGreaterThan(435);
    expect(result.frequency).toBeLessThan(445);
    expect(result.confidence).toBeGreaterThan(0.9);
  });

  it("detects 293Hz (D4, lowest erhu note) accurately", () => {
    const signal = generateSine(293, SR, FRAME / SR);
    const result = yinPitch(signal, SR, THRESHOLD, 260, 2400);

    expect(result.frequency).toBeGreaterThan(288);
    expect(result.frequency).toBeLessThan(298);
    expect(result.confidence).toBeGreaterThan(0.9);
  });

  it("detects 2349Hz (D7, highest erhu note) accurately", () => {
    // Need longer frame for high frequency stability
    const signal = generateSine(2349, SR, FRAME / SR);
    const result = yinPitch(signal, SR, THRESHOLD, 260, 2400);

    expect(result.frequency).toBeGreaterThan(2300);
    expect(result.frequency).toBeLessThan(2400);
    expect(result.confidence).toBeGreaterThan(0.8);
  });

  it("returns zero frequency for silence", () => {
    const silence = new Float32Array(FRAME); // all zeros
    const result = yinPitch(silence, SR, THRESHOLD, 260, 2400);

    expect(result.frequency).toBe(0);
    expect(result.confidence).toBe(0);
  });

  it("returns zero frequency for white noise (below threshold)", () => {
    const noise = new Float32Array(FRAME);
    // Deterministic pseudo-random noise
    let seed = 42;
    for (let i = 0; i < FRAME; i++) {
      seed = (seed * 1103515245 + 12345) & 0x7fffffff;
      noise[i] = ((seed / 0x7fffffff) * 2 - 1) * 0.5;
    }
    const result = yinPitch(noise, SR, THRESHOLD, 260, 2400);

    expect(result.frequency).toBe(0);
  });

  it("detects vibrato center frequency near 440Hz (median of multiple frames)", () => {
    // 440Hz with ±1 semitone vibrato at 5Hz — simulate streaming with overlapping frames
    // Generate 0.5s of vibrato signal, extract multiple frames, median should center near 440Hz
    const duration = 0.5;
    const totalSamples = Math.floor(SR * duration);
    const fullSignal = new Float32Array(totalSamples);
    const vibratoRate = 5;
    const vibratoDepth = 1; // semitone

    // Proper FM synthesis: integrate instantaneous frequency for phase
    let phase = 0;
    for (let i = 0; i < totalSamples; i++) {
      const t = i / SR;
      const semitoneOffset =
        vibratoDepth * Math.sin(2 * Math.PI * vibratoRate * t);
      const instFreq = 440 * Math.pow(2, semitoneOffset / 12);
      phase += (2 * Math.PI * instFreq) / SR;
      fullSignal[i] = 0.8 * Math.sin(phase);
    }

    // Extract overlapping frames (hop = 320 samples) and detect pitch for each
    const hop = 320;
    const detectedFreqs: number[] = [];

    for (let start = 0; start + FRAME <= totalSamples; start += hop) {
      const frame = fullSignal.slice(start, start + FRAME);
      const result = yinPitch(frame, SR, THRESHOLD, 260, 2400);
      if (result.frequency > 0) {
        detectedFreqs.push(result.frequency);
      }
    }

    // Should detect pitch in most frames
    expect(detectedFreqs.length).toBeGreaterThan(3);

    // Median should be near 440Hz
    detectedFreqs.sort((a, b) => a - b);
    const median = detectedFreqs[Math.floor(detectedFreqs.length / 2)];

    expect(median).toBeGreaterThan(415); // 440 - 1 semitone
    expect(median).toBeLessThan(466); // 440 + 1 semitone
  });

  it("detects multiple frequencies across the erhu range", () => {
    const testFreqs = [330, 440, 587, 880, 1175, 1760];

    for (const freq of testFreqs) {
      const signal = generateSine(freq, SR, FRAME / SR);
      const result = yinPitch(signal, SR, THRESHOLD, 260, 2400);

      const tolerance = freq * 0.02; // 2% tolerance
      expect(result.frequency).toBeGreaterThan(freq - tolerance);
      expect(result.frequency).toBeLessThan(freq + tolerance);
      expect(result.confidence).toBeGreaterThan(0.85);
    }
  });
});

describe("YIN sub-functions", () => {
  it("difference function produces zero at lag 0", () => {
    const signal = generateSine(440, SR, 0.05);
    const diff = differenceFn(signal, 100);
    expect(diff[0]).toBe(0);
  });

  it("CMND normalizes to 1.0 at lag 0", () => {
    const signal = generateSine(440, SR, 0.05);
    const diff = differenceFn(signal, 100);
    const normalized = cmnd(diff);
    expect(normalized[0]).toBe(1.0);
  });

  it("CMND shows dip near expected period for sine wave", () => {
    const freq = 440;
    const expectedLag = Math.round(SR / freq); // ~36
    const signal = generateSine(freq, SR, FRAME / SR);
    const diff = differenceFn(signal, 100);
    const normalized = cmnd(diff);

    // Should have a clear dip near the expected lag
    const dip = normalized[expectedLag];
    expect(dip).toBeLessThan(0.1);
  });

  it("parabolic interpolation refines integer lag", () => {
    // Create a synthetic CMND with minimum between two integer lags
    const arr = new Float32Array(5);
    arr[0] = 1.0;
    arr[1] = 0.5;
    arr[2] = 0.1; // minimum
    arr[3] = 0.3;
    arr[4] = 0.8;

    const refined = parabolicInterp(arr, 2);
    // Should be slightly offset from 2
    expect(refined).not.toBe(2);
    expect(refined).toBeGreaterThan(1.5);
    expect(refined).toBeLessThan(2.5);
  });
});
