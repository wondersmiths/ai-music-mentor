/**
 * Web Audio oscillator metronome.
 *
 * Plays short sine bursts on each beat:
 * - Beat 1 (accent): 1000 Hz
 * - Other beats: 800 Hz
 * Uses exponential decay for a short, crisp click.
 */

export interface MetronomeOptions {
  bpm: number;
  beatsPerMeasure?: number;
}

export class Metronome {
  private audioCtx: AudioContext | null = null;
  private timerId: ReturnType<typeof setInterval> | null = null;
  private _bpm: number;
  private beatsPerMeasure: number;
  private currentBeat = 0;
  private running = false;

  /** Fires on each beat with (beatNumber, isAccent) — 1-indexed */
  public onBeat: ((beat: number, isAccent: boolean) => void) | null = null;

  constructor(opts: MetronomeOptions) {
    this._bpm = opts.bpm;
    this.beatsPerMeasure = opts.beatsPerMeasure ?? 4;
  }

  get bpm() {
    return this._bpm;
  }

  setBpm(bpm: number) {
    this._bpm = Math.max(20, Math.min(300, bpm));
    if (this.running) {
      // Restart with new interval
      this.stop();
      this.start();
    }
  }

  setBeatsPerMeasure(beats: number) {
    this.beatsPerMeasure = beats;
  }

  start() {
    if (this.running) return;

    this.audioCtx = new AudioContext();
    this.currentBeat = 0;
    this.running = true;

    const intervalMs = (60 / this._bpm) * 1000;

    // Play first beat immediately
    this.tick();

    this.timerId = setInterval(() => {
      this.tick();
    }, intervalMs);
  }

  stop() {
    this.running = false;
    if (this.timerId !== null) {
      clearInterval(this.timerId);
      this.timerId = null;
    }
    if (this.audioCtx) {
      this.audioCtx.close().catch(() => {});
      this.audioCtx = null;
    }
  }

  private tick() {
    this.currentBeat++;
    if (this.currentBeat > this.beatsPerMeasure) {
      this.currentBeat = 1;
    }

    const isAccent = this.currentBeat === 1;
    this.playClick(isAccent);

    if (this.onBeat) {
      this.onBeat(this.currentBeat, isAccent);
    }
  }

  private playClick(accent: boolean) {
    const ctx = this.audioCtx;
    if (!ctx) return;

    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.frequency.value = accent ? 1000 : 800;
    osc.type = "sine";

    const now = ctx.currentTime;
    gain.gain.setValueAtTime(accent ? 0.5 : 0.3, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.06);

    osc.start(now);
    osc.stop(now + 0.06);
  }
}
