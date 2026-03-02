/**
 * F5: Jianpu → continuous pitch curve generator.
 *
 * Parses a jianpu string (e.g. "1 2 3 4 | 5 - 5 -") and produces a
 * time-aligned frequency curve suitable for DTW comparison or guided practice.
 *
 * Jianpu format:
 *   - Digits 1–7: scale degrees
 *   - 0: rest (silence)
 *   - '-': sustain previous note for one beat
 *   - '|': bar line (ignored for timing, used for measure counting)
 *   - Spaces separate individual beats (quarter notes)
 *   - Grouped digits without spaces: beamed notes
 *     - 2 digits: eighth notes (0.5 beat each)
 *     - 4 digits: sixteenth notes (0.25 beat each)
 *     - 3 digits: triplets (~0.33 beat each)
 *
 * Example: "1 2 3 4 | 5 - 5 -"
 *   Key of D: D4 E4 F#4 G4 | A4 (held) A4 (held)
 */

import type {
  JianpuNote,
  JianpuCurveConfig,
  JianpuCurveResult,
  PitchPoint,
} from "./types";
import {
  DEFAULT_JIANPU_CONFIG,
  DEGREE_INTERVALS,
  TONIC_MIDI,
  A4_FREQUENCY,
  A4_MIDI,
} from "./constants";

// ── MIDI / frequency helpers ────────────────────────────────

/** Convert a MIDI note number to frequency in Hz. */
export function midiToFrequency(midi: number): number {
  return A4_FREQUENCY * Math.pow(2, (midi - A4_MIDI) / 12);
}

/** Convert a scale degree + octave shift to frequency, given tonic + base octave. */
export function degreeToFrequency(
  degree: number,
  octaveShift: number,
  tonic: string,
  baseOctave: number,
): number {
  if (degree < 1 || degree > 7) return 0;

  const tonicMidi = TONIC_MIDI[tonic];
  if (tonicMidi === undefined) return 0;

  // Adjust base MIDI for the requested octave (TONIC_MIDI is at octave 4)
  const octaveOffset = (baseOctave - 4) * 12;
  const interval = DEGREE_INTERVALS[degree] ?? 0;
  const midi = tonicMidi + octaveOffset + interval + octaveShift * 12;

  return midiToFrequency(midi);
}

// ── Parser ──────────────────────────────────────────────────

/** Parse a jianpu string into a list of JianpuNote tokens. */
export function parseJianpu(
  input: string,
  beatsPerMeasure: number,
): { notes: JianpuNote[]; measureCount: number } {
  const notes: JianpuNote[] = [];
  let measureCount = 1;

  // Split by bar lines first, then parse each segment
  const segments = input.split("|");

  for (let segIdx = 0; segIdx < segments.length; segIdx++) {
    if (segIdx > 0) measureCount++;

    const segment = segments[segIdx].trim();
    if (!segment) continue;

    // Split segment into space-separated groups
    const groups = segment.split(/\s+/);

    for (const group of groups) {
      if (!group) continue;
      parseGroup(group, notes);
    }
  }

  return { notes, measureCount };
}

/**
 * Try to parse a digit (0-7) with optional octave-shift markers starting at
 * `startIndex` in `group`. Returns the parsed note and the index after the
 * consumed characters, or `null` if no digit is found at `startIndex`.
 */
function tryParseDigitWithOctave(
  group: string,
  startIndex: number,
): { digit: number; octaveShift: number; nextIndex: number } | null {
  if (startIndex >= group.length) return null;
  const ch = group[startIndex];
  if (ch < "0" || ch > "7") return null;

  const digit = parseInt(ch, 10);
  let octaveShift = 0;

  let j = startIndex + 1;
  while (j < group.length) {
    if (group[j] === "\u0307" || group[j] === "̇") {
      octaveShift++;
      j++;
    } else if (group[j] === "\u0323" || group[j] === "̣") {
      octaveShift--;
      j++;
    } else if (group[j] === "'" || group[j] === "\u02D9") {
      octaveShift++;
      j++;
    } else if (group[j] === "," || group[j] === ".") {
      octaveShift--;
      j++;
    } else {
      break;
    }
  }

  return { digit, octaveShift, nextIndex: j };
}

/** Parse a group that contains no parentheses (original flat logic). */
function parseGroupFlat(group: string, notes: JianpuNote[]): void {
  const chars: { digit: number; octaveShift: number }[] = [];
  let i = 0;
  while (i < group.length) {
    const parsed = tryParseDigitWithOctave(group, i);
    if (parsed) {
      chars.push({ digit: parsed.digit, octaveShift: parsed.octaveShift });
      i = parsed.nextIndex;
    } else if (group[i] === "-") {
      notes.push({ degree: -1, octaveShift: 0, beats: 1 });
      i++;
    } else {
      i++;
    }
  }

  if (chars.length === 0) return;

  let beatsPerNote: number;
  if (chars.length === 1) {
    beatsPerNote = 1;
  } else if (chars.length === 2) {
    beatsPerNote = 0.5;
  } else if (chars.length === 3) {
    beatsPerNote = 1 / 3;
  } else {
    beatsPerNote = 0.25;
  }

  for (const { digit, octaveShift } of chars) {
    notes.push({ degree: digit, octaveShift, beats: beatsPerNote });
  }
}

type GroupElement = {
  kind: "bare" | "subgroup";
  notes: { digit: number; octaveShift: number }[];
};

/**
 * Tokenize a group string containing parentheses into top-level elements.
 * Bare digits become `{ kind: "bare", notes: [note] }`, content in `(...)`
 * becomes `{ kind: "subgroup", notes: [...] }`.
 */
function tokenizeGroupElements(group: string): GroupElement[] {
  const elements: GroupElement[] = [];
  let i = 0;

  while (i < group.length) {
    if (group[i] === "(") {
      // Collect notes inside parentheses
      i++; // skip '('
      const subNotes: { digit: number; octaveShift: number }[] = [];
      while (i < group.length && group[i] !== ")") {
        const parsed = tryParseDigitWithOctave(group, i);
        if (parsed) {
          subNotes.push({ digit: parsed.digit, octaveShift: parsed.octaveShift });
          i = parsed.nextIndex;
        } else {
          i++;
        }
      }
      if (i < group.length) i++; // skip ')'
      if (subNotes.length > 0) {
        elements.push({ kind: "subgroup", notes: subNotes });
      }
    } else {
      const parsed = tryParseDigitWithOctave(group, i);
      if (parsed) {
        elements.push({
          kind: "bare",
          notes: [{ digit: parsed.digit, octaveShift: parsed.octaveShift }],
        });
        i = parsed.nextIndex;
      } else if (group[i] === "-") {
        // Bare dash at top level — treat as sustain with proportional beat
        elements.push({
          kind: "bare",
          notes: [{ digit: -1, octaveShift: 0 }],
        });
        i++;
      } else {
        i++;
      }
    }
  }

  return elements;
}

function parseGroup(group: string, notes: JianpuNote[]): void {
  // Pure sustain dashes
  if (/^-+$/.test(group)) {
    for (const _ of group) {
      notes.push({ degree: 0, octaveShift: 0, beats: 1 });
      notes[notes.length - 1].degree = -1;
    }
    return;
  }

  // No parentheses → use original flat logic (backward compatible)
  if (!group.includes("(")) {
    parseGroupFlat(group, notes);
    return;
  }

  // Mixed subdivision: tokenize into top-level elements
  const elements = tokenizeGroupElements(group);
  if (elements.length === 0) return;

  const topN = elements.length;
  const beatsPerElement = 1 / topN;

  for (const elem of elements) {
    if (elem.kind === "bare") {
      const { digit, octaveShift } = elem.notes[0];
      notes.push({ degree: digit, octaveShift, beats: beatsPerElement });
    } else {
      // subgroup: each note gets an equal share of this element's beat allocation
      const subBeats = beatsPerElement / elem.notes.length;
      for (const { digit, octaveShift } of elem.notes) {
        notes.push({ degree: digit, octaveShift, beats: subBeats });
      }
    }
  }
}

// ── Curve generator ─────────────────────────────────────────

export class JianpuCurveGenerator {
  private config: JianpuCurveConfig;

  constructor(config?: Partial<JianpuCurveConfig>) {
    this.config = { ...DEFAULT_JIANPU_CONFIG, ...config };
  }

  /** Parse a jianpu string and generate a continuous pitch curve. */
  generate(input: string): JianpuCurveResult {
    const { tonic, baseOctave, bpm, framesPerSecond, beatsPerMeasure } = this.config;
    const secPerBeat = 60 / bpm;

    const { notes, measureCount } = parseJianpu(input, beatsPerMeasure);

    const curve: PitchPoint[] = [];
    let currentTime = 0;
    let lastFrequency = 0; // for sustain

    for (const note of notes) {
      const durationSec = note.beats * secPerBeat;
      const numFrames = Math.max(1, Math.round(durationSec * framesPerSecond));

      let frequency: number;

      if (note.degree === -1) {
        // Sustain: continue the previous note's frequency
        frequency = lastFrequency;
      } else if (note.degree === 0) {
        // Rest
        frequency = 0;
      } else {
        // Scale degree → frequency
        frequency = degreeToFrequency(note.degree, note.octaveShift, tonic, baseOctave);
        lastFrequency = frequency;
      }

      for (let i = 0; i < numFrames; i++) {
        const time = currentTime + (i / framesPerSecond);
        curve.push({ time: Math.round(time * 10000) / 10000, frequency });
      }

      currentTime += durationSec;
    }

    return {
      curve,
      duration: Math.round(currentTime * 10000) / 10000,
      measureCount,
      notes,
    };
  }

  /** Convert a jianpu string to reference curve format for DTW: (time, frequency) tuples. */
  toReferenceCurve(input: string): Array<[number, number]> {
    const { curve } = this.generate(input);
    return curve.map((p) => [p.time, p.frequency]);
  }

  /** Get the frequency for a specific scale degree in the configured key. */
  getFrequency(degree: number, octaveShift = 0): number {
    return degreeToFrequency(
      degree,
      octaveShift,
      this.config.tonic,
      this.config.baseOctave,
    );
  }
}
