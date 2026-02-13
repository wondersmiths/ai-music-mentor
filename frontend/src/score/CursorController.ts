/**
 * CursorController — smooth cursor tracking for a digital music score.
 *
 * Takes alignment updates (measure, beat, confidence) from the backend
 * and drives a visual cursor across the rendered score. Uses confidence
 * gating, tempo-adaptive interpolation, and spring-based smoothing.
 *
 * Design goals:
 *  - High confidence → cursor advances smoothly to the new position
 *  - Low confidence  → cursor pauses and fades to signal uncertainty
 *  - Tempo changes   → interpolation speed adapts gradually (EMA)
 *  - Frame-rate independent via requestAnimationFrame + delta time
 */

// ── Types ──────────────────────────────────────────────────

/** Alignment state received from the backend score follower. */
export interface AlignmentUpdate {
  current_measure: number; // 1-based
  current_beat: number;
  confidence: number; // 0.0–1.0
  is_complete: boolean;
}

/** Absolute position in the score, used for rendering. */
export interface CursorPosition {
  /** Fractional measure position: measure 2, beat 3 of 4 → 2.5 */
  position: number;
  /** Visual opacity: 1.0 = confident, fades toward 0.3 when paused */
  opacity: number;
  /** Whether the cursor is actively tracking (vs paused) */
  tracking: boolean;
  /** Whether playback has reached the end of the score */
  complete: boolean;
}

/** Configuration for the cursor controller. */
export interface CursorConfig {
  /** Confidence below this pauses the cursor. Default 0.35 */
  confidenceGate: number;
  /** Confidence above this resumes tracking. Default 0.5.
   *  Higher than gate to prevent rapid toggling (hysteresis). */
  confidenceResume: number;
  /** Spring stiffness for position smoothing. Higher = snappier.
   *  Range 4–20, default 8. */
  springStiffness: number;
  /** Spring damping ratio. 1.0 = critically damped (no overshoot).
   *  Range 0.7–1.0, default 0.9. */
  springDamping: number;
  /** EMA alpha for tempo adaptation. Lower = smoother. Default 0.15 */
  tempoAlpha: number;
  /** Minimum opacity when paused. Default 0.3 */
  pausedOpacity: number;
  /** Beats per measure, used to convert (measure, beat) to a linear
   *  position. Updated automatically from alignment data. Default 4 */
  beatsPerMeasure: number;
}

// ── Defaults ───────────────────────────────────────────────

const DEFAULT_CONFIG: CursorConfig = {
  confidenceGate: 0.35,
  confidenceResume: 0.5,
  springStiffness: 8,
  springDamping: 0.9,
  pausedOpacity: 0.3,
  tempoAlpha: 0.15,
  beatsPerMeasure: 4,
};

// ── Controller ─────────────────────────────────────────────

export class CursorController {
  private config: CursorConfig;

  // Target position (where alignment says we should be)
  private targetPos = 0;

  // Spring state for smooth interpolation
  private currentPos = 0;
  private velocity = 0;

  // Confidence & tracking state
  private tracking = false;
  private currentConfidence = 0;
  private opacity = 0.3;

  // Tempo adaptation: estimated seconds between beats (EMA)
  private secPerBeat = 0.5; // default 120 BPM
  private lastUpdateTime = 0;
  private lastTargetPos = 0;

  // Animation
  private animId: number | null = null;
  private lastFrameTime = 0;
  private complete = false;

  // External render callback
  private onRender: ((pos: CursorPosition) => void) | null = null;

  constructor(config?: Partial<CursorConfig>) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  // ── Public API ─────────────────────────────────────────

  /**
   * Register a callback that fires every animation frame with the
   * smoothed cursor position. This is how you connect the controller
   * to your score renderer.
   */
  setRenderCallback(cb: (pos: CursorPosition) => void): void {
    this.onRender = cb;
  }

  /**
   * Feed an alignment update from the backend. Call this whenever
   * a new AlignmentState arrives (typically on each detected onset).
   */
  update(alignment: AlignmentUpdate): void {
    const now = performance.now() / 1000;
    this.currentConfidence = alignment.confidence;
    this.complete = alignment.is_complete;

    // Convert (measure, beat) to a linear position.
    // Position = (measure - 1) + (beat - 1) / beatsPerMeasure
    // e.g. measure 2, beat 3, 4/4 time → 1.5
    const bpm = this.config.beatsPerMeasure;
    const newTarget =
      (alignment.current_measure - 1) +
      (alignment.current_beat - 1) / bpm;

    // Tempo adaptation: estimate seconds-per-beat from successive updates
    if (this.lastUpdateTime > 0 && newTarget > this.lastTargetPos) {
      const dt = now - this.lastUpdateTime;
      const dPos = newTarget - this.lastTargetPos;
      const measuredSpb = dt / (dPos * bpm);

      // Clamp to sane range (30–300 BPM → 0.2–2.0 s/beat)
      const clampedSpb = Math.max(0.2, Math.min(2.0, measuredSpb));
      const alpha = this.config.tempoAlpha;
      this.secPerBeat = alpha * clampedSpb + (1 - alpha) * this.secPerBeat;
    }

    this.lastUpdateTime = now;
    this.lastTargetPos = newTarget;

    // Confidence gating with hysteresis
    if (this.tracking) {
      if (alignment.confidence < this.config.confidenceGate) {
        this.tracking = false;
      }
    } else {
      if (alignment.confidence >= this.config.confidenceResume) {
        this.tracking = true;
      }
    }

    // Only update target when tracking
    if (this.tracking && newTarget >= this.targetPos) {
      this.targetPos = newTarget;
    }
  }

  /** Start the animation loop. */
  start(): void {
    if (this.animId !== null) return;
    this.lastFrameTime = performance.now() / 1000;
    this.tick();
  }

  /** Stop the animation loop. */
  stop(): void {
    if (this.animId !== null) {
      cancelAnimationFrame(this.animId);
      this.animId = null;
    }
  }

  /** Reset to the beginning of the score. */
  reset(): void {
    this.targetPos = 0;
    this.currentPos = 0;
    this.velocity = 0;
    this.tracking = false;
    this.currentConfidence = 0;
    this.opacity = this.config.pausedOpacity;
    this.lastUpdateTime = 0;
    this.lastTargetPos = 0;
    this.secPerBeat = 0.5;
    this.complete = false;
  }

  /** Get the current cursor position synchronously. */
  getPosition(): CursorPosition {
    return {
      position: this.currentPos,
      opacity: this.opacity,
      tracking: this.tracking,
      complete: this.complete,
    };
  }

  // ── Animation loop ─────────────────────────────────────

  private tick = (): void => {
    const now = performance.now() / 1000;
    const dt = Math.min(now - this.lastFrameTime, 0.05); // cap at 50ms
    this.lastFrameTime = now;

    this.stepSpring(dt);
    this.stepOpacity(dt);

    if (this.onRender) {
      this.onRender(this.getPosition());
    }

    this.animId = requestAnimationFrame(this.tick);
  };

  /**
   * Critically-damped spring physics for position smoothing.
   *
   * A spring gives us:
   * - Smooth acceleration toward the target (no sudden jumps)
   * - Automatic speed adaptation: large gaps → fast catch-up,
   *   small gaps → gentle glide
   * - Configurable stiffness (snappiness) and damping (overshoot)
   *
   * The spring constant is scaled by tempo so that faster tempos
   * produce stiffer tracking (cursor keeps up) and slower tempos
   * produce softer movement (cursor doesn't jitter).
   */
  private stepSpring(dt: number): void {
    if (!this.tracking && Math.abs(this.velocity) < 0.001) {
      // Paused and nearly stopped — don't waste computation
      this.velocity = 0;
      return;
    }

    const error = this.targetPos - this.currentPos;

    // Scale stiffness by inverse seconds-per-beat: faster tempo = stiffer
    const tempoScale = 0.5 / this.secPerBeat;
    const k = this.config.springStiffness * tempoScale;
    const c = this.config.springDamping * 2 * Math.sqrt(k); // critical damping

    // Spring force: F = k * error - c * velocity
    const acceleration = k * error - c * this.velocity;

    this.velocity += acceleration * dt;
    this.currentPos += this.velocity * dt;

    // Prevent overshoot past the target
    if (
      (error > 0 && this.currentPos > this.targetPos) ||
      (error < 0 && this.currentPos < this.targetPos)
    ) {
      this.currentPos = this.targetPos;
      this.velocity = 0;
    }
  }

  /**
   * Smooth opacity transitions between tracking and paused states.
   * Ramps toward 1.0 when tracking, toward pausedOpacity when paused.
   */
  private stepOpacity(dt: number): void {
    const targetOpacity = this.tracking ? 1.0 : this.config.pausedOpacity;
    const rate = 4.0; // opacity change per second
    const diff = targetOpacity - this.opacity;
    const step = Math.sign(diff) * Math.min(Math.abs(diff), rate * dt);
    this.opacity = Math.max(0, Math.min(1, this.opacity + step));
  }
}
