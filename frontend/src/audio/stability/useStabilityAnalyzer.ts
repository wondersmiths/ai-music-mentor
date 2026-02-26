import { useCallback, useEffect, useRef, useState } from "react";
import type { PitchFrame, StabilityResult, StabilityAnalyzerConfig } from "./types";
import { StabilityAnalyzer } from "./StabilityAnalyzer";

interface UseStabilityAnalyzerOptions {
  targetFrequency: number;
  config?: Partial<Omit<StabilityAnalyzerConfig, "targetFrequency">>;
  enabled?: boolean;
}

interface UseStabilityAnalyzerReturn {
  stability: StabilityResult | null;
  pushFrame: (frame: PitchFrame) => void;
  reset: () => void;
}

export function useStabilityAnalyzer(
  opts: UseStabilityAnalyzerOptions
): UseStabilityAnalyzerReturn {
  const { targetFrequency, config, enabled = true } = opts;

  const [stability, setStability] = useState<StabilityResult | null>(null);
  const analyzerRef = useRef<StabilityAnalyzer | null>(null);

  // Create / recreate analyzer when target frequency changes
  useEffect(() => {
    analyzerRef.current = new StabilityAnalyzer({
      ...config,
      targetFrequency,
    });
    setStability(null);
  }, [targetFrequency]); // eslint-disable-line react-hooks/exhaustive-deps

  const pushFrame = useCallback(
    (frame: PitchFrame) => {
      if (!enabled || !analyzerRef.current) return;
      const result = analyzerRef.current.pushFrame(frame);
      if (result) {
        setStability(result);
      }
    },
    [enabled]
  );

  const reset = useCallback(() => {
    analyzerRef.current?.reset();
    setStability(null);
  }, []);

  return { stability, pushFrame, reset };
}
