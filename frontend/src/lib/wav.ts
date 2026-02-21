/**
 * encodeWav — encode a Float32Array of audio samples into a 16-bit PCM WAV Blob.
 *
 * Produces a standard WAV file with a 44-byte header that Python's `wave`
 * module can read directly. Samples are clamped to [-1, 1] and scaled to int16.
 */

export function encodeWav(samples: Float32Array, sampleRate: number): Blob {
  const numChannels = 1;
  const bitsPerSample = 16;
  const bytesPerSample = bitsPerSample / 8;
  const dataLength = samples.length * bytesPerSample;
  const headerLength = 44;
  const buffer = new ArrayBuffer(headerLength + dataLength);
  const view = new DataView(buffer);

  // ── RIFF header ───────────────────────────────────────────
  writeString(view, 0, "RIFF");
  view.setUint32(4, 36 + dataLength, true);
  writeString(view, 8, "WAVE");

  // ── fmt sub-chunk ─────────────────────────────────────────
  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true);               // sub-chunk size
  view.setUint16(20, 1, true);                // PCM format
  view.setUint16(22, numChannels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * numChannels * bytesPerSample, true); // byte rate
  view.setUint16(32, numChannels * bytesPerSample, true);             // block align
  view.setUint16(34, bitsPerSample, true);

  // ── data sub-chunk ────────────────────────────────────────
  writeString(view, 36, "data");
  view.setUint32(40, dataLength, true);

  // ── PCM samples ───────────────────────────────────────────
  let offset = headerLength;
  for (let i = 0; i < samples.length; i++) {
    const clamped = Math.max(-1, Math.min(1, samples[i]));
    const int16 = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
    view.setInt16(offset, int16, true);
    offset += 2;
  }

  return new Blob([buffer], { type: "audio/wav" });
}

function writeString(view: DataView, offset: number, str: string): void {
  for (let i = 0; i < str.length; i++) {
    view.setUint8(offset + i, str.charCodeAt(i));
  }
}
