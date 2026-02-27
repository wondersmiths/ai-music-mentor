import { useCallback, useEffect, useRef, useState } from "react";
import type {
  CursorEngineConfig,
  CursorEngineState,
  CursorPosition,
} from "./types";
import { CursorEngine } from "./CursorEngine";

interface UseCursorEngineOptions {
  config?: Partial<CursorEngineConfig>;
  /** If true, starts an animation loop to update position each frame. */
  animationLoop?: boolean;
}

interface UseCursorEngineReturn {
  state: CursorEngineState;
  position: CursorPosition;
  start: () => void;
  stop: () => void;
  pause: () => void;
  resume: () => void;
  resyncToBar: (bar: number) => void;
  setBpm: (bpm: number) => void;
}

export function useCursorEngine(
  opts: UseCursorEngineOptions = {},
): UseCursorEngineReturn {
  const { config, animationLoop = true } = opts;

  const [state, setState] = useState<CursorEngineState>("idle");
  const [position, setPosition] = useState<CursorPosition>({
    currentTime: 0,
    currentBar: 1,
    currentBeat: 1,
    totalBeats: 0,
  });

  const engineRef = useRef<CursorEngine>(new CursorEngine(config));

  useEffect(() => {
    if (!animationLoop) return;

    const engine = engineRef.current;
    engine.setTickCallback((pos) => {
      setPosition(pos);
      setState(engine.getState());
    });
    engine.startAnimationLoop();

    return () => {
      engine.stopAnimationLoop();
    };
  }, [animationLoop]);

  const start = useCallback(() => {
    engineRef.current.start();
    setState("playing");
    setPosition({ currentTime: 0, currentBar: 1, currentBeat: 1, totalBeats: 0 });
  }, []);

  const stop = useCallback(() => {
    engineRef.current.stop();
    setState("idle");
    setPosition({ currentTime: 0, currentBar: 1, currentBeat: 1, totalBeats: 0 });
  }, []);

  const pause = useCallback(() => {
    engineRef.current.pause();
    setState("paused");
  }, []);

  const resume = useCallback(() => {
    engineRef.current.resume();
    setState("playing");
  }, []);

  const resyncToBar = useCallback((bar: number) => {
    engineRef.current.resyncToBar(bar);
  }, []);

  const setBpm = useCallback((bpm: number) => {
    engineRef.current.setBpm(bpm);
  }, []);

  return { state, position, start, stop, pause, resume, resyncToBar, setBpm };
}
