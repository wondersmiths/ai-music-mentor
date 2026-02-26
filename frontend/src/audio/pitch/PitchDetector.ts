import type { PitchFrame, PitchDetectorConfig, PitchDetectorState } from "./types";
import { DEFAULT_CONFIG } from "./constants";

export interface PitchDetectorCallbacks {
  onPitch?: (frame: PitchFrame) => void;
  onStateChange?: (state: PitchDetectorState) => void;
  onError?: (error: string) => void;
}

export class PitchDetector {
  private config: PitchDetectorConfig;
  private callbacks: PitchDetectorCallbacks;
  private state: PitchDetectorState = "idle";

  private audioContext: AudioContext | null = null;
  private workletNode: AudioWorkletNode | null = null;
  private sourceNode: MediaStreamAudioSourceNode | null = null;
  private stream: MediaStream | null = null;

  constructor(
    config?: Partial<PitchDetectorConfig>,
    callbacks?: PitchDetectorCallbacks
  ) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.callbacks = callbacks || {};
  }

  getState(): PitchDetectorState {
    return this.state;
  }

  private setState(state: PitchDetectorState) {
    this.state = state;
    this.callbacks.onStateChange?.(state);
  }

  async start(): Promise<void> {
    if (this.state === "running" || this.state === "starting") return;

    this.setState("starting");

    try {
      // Get mic stream — mono, no browser processing
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        },
      });

      // Create AudioContext at native sample rate (worklet handles downsampling)
      this.audioContext = new AudioContext();

      // Load the worklet module
      await this.audioContext.audioWorklet.addModule(
        "/audio-worklets/pitch-processor.js"
      );

      // Create worklet node with config
      this.workletNode = new AudioWorkletNode(
        this.audioContext,
        "pitch-processor",
        {
          processorOptions: {
            sampleRate: this.config.sampleRate,
            frameSize: this.config.frameSize,
            hopSize: this.config.hopSize,
            yinThreshold: this.config.yinThreshold,
            freqMin: this.config.freqMin,
            freqMax: this.config.freqMax,
            medianWindow: this.config.medianWindow,
            emaAlpha: this.config.emaAlpha,
            silenceThreshold: this.config.silenceThreshold,
            confidenceFloor: this.config.confidenceFloor,
          },
        }
      );

      // Listen for pitch frames from the worklet
      this.workletNode.port.onmessage = (event: MessageEvent<PitchFrame>) => {
        this.callbacks.onPitch?.(event.data);
      };

      // Connect: mic → worklet → destination (required for processing)
      this.sourceNode = this.audioContext.createMediaStreamSource(this.stream);
      this.sourceNode.connect(this.workletNode);
      this.workletNode.connect(this.audioContext.destination);

      this.setState("running");
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to start pitch detector";
      this.setState("error");
      this.callbacks.onError?.(message);
      this.cleanup();
      throw err;
    }
  }

  stop(): void {
    if (this.state === "idle") return;

    // Tell the worklet to stop
    this.workletNode?.port.postMessage({ type: "stop" });
    this.cleanup();
    this.setState("idle");
  }

  reset(): void {
    // Clear worklet state without stopping
    this.workletNode?.port.postMessage({ type: "reset" });
  }

  private cleanup(): void {
    // Disconnect audio nodes
    try {
      this.sourceNode?.disconnect();
    } catch {
      // already disconnected
    }
    try {
      this.workletNode?.disconnect();
    } catch {
      // already disconnected
    }

    // Stop mic tracks
    this.stream?.getTracks().forEach((track) => track.stop());

    // Close audio context
    if (this.audioContext && this.audioContext.state !== "closed") {
      this.audioContext.close().catch(() => {});
    }

    this.sourceNode = null;
    this.workletNode = null;
    this.stream = null;
    this.audioContext = null;
  }
}
