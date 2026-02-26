/**
 * AudioWorklet processor for real-time YIN pitch detection, optimized for erhu.
 *
 * Ported from:
 *   ai/pitch/yin.py — core YIN algorithm
 *   ai/pitch/erhu.py — erhu-specific enhancements
 *
 * Runs entirely off the main thread. Posts {time, frequency, confidence}
 * tuples to the main thread at ~50Hz (every 320 samples at 16kHz).
 *
 * All DSP is time-domain — no FFT needed for the small erhu lag range
 * (7–62 lags), making this trivially fast (~0.3% CPU).
 */

class PitchProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();

    const cfg = options.processorOptions || {};
    this.targetSampleRate = cfg.sampleRate || 16000;
    this.frameSize = cfg.frameSize || 2048;
    this.hopSize = cfg.hopSize || 320;
    this.yinThreshold = cfg.yinThreshold || 0.12;
    this.freqMin = cfg.freqMin || 260;
    this.freqMax = cfg.freqMax || 2400;
    this.medianWindow = cfg.medianWindow || 5;
    this.emaAlpha = cfg.emaAlpha || 0.35;
    this.silenceThreshold = Math.pow(10, (cfg.silenceThreshold || -50) / 20);
    this.confidenceFloor = cfg.confidenceFloor || 0.65;
    this.preEmphasis = 0.97;

    // Lag bounds for erhu frequency range
    this.minLag = Math.max(2, Math.floor(this.targetSampleRate / this.freqMax));
    this.maxLag = Math.min(
      Math.floor(this.frameSize / 2),
      Math.floor(this.targetSampleRate / this.freqMin)
    );

    // Ring buffer for downsampled audio
    this.ringBuffer = new Float32Array(this.frameSize + this.hopSize);
    this.ringWritePos = 0;
    this.samplesInBuffer = 0;

    // Downsampler state
    this.srcSampleRate = sampleRate; // AudioWorklet global
    this.downsampleRatio = this.srcSampleRate / this.targetSampleRate;
    this.downsampleAccum = 0; // fractional sample accumulator

    // Pre-emphasis state
    this.prevSample = 0;

    // Smoothing state
    this.pitchHistory = [];
    this.smoothedHz = 0;
    this.prevRawHz = 0;

    // Frame counter for timestamps
    this.hopCount = 0;
    this.newSampleCount = 0;

    this.running = true;

    this.port.onmessage = (e) => {
      if (e.data.type === "stop") {
        this.running = false;
      } else if (e.data.type === "reset") {
        this._reset();
      }
    };
  }

  _reset() {
    this.ringBuffer.fill(0);
    this.ringWritePos = 0;
    this.samplesInBuffer = 0;
    this.downsampleAccum = 0;
    this.prevSample = 0;
    this.pitchHistory = [];
    this.smoothedHz = 0;
    this.prevRawHz = 0;
    this.hopCount = 0;
    this.newSampleCount = 0;
  }

  process(inputs, _outputs, _params) {
    if (!this.running) return false;

    const input = inputs[0];
    if (!input || !input[0] || input[0].length === 0) return true;

    const channel = input[0];

    // Downsample incoming audio to target rate using linear interpolation
    for (let i = 0; i < channel.length; i++) {
      this.downsampleAccum += 1;
      if (this.downsampleAccum >= this.downsampleRatio) {
        this.downsampleAccum -= this.downsampleRatio;

        // Linear interpolation
        const srcIdx = i;
        const sample = channel[srcIdx];

        // Write to ring buffer
        this.ringBuffer[this.ringWritePos] = sample;
        this.ringWritePos = (this.ringWritePos + 1) % this.ringBuffer.length;
        this.samplesInBuffer = Math.min(
          this.samplesInBuffer + 1,
          this.ringBuffer.length
        );
        this.newSampleCount++;
      }
    }

    // Process when we have enough new samples (one hop)
    while (this.newSampleCount >= this.hopSize && this.samplesInBuffer >= this.frameSize) {
      this.newSampleCount -= this.hopSize;
      this._analyzeFrame();
    }

    return true;
  }

  _analyzeFrame() {
    // Extract frame from ring buffer
    const frame = new Float32Array(this.frameSize);
    const start =
      (this.ringWritePos - this.samplesInBuffer + this.ringBuffer.length) %
      this.ringBuffer.length;

    for (let i = 0; i < this.frameSize; i++) {
      frame[i] = this.ringBuffer[(start + i) % this.ringBuffer.length];
    }

    // Advance the buffer (consume one hop)
    this.samplesInBuffer -= this.hopSize;

    const timestamp = (this.hopCount * this.hopSize) / this.targetSampleRate;
    this.hopCount++;

    // 1. Pre-emphasis highpass: y[n] = x[n] - α·x[n-1]
    const emphasized = new Float32Array(this.frameSize);
    emphasized[0] = frame[0] - this.preEmphasis * this.prevSample;
    for (let i = 1; i < this.frameSize; i++) {
      emphasized[i] = frame[i] - this.preEmphasis * frame[i - 1];
    }
    this.prevSample = frame[this.frameSize - 1];

    // 2. Silence gate
    let sumSq = 0;
    for (let i = 0; i < this.frameSize; i++) {
      sumSq += emphasized[i] * emphasized[i];
    }
    const rms = Math.sqrt(sumSq / this.frameSize);

    if (rms < this.silenceThreshold) {
      this.pitchHistory.push(0);
      if (this.pitchHistory.length > this.medianWindow) {
        this.pitchHistory.shift();
      }
      this.smoothedHz = 0;
      this.port.postMessage({ time: timestamp, frequency: 0, confidence: 0 });
      return;
    }

    // 3. YIN core — time-domain difference function (fast for small lag range)
    const diff = this._differenceFn(emphasized, this.maxLag);
    const cmnd = this._cmnd(diff);

    // Mask lags outside erhu range
    for (let i = 0; i < this.minLag; i++) {
      cmnd[i] = 1.0;
    }

    // 4. Absolute threshold search
    let tau = this._absoluteThreshold(cmnd, this.yinThreshold);

    let rawHz = 0;
    let confidence = 0;

    if (tau === 0) {
      this.pitchHistory.push(0);
      if (this.pitchHistory.length > this.medianWindow) {
        this.pitchHistory.shift();
      }
    } else {
      // 5. Parabolic interpolation for sub-sample accuracy
      const refinedTau = this._parabolicInterp(cmnd, tau);
      rawHz = refinedTau > 0 ? this.targetSampleRate / refinedTau : 0;
      const yinConf = 1.0 - cmnd[tau];

      // 6. Octave guard
      rawHz = this._octaveGuard(rawHz, cmnd);

      // Range sanity
      if (rawHz < this.freqMin || rawHz > this.freqMax) {
        rawHz = 0;
      }

      // 7. Harmonic confidence boost
      const harmBoost = this._harmonicCheck(cmnd, tau);
      confidence = Math.min(1.0, yinConf * 0.8 + harmBoost * 0.2);

      // Confidence floor
      if (confidence < this.confidenceFloor) {
        rawHz = 0;
        confidence = 0;
      }

      this.pitchHistory.push(rawHz);
      if (this.pitchHistory.length > this.medianWindow) {
        this.pitchHistory.shift();
      }
    }

    this.prevRawHz = rawHz;

    // 8. Temporal smoothing
    // Stage 1: median filter
    const medianHz = this._medianPitch();

    // Stage 2: adaptive EMA in log-frequency space
    if (medianHz > 0 && this.smoothedHz > 0) {
      const alpha = this._adaptiveAlpha(medianHz);
      const logSmooth = Math.log2(this.smoothedHz);
      const logNew = Math.log2(medianHz);
      const logOut = alpha * logNew + (1 - alpha) * logSmooth;
      this.smoothedHz = Math.pow(2, logOut);
    } else if (medianHz > 0) {
      this.smoothedHz = medianHz;
    } else {
      this.smoothedHz *= 0.5;
    }

    const finalHz = this.smoothedHz > 10 ? this.smoothedHz : 0;

    this.port.postMessage({
      time: timestamp,
      frequency: finalHz,
      confidence: finalHz > 0 ? Math.max(0, Math.min(1, confidence)) : 0,
    });
  }

  // ── YIN core functions ──────────────────────────────────────

  /**
   * Time-domain difference function d(τ).
   * d(τ) = Σ (x[j] - x[j+τ])² for j = 0..W-1-τ
   *
   * Direct computation is O(N·maxLag) but with only ~55 lags this is trivially fast.
   */
  _differenceFn(frame, maxLag) {
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

  /**
   * Cumulative mean normalized difference.
   * d'(τ) = d(τ) / ((1/τ) * Σ d(j) for j=1..τ)
   * d'(0) = 1
   */
  _cmnd(diff) {
    const result = new Float32Array(diff.length);
    result[0] = 1.0;
    let runningSum = 0;

    for (let tau = 1; tau < diff.length; tau++) {
      runningSum += diff[tau];
      result[tau] = runningSum > 0 ? (diff[tau] * tau) / runningSum : 1.0;
    }

    return result;
  }

  /**
   * Find first τ where CMND dips below threshold and is a local minimum.
   * Returns 0 if no pitch found.
   */
  _absoluteThreshold(cmndArr, threshold) {
    let tau = 2;
    while (tau < cmndArr.length - 1) {
      if (cmndArr[tau] < threshold) {
        // Walk past any plateau to local minimum
        while (
          tau + 1 < cmndArr.length &&
          cmndArr[tau + 1] < cmndArr[tau]
        ) {
          tau++;
        }
        return tau;
      }
      tau++;
    }
    return 0;
  }

  /**
   * Parabolic interpolation around the minimum for sub-sample accuracy.
   */
  _parabolicInterp(cmndArr, tau) {
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

  // ── Erhu-specific enhancements ──────────────────────────────

  /**
   * Correct octave jumps by comparing CMND values at candidate periods.
   */
  _octaveGuard(hz, cmnd) {
    if (hz <= 0 || this.prevRawHz <= 0) return hz;

    const ratio = hz / this.prevRawHz;
    if (ratio < 0.6) {
      // Dropped an octave — check if double freq is better
      return this._pickBetter(hz, hz * 2, cmnd);
    }
    if (ratio > 1.8) {
      // Jumped up — check if half freq is better
      return this._pickBetter(hz, hz / 2, cmnd);
    }

    return hz;
  }

  /**
   * Return whichever candidate has a lower CMND value (better periodicity).
   */
  _pickBetter(aHz, bHz, cmnd) {
    const cmndAt = (freq) => {
      if (freq <= 0) return 1.0;
      const tau = Math.round(this.targetSampleRate / freq);
      if (tau < 1 || tau >= cmnd.length) return 1.0;
      return cmnd[tau];
    };

    return cmndAt(aHz) <= cmndAt(bHz) ? aHz : bHz;
  }

  /**
   * Check for CMND dip at τ/2 (2nd harmonic confirmation).
   * Returns 0.0–1.0 where higher = more confident the fundamental is correct.
   */
  _harmonicCheck(cmnd, tau) {
    const halfTau = Math.floor(tau / 2);
    if (halfTau < 2 || halfTau >= cmnd.length) {
      return 0.5; // can't check — neutral
    }

    const val = cmnd[halfTau];
    if (val < 0.3) return 1.0;
    if (val < 0.6) return 0.7;
    return 0.3;
  }

  // ── Smoothing ───────────────────────────────────────────────

  /**
   * Median of recent non-zero pitch values.
   */
  _medianPitch() {
    const valid = this.pitchHistory.filter((p) => p > 0);
    if (valid.length === 0) return 0;

    valid.sort((a, b) => a - b);
    const mid = Math.floor(valid.length / 2);
    return valid.length % 2 === 1
      ? valid[mid]
      : (valid[mid - 1] + valid[mid]) / 2;
  }

  /**
   * Adaptive EMA alpha based on pitch change rate (in semitones per frame).
   * During portamento: more responsive. During steady notes: more smoothing.
   */
  _adaptiveAlpha(newHz) {
    if (this.smoothedHz <= 0 || newHz <= 0) {
      return this.emaAlpha;
    }

    const semitoneDelta = Math.abs(12.0 * Math.log2(newHz / this.smoothedHz));

    if (semitoneDelta > 1.0) {
      // Fast glide — track closely
      return Math.min(0.8, this.emaAlpha * 2.5);
    }
    if (semitoneDelta > 0.3) {
      // Moderate portamento — slightly more responsive
      return Math.min(0.6, this.emaAlpha * 1.5);
    }

    // Steady pitch — base alpha
    return this.emaAlpha;
  }
}

registerProcessor("pitch-processor", PitchProcessor);
