/**
 * Production-ready fetch wrapper for the backend API.
 *
 * - Reads NEXT_PUBLIC_API_URL from environment
 * - Structured error handling with typed responses
 * - Timeout support
 * - Works both client-side and server-side
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

interface RequestOptions {
  timeout?: number; // ms, default 30000
}

async function request<T>(
  path: string,
  init: RequestInit,
  opts: RequestOptions = {},
): Promise<T> {
  const timeout = opts.timeout ?? 30000;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);

  try {
    const res = await fetch(`${API_URL}${path}`, {
      ...init,
      signal: controller.signal,
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ApiError(res.status, body.detail || `HTTP ${res.status}`);
    }

    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if ((err as Error).name === "AbortError") {
      throw new ApiError(408, "Request timed out");
    }
    throw new ApiError(0, (err as Error).message || "Network error");
  } finally {
    clearTimeout(timer);
  }
}

// ── Typed API methods ───────────────────────────────────────

export interface PitchEvent {
  time: number;
  note: string;
  frequency: number;
  cents_off: number;
  confidence: number;
}

export interface OnsetEvent {
  time: number;
  strength: number;
}

export interface AnalysisResult {
  pitches: PitchEvent[];
  onsets: OnsetEvent[];
  tempo: { bpm: number; confidence: number };
  duration_s: number;
}

export interface ScoreResult {
  title: string;
  confidence: number;
  is_mock: boolean;
  measures: Array<{
    number: number;
    time_signature: string;
    notes: Array<{ pitch: string; duration: string; beat: number }>;
  }>;
}

/** Upload a WAV audio chunk for analysis. */
export async function analyzeAudio(wavBlob: Blob): Promise<AnalysisResult> {
  const form = new FormData();
  form.append("file", wavBlob, "chunk.wav");
  return request<AnalysisResult>("/api/analyze", { method: "POST", body: form });
}

/** Upload a score image/PDF for recognition. */
export async function parseScore(file: File): Promise<ScoreResult> {
  const form = new FormData();
  form.append("file", file);
  return request<ScoreResult>("/api/score/parse", { method: "POST", body: form });
}

/** Health check. */
export async function checkHealth(): Promise<{ status: string }> {
  return request("/health", { method: "GET" });
}
