/**
 * React hook for the Web Audio metronome.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Metronome } from "./Metronome";

interface UseMetronomeOptions {
  bpm: number;
  beatsPerMeasure?: number;
  enabled?: boolean;
}

export function useMetronome({
  bpm,
  beatsPerMeasure = 4,
  enabled = false,
}: UseMetronomeOptions) {
  const metroRef = useRef<Metronome | null>(null);
  const [currentBeat, setCurrentBeat] = useState(0);
  const [isAccent, setIsAccent] = useState(false);

  useEffect(() => {
    if (!enabled) {
      if (metroRef.current) {
        metroRef.current.stop();
        metroRef.current = null;
      }
      setCurrentBeat(0);
      return;
    }

    const metro = new Metronome({ bpm, beatsPerMeasure });
    metro.onBeat = (beat, accent) => {
      setCurrentBeat(beat);
      setIsAccent(accent);
    };
    metro.start();
    metroRef.current = metro;

    return () => {
      metro.stop();
      metroRef.current = null;
    };
  }, [bpm, beatsPerMeasure, enabled]);

  const stop = useCallback(() => {
    if (metroRef.current) {
      metroRef.current.stop();
      metroRef.current = null;
    }
    setCurrentBeat(0);
  }, []);

  return { currentBeat, isAccent, stop };
}
