/**
 * usePractice — React hook managing the full practice lifecycle.
 *
 * State machine: idle → starting → practicing → stopping → done
 *
 * Frame batching: Accumulates MicCapture frames (Float32Array[2048] at 16kHz).
 * When 16 frames collected (~2.05s), encodes as WAV, POSTs to /api/practice/frame.
 * Skips send if previous request is in-flight (accumulated frames join next chunk).
 *
 * CursorController's spring physics handle the ~2s gap between updates,
 * smoothly interpolating toward the last known position.
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import MicCapture from "@/audio/MicCapture";
import { CursorController } from "@/score/CursorController";
import { encodeWav } from "@/lib/wav";
import {
  startPractice,
  sendPracticeFrame,
  stopPractice,
  StopResult,
  ScoreResult,
  ApiError,
} from "@/lib/api";

// ── Types ───────────────────────────────────────────────────

export type PracticeState = "idle" | "starting" | "practicing" | "stopping" | "done";

export interface UsePracticeReturn {
  state: PracticeState;
  start: () => void;
  stop: () => void;
  feedback: StopResult | null;
  error: string;
  elapsed: number;
}

// ── Constants ───────────────────────────────────────────────

const FRAME_SIZE = 2048;
const SAMPLE_RATE = 16000;
const FRAMES_PER_CHUNK = 16; // ~2.05s at 16kHz with 2048-sample frames

// ── Hook ────────────────────────────────────────────────────

export function usePractice(
  score: ScoreResult,
  cursorRef: React.RefObject<CursorController | null>,
  bpm: number = 120,
): UsePracticeReturn {
  const [state, setState] = useState<PracticeState>("idle");
  const [feedback, setFeedback] = useState<StopResult | null>(null);
  const [error, setError] = useState("");
  const [elapsed, setElapsed] = useState(0);

  const sessionIdRef = useRef<string | null>(null);
  const micRef = useRef<MicCapture | null>(null);
  const bufferRef = useRef<Float32Array[]>([]);
  const inflightRef = useRef(false);
  const stateRef = useRef<PracticeState>("idle");

  // Keep stateRef in sync
  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  // Send accumulated frames to backend
  const flushFrames = useCallback(async () => {
    const sessionId = sessionIdRef.current;
    if (!sessionId || inflightRef.current || bufferRef.current.length === 0) return;

    // Concatenate buffered frames
    const frames = bufferRef.current;
    bufferRef.current = [];
    const totalSamples = frames.reduce((sum, f) => sum + f.length, 0);
    const concat = new Float32Array(totalSamples);
    let offset = 0;
    for (const frame of frames) {
      concat.set(frame, offset);
      offset += frame.length;
    }

    const wavBlob = encodeWav(concat, SAMPLE_RATE);
    inflightRef.current = true;

    try {
      const result = await sendPracticeFrame(sessionId, wavBlob);
      setElapsed(result.elapsed_s);

      // Feed alignment to CursorController
      if (cursorRef.current) {
        cursorRef.current.update({
          current_measure: result.alignment.current_measure,
          current_beat: result.alignment.current_beat,
          confidence: result.alignment.confidence,
          is_complete: result.alignment.is_complete,
        });
      }
    } catch (err) {
      // Ignore 404 (session expired) during stop transition
      if (stateRef.current === "practicing") {
        const msg = err instanceof ApiError ? err.detail : "Frame send failed";
        console.error("Frame error:", msg);
      }
    } finally {
      inflightRef.current = false;
    }
  }, [cursorRef]);

  // Handle incoming mic frame
  const onFrame = useCallback(
    (frame: Float32Array) => {
      bufferRef.current.push(frame);
      if (bufferRef.current.length >= FRAMES_PER_CHUNK) {
        flushFrames();
      }
    },
    [flushFrames],
  );

  // Start practice
  const start = useCallback(async () => {
    if (state !== "idle" && state !== "done") return;

    setError("");
    setFeedback(null);
    setElapsed(0);
    setState("starting");

    try {
      // Start backend session
      const resp = await startPractice(score, bpm);
      sessionIdRef.current = resp.session_id;

      // Reset cursor
      if (cursorRef.current) {
        cursorRef.current.reset();
        cursorRef.current.start();
      }

      // Start mic capture
      const mic = new MicCapture({
        sampleRate: SAMPLE_RATE,
        frameSize: FRAME_SIZE,
        onFrame,
      });
      await mic.start();
      micRef.current = mic;

      setState("practicing");
    } catch (err) {
      const msg = err instanceof ApiError
        ? err.detail
        : err instanceof DOMException && err.name === "NotAllowedError"
          ? "Microphone permission denied"
          : "Failed to start practice session";
      setError(msg);
      setState("idle");
      sessionIdRef.current = null;
    }
  }, [state, score, bpm, cursorRef, onFrame]);

  // Stop practice
  const stop = useCallback(async () => {
    if (state !== "practicing") return;

    setState("stopping");

    // Stop mic first
    if (micRef.current) {
      micRef.current.stop();
      micRef.current = null;
    }
    bufferRef.current = [];

    // Stop cursor animation
    if (cursorRef.current) {
      cursorRef.current.stop();
    }

    const sessionId = sessionIdRef.current;
    if (!sessionId) {
      setState("idle");
      return;
    }

    try {
      const result = await stopPractice(sessionId);
      setFeedback(result);
      setState("done");
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "Failed to get analysis";
      setError(msg);
      setState("idle");
    } finally {
      sessionIdRef.current = null;
    }
  }, [state, cursorRef]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (micRef.current) {
        micRef.current.stop();
        micRef.current = null;
      }
    };
  }, []);

  return { state, start, stop, feedback, error, elapsed };
}
