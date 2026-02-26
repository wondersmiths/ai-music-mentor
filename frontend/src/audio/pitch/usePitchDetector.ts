import { useCallback, useEffect, useRef, useState } from "react";
import type { PitchFrame, PitchDetectorConfig, PitchDetectorState } from "./types";
import { PitchDetector } from "./PitchDetector";

interface UsePitchDetectorOptions {
  config?: Partial<PitchDetectorConfig>;
  onPitch?: (frame: PitchFrame) => void;
}

interface UsePitchDetectorReturn {
  state: PitchDetectorState;
  start: () => Promise<void>;
  stop: () => void;
  latestPitch: PitchFrame | null;
  error: string;
}

export function usePitchDetector(
  opts?: UsePitchDetectorOptions
): UsePitchDetectorReturn {
  const [state, setState] = useState<PitchDetectorState>("idle");
  const [latestPitch, setLatestPitch] = useState<PitchFrame | null>(null);
  const [error, setError] = useState("");

  // Keep callbacks fresh without recreating the detector
  const onPitchRef = useRef(opts?.onPitch);
  onPitchRef.current = opts?.onPitch;

  const detectorRef = useRef<PitchDetector | null>(null);

  // Create detector once on mount
  useEffect(() => {
    const detector = new PitchDetector(opts?.config, {
      onPitch: (frame) => {
        onPitchRef.current?.(frame);
        setLatestPitch(frame);
      },
      onStateChange: setState,
      onError: setError,
    });
    detectorRef.current = detector;

    return () => {
      detector.stop();
      detectorRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const start = useCallback(async () => {
    setError("");
    await detectorRef.current?.start();
  }, []);

  const stop = useCallback(() => {
    detectorRef.current?.stop();
    setLatestPitch(null);
  }, []);

  return { state, start, stop, latestPitch, error };
}
