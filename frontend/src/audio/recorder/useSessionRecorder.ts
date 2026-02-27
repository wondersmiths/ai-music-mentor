import { useCallback, useRef, useState } from "react";
import type { PitchFrame, RecorderConfig, RecorderState, PracticeSession } from "./types";
import { SessionRecorder } from "./SessionRecorder";

interface UseSessionRecorderOptions {
  exerciseType: string;
  config?: Partial<RecorderConfig>;
}

interface UseSessionRecorderReturn {
  state: RecorderState;
  elapsed: number;
  frameCount: number;
  pushFrame: (frame: PitchFrame) => void;
  start: () => void;
  stop: () => void;
  reset: () => void;
  getSession: () => PracticeSession | null;
  toJSON: () => string | null;
}

export function useSessionRecorder(
  opts: UseSessionRecorderOptions
): UseSessionRecorderReturn {
  const { exerciseType, config } = opts;

  const [state, setState] = useState<RecorderState>("idle");
  const [elapsed, setElapsed] = useState(0);
  const [frameCount, setFrameCount] = useState(0);

  const recorderRef = useRef<SessionRecorder>(
    new SessionRecorder(exerciseType, config)
  );

  const pushFrame = useCallback((frame: PitchFrame) => {
    const recorder = recorderRef.current;
    recorder.pushFrame(frame);

    const newState = recorder.getState();
    setState(newState);
    setElapsed(recorder.getElapsed());
    setFrameCount(recorder.getFrameCount());
  }, []);

  const start = useCallback(() => {
    recorderRef.current.start();
    setState("recording");
    setElapsed(0);
    setFrameCount(0);
  }, []);

  const stop = useCallback(() => {
    recorderRef.current.stop();
    setState("stopped");
  }, []);

  const reset = useCallback(() => {
    recorderRef.current.reset();
    setState("idle");
    setElapsed(0);
    setFrameCount(0);
  }, []);

  const getSession = useCallback(() => {
    return recorderRef.current.getSession();
  }, []);

  const toJSON = useCallback(() => {
    return recorderRef.current.toJSON();
  }, []);

  return { state, elapsed, frameCount, pushFrame, start, stop, reset, getSession, toJSON };
}
