import type {
  PitchFrame,
  RecordedFrame,
  PracticeSession,
  RecorderConfig,
  RecorderState,
} from "./types";
import { DEFAULT_RECORDER_CONFIG } from "./constants";

export class SessionRecorder {
  private config: RecorderConfig;
  private exerciseType: string;
  private state: RecorderState = "idle";
  private sessionId = "";
  private startedAt = "";
  private startTime = 0; // performance timestamp of first frame or start() call
  private duration = 0;
  private frames: RecordedFrame[] = [];

  constructor(exerciseType: string, config?: Partial<RecorderConfig>) {
    this.exerciseType = exerciseType;
    this.config = { ...DEFAULT_RECORDER_CONFIG, ...config };
  }

  start(): void {
    if (this.state !== "idle") return;
    this.state = "recording";
    this.sessionId = crypto.randomUUID();
    this.startedAt = new Date().toISOString();
    this.startTime = 0;
    this.duration = 0;
    this.frames = [];
  }

  pushFrame(frame: PitchFrame): void {
    if (this.state !== "recording") return;

    // Skip silence / no-pitch frames
    if (frame.frequency <= 0) return;

    // Rebase time relative to recording start
    if (this.frames.length === 0 && this.startTime === 0) {
      this.startTime = frame.time;
    }

    const elapsed = frame.time - this.startTime;

    // Duration enforcement: auto-stop if we've reached the limit
    if (elapsed >= this.config.maxDuration) {
      this.duration = this.config.maxDuration;
      this.state = "stopped";
      return;
    }

    this.frames.push({
      time: elapsed,
      frequency: frame.frequency,
      confidence: frame.confidence,
    });

    this.duration = elapsed;
  }

  stop(): void {
    if (this.state !== "recording") return;
    this.state = "stopped";
  }

  reset(): void {
    this.state = "idle";
    this.sessionId = "";
    this.startedAt = "";
    this.startTime = 0;
    this.duration = 0;
    this.frames = [];
  }

  getSession(): PracticeSession | null {
    if (this.state !== "stopped") return null;
    return {
      id: this.sessionId,
      exerciseType: this.exerciseType,
      startedAt: this.startedAt,
      duration: this.duration,
      frameCount: this.frames.length,
      framesPerSecond: this.config.framesPerSecond,
      frames: [...this.frames],
    };
  }

  toJSON(): string | null {
    const session = this.getSession();
    if (!session) return null;
    return JSON.stringify(session);
  }

  getElapsed(): number {
    return this.duration;
  }

  getFrameCount(): number {
    return this.frames.length;
  }

  getState(): RecorderState {
    return this.state;
  }
}
