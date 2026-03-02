import { describe, it, expect } from "vitest";
import {
  JianpuCurveGenerator,
  midiToFrequency,
  degreeToFrequency,
  parseJianpu,
} from "../JianpuCurveGenerator";

// ── MIDI / frequency helpers ────────────────────────────────

describe("midiToFrequency", () => {
  it("converts A4 (MIDI 69) to 440 Hz", () => {
    expect(midiToFrequency(69)).toBeCloseTo(440, 1);
  });

  it("converts D4 (MIDI 62) correctly", () => {
    expect(midiToFrequency(62)).toBeCloseTo(293.66, 1);
  });

  it("converts C4 (MIDI 60) correctly", () => {
    expect(midiToFrequency(60)).toBeCloseTo(261.63, 1);
  });
});

describe("degreeToFrequency", () => {
  it("degree 1 in D major = D4 (293.66 Hz)", () => {
    const freq = degreeToFrequency(1, 0, "D", 4);
    expect(freq).toBeCloseTo(293.66, 1);
  });

  it("degree 2 in D major = E4 (329.63 Hz)", () => {
    const freq = degreeToFrequency(2, 0, "D", 4);
    expect(freq).toBeCloseTo(329.63, 1);
  });

  it("degree 3 in D major = F#4 (369.99 Hz)", () => {
    const freq = degreeToFrequency(3, 0, "D", 4);
    expect(freq).toBeCloseTo(369.99, 0);
  });

  it("degree 5 in D major = A4 (440 Hz)", () => {
    const freq = degreeToFrequency(5, 0, "D", 4);
    expect(freq).toBeCloseTo(440.0, 1);
  });

  it("degree 1 with octave up = D5 (587.33 Hz)", () => {
    const freq = degreeToFrequency(1, 1, "D", 4);
    expect(freq).toBeCloseTo(587.33, 1);
  });

  it("degree 1 in C major = C4 (261.63 Hz)", () => {
    const freq = degreeToFrequency(1, 0, "C", 4);
    expect(freq).toBeCloseTo(261.63, 1);
  });

  it("degree 6 in F major = D5 (587.33 Hz)", () => {
    // Matches backend jianpu.py: degree=6, tonic=F, octave 4
    // F4=MIDI 65, interval for 6=9 semitones → MIDI 74 = D5
    const freq = degreeToFrequency(6, 0, "F", 4);
    expect(freq).toBeCloseTo(587.33, 1);
  });

  it("returns 0 for invalid degree", () => {
    expect(degreeToFrequency(0, 0, "D", 4)).toBe(0);
    expect(degreeToFrequency(8, 0, "D", 4)).toBe(0);
  });

  it("returns 0 for unknown tonic", () => {
    expect(degreeToFrequency(1, 0, "X", 4)).toBe(0);
  });
});

// ── Parser ──────────────────────────────────────────────────

describe("parseJianpu", () => {
  it("parses simple quarter notes", () => {
    const { notes, measureCount } = parseJianpu("1 2 3 4", 4);
    expect(notes).toHaveLength(4);
    expect(notes[0]).toEqual({ degree: 1, octaveShift: 0, beats: 1 });
    expect(notes[3]).toEqual({ degree: 4, octaveShift: 0, beats: 1 });
    expect(measureCount).toBe(1);
  });

  it("parses bar lines and counts measures", () => {
    const { notes, measureCount } = parseJianpu("1 2 3 4 | 5 6 7 1", 4);
    expect(notes).toHaveLength(8);
    expect(measureCount).toBe(2);
  });

  it("parses rests (0)", () => {
    const { notes } = parseJianpu("1 0 3 0", 4);
    expect(notes[1].degree).toBe(0);
    expect(notes[3].degree).toBe(0);
  });

  it("parses sustain dashes", () => {
    const { notes } = parseJianpu("5 - - -", 4);
    expect(notes).toHaveLength(4);
    expect(notes[0].degree).toBe(5);
    expect(notes[1].degree).toBe(-1); // sustain
    expect(notes[2].degree).toBe(-1);
    expect(notes[3].degree).toBe(-1);
  });

  it("parses grouped eighth notes", () => {
    const { notes } = parseJianpu("12 34", 4);
    expect(notes).toHaveLength(4);
    expect(notes[0].beats).toBe(0.5);
    expect(notes[1].beats).toBe(0.5);
  });

  it("parses grouped sixteenth notes", () => {
    const { notes } = parseJianpu("1234", 4);
    expect(notes).toHaveLength(4);
    expect(notes[0].beats).toBe(0.25);
  });

  it("parses triplets", () => {
    const { notes } = parseJianpu("123", 4);
    expect(notes).toHaveLength(3);
    expect(notes[0].beats).toBeCloseTo(1 / 3, 5);
  });

  // ── Mixed subdivisions (parenthesized sub-groups) ──────────

  it("parses 1(23) as eighth + two sixteenths", () => {
    const { notes } = parseJianpu("1(23)", 4);
    expect(notes).toHaveLength(3);
    expect(notes[0].beats).toBeCloseTo(0.5, 5);   // bare "1" = 1/2
    expect(notes[1].beats).toBeCloseTo(0.25, 5);   // sub "2" = (1/2)/2
    expect(notes[2].beats).toBeCloseTo(0.25, 5);   // sub "3" = (1/2)/2
  });

  it("parses (12)3 as two sixteenths + eighth", () => {
    const { notes } = parseJianpu("(12)3", 4);
    expect(notes).toHaveLength(3);
    expect(notes[0].beats).toBeCloseTo(0.25, 5);
    expect(notes[1].beats).toBeCloseTo(0.25, 5);
    expect(notes[2].beats).toBeCloseTo(0.5, 5);
  });

  it("parses 1(234) as eighth + three sub-notes", () => {
    const { notes } = parseJianpu("1(234)", 4);
    expect(notes).toHaveLength(4);
    expect(notes[0].beats).toBeCloseTo(0.5, 5);
    const subBeat = 0.5 / 3;
    expect(notes[1].beats).toBeCloseTo(subBeat, 5);
    expect(notes[2].beats).toBeCloseTo(subBeat, 5);
    expect(notes[3].beats).toBeCloseTo(subBeat, 5);
  });

  it("parses (12)(34) as four sixteenths", () => {
    const { notes } = parseJianpu("(12)(34)", 4);
    expect(notes).toHaveLength(4);
    for (const n of notes) {
      expect(n.beats).toBeCloseTo(0.25, 5);
    }
  });

  it("1(23) total beats sum to 1.0", () => {
    const { notes } = parseJianpu("1(23)", 4);
    const total = notes.reduce((sum, n) => sum + n.beats, 0);
    expect(total).toBeCloseTo(1.0, 5);
  });

  it("backward compat: 12 still gives two eighths", () => {
    const { notes } = parseJianpu("12", 4);
    expect(notes).toHaveLength(2);
    expect(notes[0].beats).toBe(0.5);
    expect(notes[1].beats).toBe(0.5);
  });

  it("mixed group in context: 1 1(23) 4", () => {
    const { notes } = parseJianpu("1 1(23) 4", 4);
    expect(notes).toHaveLength(5);
    // First quarter note
    expect(notes[0].beats).toBe(1);
    expect(notes[0].degree).toBe(1);
    // Mixed group
    expect(notes[1].beats).toBeCloseTo(0.5, 5);
    expect(notes[2].beats).toBeCloseTo(0.25, 5);
    expect(notes[3].beats).toBeCloseTo(0.25, 5);
    // Last quarter note
    expect(notes[4].beats).toBe(1);
    expect(notes[4].degree).toBe(4);
  });

  it("rests inside sub-groups: 1(03)", () => {
    const { notes } = parseJianpu("1(03)", 4);
    expect(notes).toHaveLength(3);
    expect(notes[0].degree).toBe(1);
    expect(notes[0].beats).toBeCloseTo(0.5, 5);
    expect(notes[1].degree).toBe(0); // rest
    expect(notes[1].beats).toBeCloseTo(0.25, 5);
    expect(notes[2].degree).toBe(3);
    expect(notes[2].beats).toBeCloseTo(0.25, 5);
  });
});

// ── Curve generation ────────────────────────────────────────

describe("JianpuCurveGenerator", () => {
  it("generates correct duration for simple 4-note phrase at 120 BPM", () => {
    const gen = new JianpuCurveGenerator({ tonic: "D", bpm: 120 });
    const result = gen.generate("1 2 3 4");

    // 4 beats × 0.5s/beat = 2.0s
    expect(result.duration).toBeCloseTo(2.0, 2);
    expect(result.measureCount).toBe(1);
    expect(result.notes).toHaveLength(4);
  });

  it("generates curve points at configured FPS", () => {
    const gen = new JianpuCurveGenerator({
      tonic: "D",
      bpm: 120,
      framesPerSecond: 50,
    });
    const result = gen.generate("1");

    // 1 beat at 120 BPM = 0.5s → 0.5 * 50 = 25 frames
    expect(result.curve.length).toBe(25);
    // All should be D4
    for (const pt of result.curve) {
      expect(pt.frequency).toBeCloseTo(293.66, 1);
    }
  });

  it("rests produce frequency 0", () => {
    const gen = new JianpuCurveGenerator({ tonic: "D", bpm: 120 });
    const result = gen.generate("0");

    expect(result.curve.length).toBeGreaterThan(0);
    for (const pt of result.curve) {
      expect(pt.frequency).toBe(0);
    }
  });

  it("sustain dashes continue previous frequency", () => {
    const gen = new JianpuCurveGenerator({
      tonic: "D",
      bpm: 120,
      framesPerSecond: 50,
    });
    const result = gen.generate("5 -");

    // 2 beats at 120 BPM = 1.0s → 50 frames
    expect(result.curve.length).toBe(50);
    // All frames should be A4 (440 Hz) — degree 5 in D major
    for (const pt of result.curve) {
      expect(pt.frequency).toBeCloseTo(440.0, 1);
    }
  });

  it("D major scale produces correct frequencies", () => {
    const gen = new JianpuCurveGenerator({
      tonic: "D",
      bpm: 60, // 1 beat = 1 second for easy math
      framesPerSecond: 10,
    });
    const result = gen.generate("1 2 3 4 5 6 7");

    const expected = [293.66, 329.63, 369.99, 392.0, 440.0, 493.88, 554.37];

    // Check first frame of each note
    for (let i = 0; i < 7; i++) {
      const frameIdx = i * 10; // 10 frames per note at 10fps, 1s per beat
      expect(result.curve[frameIdx].frequency).toBeCloseTo(expected[i], 0);
    }
  });

  it("handles bar lines correctly in timing", () => {
    const gen = new JianpuCurveGenerator({
      tonic: "D",
      bpm: 120,
      framesPerSecond: 50,
    });
    const result = gen.generate("1 2 | 3 4");

    // 4 notes × 0.5s = 2.0s regardless of bar lines
    expect(result.duration).toBeCloseTo(2.0, 2);
    expect(result.measureCount).toBe(2);
  });

  it("handles eighth note groups", () => {
    const gen = new JianpuCurveGenerator({
      tonic: "D",
      bpm: 120,
      framesPerSecond: 50,
    });
    const result = gen.generate("12 34");

    // 4 eighth notes = 2 beats = 1.0s
    expect(result.duration).toBeCloseTo(1.0, 2);
    expect(result.notes).toHaveLength(4);
    // All have 0.5 beat duration
    for (const n of result.notes) {
      expect(n.beats).toBe(0.5);
    }
  });

  it("handles empty input", () => {
    const gen = new JianpuCurveGenerator();
    const result = gen.generate("");

    expect(result.curve).toHaveLength(0);
    expect(result.duration).toBe(0);
  });

  it("toReferenceCurve returns [time, frequency] tuples", () => {
    const gen = new JianpuCurveGenerator({ tonic: "D", bpm: 120 });
    const curve = gen.toReferenceCurve("1 2");

    expect(curve.length).toBeGreaterThan(0);
    for (const [time, freq] of curve) {
      expect(typeof time).toBe("number");
      expect(typeof freq).toBe("number");
    }
  });

  it("getFrequency returns correct frequency for given degree", () => {
    const gen = new JianpuCurveGenerator({ tonic: "D" });

    expect(gen.getFrequency(1)).toBeCloseTo(293.66, 1);
    expect(gen.getFrequency(5)).toBeCloseTo(440.0, 1);
    expect(gen.getFrequency(1, 1)).toBeCloseTo(587.33, 1);
  });

  it("curve timestamps are monotonically increasing", () => {
    const gen = new JianpuCurveGenerator({ tonic: "D", bpm: 120 });
    const result = gen.generate("1 2 3 4 | 5 - 5 -");

    for (let i = 1; i < result.curve.length; i++) {
      expect(result.curve[i].time).toBeGreaterThanOrEqual(result.curve[i - 1].time);
    }
  });

  it("different BPM produces different durations", () => {
    const fast = new JianpuCurveGenerator({ tonic: "D", bpm: 240 });
    const slow = new JianpuCurveGenerator({ tonic: "D", bpm: 60 });

    const fastResult = fast.generate("1 2 3 4");
    const slowResult = slow.generate("1 2 3 4");

    // 240 BPM = 0.25s/beat × 4 = 1.0s
    // 60 BPM = 1.0s/beat × 4 = 4.0s
    expect(fastResult.duration).toBeCloseTo(1.0, 2);
    expect(slowResult.duration).toBeCloseTo(4.0, 2);
  });
});
