/**
 * MicCapture — Real-time microphone audio capture for pitch detection.
 *
 * Captures mono audio at 16 kHz and delivers fixed-size Float32 frames
 * to a callback. The Web Audio API records at the hardware sample rate,
 * so we downsample on the fly via an OfflineAudioContext per chunk.
 *
 * Usage:
 *   const mic = new MicCapture({ frameSize: 2048, onFrame: (buf) => { ... } });
 *   await mic.start();
 *   mic.stop();
 */

/** Default settings tuned for pitch detection */
const DEFAULTS = {
  /** Target sample rate in Hz */
  sampleRate: 16000,
  /** Samples per frame — 2048 @ 16 kHz ≈ 128 ms, good for pitch detection down to ~50 Hz */
  frameSize: 2048,
  /** ScriptProcessor buffer size (must be power of 2). Smaller = lower latency. */
  bufferSize: 4096,
};

export default class MicCapture {
  /**
   * @param {object}   opts
   * @param {number}   [opts.sampleRate=16000]  Target sample rate (Hz)
   * @param {number}   [opts.frameSize=2048]    Samples per delivered frame
   * @param {number}   [opts.bufferSize=4096]   Internal capture buffer size
   * @param {function} opts.onFrame             Callback receiving a Float32Array frame
   */
  constructor(opts = {}) {
    if (typeof opts.onFrame !== "function") {
      throw new Error("MicCapture requires an onFrame callback");
    }

    this.sampleRate = opts.sampleRate ?? DEFAULTS.sampleRate;
    this.frameSize = opts.frameSize ?? DEFAULTS.frameSize;
    this.bufferSize = opts.bufferSize ?? DEFAULTS.bufferSize;
    this.onFrame = opts.onFrame;

    // Internal state
    this._stream = null;
    this._audioCtx = null;
    this._processor = null;
    this._source = null;
    this._accumulator = new Float32Array(0); // collects samples between frames
    this._running = false;
  }

  /**
   * Request mic permission and begin capturing audio frames.
   * Resolves once the pipeline is live.
   */
  async start() {
    if (this._running) return;

    // 1. Get mono mic stream
    this._stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: false, // disable processing that distorts pitch
        noiseSuppression: false,
        autoGainControl: false,
      },
    });

    // 2. Create audio context at the hardware's native rate
    this._audioCtx = new (window.AudioContext)();
    const nativeRate = this._audioCtx.sampleRate;

    // 3. Connect mic → ScriptProcessor (mono in, mono out)
    this._source = this._audioCtx.createMediaStreamSource(this._stream);
    this._processor = this._audioCtx.createScriptProcessor(this.bufferSize, 1, 1);

    this._processor.onaudioprocess = (event) => {
      if (!this._running) return;
      const input = event.inputBuffer.getChannelData(0); // Float32, native rate
      this._ingest(input, nativeRate);
    };

    // Connect the graph (processor must connect to destination to fire events)
    this._source.connect(this._processor);
    this._processor.connect(this._audioCtx.destination);

    this._running = true;
  }

  /** Stop capturing and release all resources. */
  stop() {
    this._running = false;

    if (this._processor) {
      this._processor.disconnect();
      this._processor.onaudioprocess = null;
      this._processor = null;
    }
    if (this._source) {
      this._source.disconnect();
      this._source = null;
    }
    if (this._audioCtx) {
      this._audioCtx.close();
      this._audioCtx = null;
    }
    if (this._stream) {
      this._stream.getTracks().forEach((t) => t.stop());
      this._stream = null;
    }

    // Flush leftover samples
    this._accumulator = new Float32Array(0);
  }

  /** @returns {boolean} Whether the capture is currently active */
  get running() {
    return this._running;
  }

  // ── Internals ──────────────────────────────────────────────

  /**
   * Accept a chunk of native-rate samples, downsample to target rate,
   * accumulate, and emit complete frames.
   *
   * @param {Float32Array} raw        Samples at the native hardware rate
   * @param {number}       nativeRate Hardware sample rate (e.g. 44100 or 48000)
   */
  _ingest(raw, nativeRate) {
    const downsampled =
      nativeRate === this.sampleRate
        ? raw
        : downsample(raw, nativeRate, this.sampleRate);

    // Append to accumulator
    const merged = new Float32Array(this._accumulator.length + downsampled.length);
    merged.set(this._accumulator);
    merged.set(downsampled, this._accumulator.length);
    this._accumulator = merged;

    // Emit as many complete frames as available
    while (this._accumulator.length >= this.frameSize) {
      const frame = this._accumulator.slice(0, this.frameSize);
      this._accumulator = this._accumulator.slice(this.frameSize);
      this.onFrame(frame);
    }
  }
}

// ── Utility ────────────────────────────────────────────────

/**
 * Simple linear-interpolation downsampler.
 * Good enough for pitch detection; avoids the latency of OfflineAudioContext.
 *
 * @param {Float32Array} buffer     Source samples
 * @param {number}       fromRate   Source sample rate
 * @param {number}       toRate     Target sample rate
 * @returns {Float32Array}          Downsampled buffer
 */
function downsample(buffer, fromRate, toRate) {
  if (toRate >= fromRate) return buffer;

  const ratio = fromRate / toRate;
  const length = Math.floor(buffer.length / ratio);
  const result = new Float32Array(length);

  for (let i = 0; i < length; i++) {
    // Fractional index into the source buffer
    const srcIndex = i * ratio;
    const lo = Math.floor(srcIndex);
    const hi = Math.min(lo + 1, buffer.length - 1);
    const frac = srcIndex - lo;

    // Linear interpolation between adjacent samples
    result[i] = buffer[lo] * (1 - frac) + buffer[hi] * frac;
  }

  return result;
}
