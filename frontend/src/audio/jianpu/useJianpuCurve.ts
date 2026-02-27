import { useMemo } from "react";
import type { JianpuCurveConfig, JianpuCurveResult } from "./types";
import { JianpuCurveGenerator } from "./JianpuCurveGenerator";

interface UseJianpuCurveOptions {
  /** Jianpu string to convert. */
  input: string;
  /** Configuration overrides. */
  config?: Partial<JianpuCurveConfig>;
}

/**
 * React hook that converts a jianpu string into a continuous pitch curve.
 * Re-generates when input or config changes.
 */
export function useJianpuCurve(opts: UseJianpuCurveOptions): JianpuCurveResult {
  const { input, config } = opts;

  return useMemo(() => {
    if (!input.trim()) {
      return { curve: [], duration: 0, measureCount: 0, notes: [] };
    }
    const generator = new JianpuCurveGenerator(config);
    return generator.generate(input);
  }, [input, config]);
}
