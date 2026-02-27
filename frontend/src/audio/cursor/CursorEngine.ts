/**
 * F4: Local BPM-based cursor engine.
 *
 * Drives a cursor through musical time using performance.now() for drift-free
 * timing. Supports start/stop/pause/resume, per-bar resync, and configurable
 * BPM / time signature.
 *
 * Unlike the CursorController in src/score/ (which smoothly tracks backend
 * alignment updates via spring physics), this engine is a standalone local
 * clock that advances purely from wall-clock time — suitable for guided
 * practice where no backend alignment is available.
 */

import type {
  CursorEngineState,
  CursorPosition,
  CursorEngineConfig,
} from "./types";
import { DEFAULT_CURSOR_CONFIG } from "./constants";

export class CursorEngine {
  private config: CursorEngineConfig;
  private state: CursorEngineState = "idle";

  /** Absolute time (ms) when playback started, from performance.now(). */
  private startTimeMs = 0;

  /** Accumulated pause duration in ms. */
  private pausedDurationMs = 0;

  /** Time (ms) when the most recent pause began. */
  private pauseStartMs = 0;

  /** Manual resync offset in beats. */
  private resyncOffsetBeats = 0;

  /** Callback invoked each tick with the current position. */
  private onTick: ((pos: CursorPosition) => void) | null = null;

  /** rAF handle. */
  private animId: number | null = null;

  constructor(config?: Partial<CursorEngineConfig>) {
    this.config = { ...DEFAULT_CURSOR_CONFIG, ...config };
  }

  // ── Public API ──────────────────────────────────────────

  /** Start playback from the beginning. */
  start(now?: number): void {
    if (this.state === "playing") return;

    const t = now ?? performance.now();
    this.startTimeMs = t;
    this.pausedDurationMs = 0;
    this.pauseStartMs = 0;
    this.resyncOffsetBeats = 0;
    this.state = "playing";
  }

  /** Pause playback. */
  pause(now?: number): void {
    if (this.state !== "playing") return;
    this.pauseStartMs = now ?? performance.now();
    this.state = "paused";
  }

  /** Resume from pause. */
  resume(now?: number): void {
    if (this.state !== "paused") return;
    const t = now ?? performance.now();
    this.pausedDurationMs += t - this.pauseStartMs;
    this.pauseStartMs = 0;
    this.state = "playing";
  }

  /** Stop playback and reset to idle. */
  stop(): void {
    this.state = "idle";
    this.startTimeMs = 0;
    this.pausedDurationMs = 0;
    this.pauseStartMs = 0;
    this.resyncOffsetBeats = 0;
    if (this.animId !== null) {
      cancelAnimationFrame(this.animId);
      this.animId = null;
    }
  }

  /**
   * Resync the cursor to the start of a specific bar.
   * Adjusts the internal offset so the next getPosition() returns
   * the beginning of `barNumber`.
   */
  resyncToBar(barNumber: number, now?: number): void {
    if (this.state !== "playing" && this.state !== "paused") return;

    const targetBeats = (barNumber - 1) * this.config.beatsPerMeasure;
    const currentPos = this.getPosition(now);
    this.resyncOffsetBeats += targetBeats - currentPos.totalBeats;
  }

  /** Update BPM on the fly (takes effect immediately). */
  setBpm(bpm: number): void {
    if (bpm > 0) {
      this.config.bpm = bpm;
    }
  }

  /** Get the current cursor position. */
  getPosition(now?: number): CursorPosition {
    if (this.state === "idle") {
      return { currentTime: 0, currentBar: 1, currentBeat: 1, totalBeats: 0 };
    }

    const t = now ?? performance.now();
    let elapsedMs: number;

    if (this.state === "paused") {
      elapsedMs = this.pauseStartMs - this.startTimeMs - this.pausedDurationMs;
    } else {
      elapsedMs = t - this.startTimeMs - this.pausedDurationMs;
    }

    const elapsedSec = Math.max(0, elapsedMs / 1000);
    const secPerBeat = 60 / this.config.bpm;
    let totalBeats = elapsedSec / secPerBeat + this.resyncOffsetBeats;

    // Handle count-in: negative beats during count-in period
    const countIn = this.config.countInBeats;
    if (countIn > 0) {
      totalBeats -= countIn;
    }

    // Check finish condition
    if (
      this.config.totalMeasures > 0 &&
      totalBeats >= this.config.totalMeasures * this.config.beatsPerMeasure
    ) {
      totalBeats = this.config.totalMeasures * this.config.beatsPerMeasure;
      if (this.state === "playing") {
        this.state = "finished";
      }
    }

    const bpm = this.config.beatsPerMeasure;

    // During count-in (totalBeats < 0), show bar 0 or negative
    const currentBar = Math.floor(totalBeats / bpm) + 1;
    const beatInBar = (totalBeats % bpm) + 1;

    // Handle negative modulo for count-in
    const adjustedBeat = totalBeats < 0
      ? bpm + (totalBeats % bpm) + 1
      : beatInBar;

    return {
      currentTime: elapsedSec,
      currentBar: Math.max(0, currentBar),
      currentBeat: Math.round(adjustedBeat * 1000) / 1000,
      totalBeats: Math.round(totalBeats * 1000) / 1000,
    };
  }

  /** Get the current state. */
  getState(): CursorEngineState {
    return this.state;
  }

  /** Register a tick callback for animation-loop driven updates. */
  setTickCallback(cb: (pos: CursorPosition) => void): void {
    this.onTick = cb;
  }

  /** Start the animation loop (calls onTick each frame). */
  startAnimationLoop(): void {
    if (this.animId !== null) return;
    this.tick();
  }

  /** Stop the animation loop. */
  stopAnimationLoop(): void {
    if (this.animId !== null) {
      cancelAnimationFrame(this.animId);
      this.animId = null;
    }
  }

  // ── Internal ────────────────────────────────────────────

  private tick = (): void => {
    if (this.onTick && (this.state === "playing" || this.state === "paused")) {
      this.onTick(this.getPosition());
    }
    this.animId = requestAnimationFrame(this.tick);
  };
}
