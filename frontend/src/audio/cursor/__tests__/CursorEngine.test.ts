import { describe, it, expect, vi, beforeEach } from "vitest";
import { CursorEngine } from "../CursorEngine";

// ── Helpers ──────────────────────────────────────────────────

/**
 * Simulate elapsed time by passing explicit `now` values in ms.
 * This avoids dependency on real timers and makes tests deterministic.
 */

// ── State transitions ────────────────────────────────────────

describe("state transitions", () => {
  it("starts in idle", () => {
    const engine = new CursorEngine();
    expect(engine.getState()).toBe("idle");
  });

  it("transitions idle → playing → paused → playing → idle", () => {
    const engine = new CursorEngine();

    engine.start(0);
    expect(engine.getState()).toBe("playing");

    engine.pause(500);
    expect(engine.getState()).toBe("paused");

    engine.resume(1000);
    expect(engine.getState()).toBe("playing");

    engine.stop();
    expect(engine.getState()).toBe("idle");
  });

  it("start is a no-op when already playing", () => {
    const engine = new CursorEngine();
    engine.start(0);
    // Second start should not reset
    engine.start(5000);
    const pos = engine.getPosition(1000);
    // Should still be 1 second in, not reset
    expect(pos.currentTime).toBeCloseTo(1.0, 1);
  });

  it("pause is a no-op when not playing", () => {
    const engine = new CursorEngine();
    engine.pause();
    expect(engine.getState()).toBe("idle");
  });

  it("resume is a no-op when not paused", () => {
    const engine = new CursorEngine();
    engine.start(0);
    engine.resume();
    expect(engine.getState()).toBe("playing");
  });
});

// ── Position computation ────────────────────────────────────

describe("position computation", () => {
  it("returns bar 1, beat 1 at time 0", () => {
    const engine = new CursorEngine({ bpm: 120, beatsPerMeasure: 4 });
    engine.start(0);

    const pos = engine.getPosition(0);
    expect(pos.currentTime).toBe(0);
    expect(pos.currentBar).toBe(1);
    expect(pos.currentBeat).toBeCloseTo(1.0, 2);
    expect(pos.totalBeats).toBe(0);
  });

  it("advances correctly at 120 BPM, 4/4 time", () => {
    const engine = new CursorEngine({ bpm: 120, beatsPerMeasure: 4 });
    engine.start(0);

    // At 120 BPM, 1 beat = 0.5s
    // After 1 second = 2 beats
    const pos = engine.getPosition(1000);
    expect(pos.currentTime).toBeCloseTo(1.0, 2);
    expect(pos.totalBeats).toBeCloseTo(2.0, 2);
    expect(pos.currentBar).toBe(1);
    expect(pos.currentBeat).toBeCloseTo(3.0, 2);
  });

  it("crosses bar lines correctly", () => {
    const engine = new CursorEngine({ bpm: 120, beatsPerMeasure: 4 });
    engine.start(0);

    // 4 beats = 2 seconds → start of bar 2
    const pos = engine.getPosition(2000);
    expect(pos.currentBar).toBe(2);
    expect(pos.currentBeat).toBeCloseTo(1.0, 2);
    expect(pos.totalBeats).toBeCloseTo(4.0, 2);
  });

  it("handles 3/4 time signature", () => {
    const engine = new CursorEngine({ bpm: 120, beatsPerMeasure: 3 });
    engine.start(0);

    // 3 beats = 1.5s → start of bar 2
    const pos = engine.getPosition(1500);
    expect(pos.currentBar).toBe(2);
    expect(pos.currentBeat).toBeCloseTo(1.0, 2);
  });

  it("returns zero position when idle", () => {
    const engine = new CursorEngine();
    const pos = engine.getPosition();
    expect(pos.currentTime).toBe(0);
    expect(pos.currentBar).toBe(1);
    expect(pos.currentBeat).toBe(1);
    expect(pos.totalBeats).toBe(0);
  });
});

// ── Pause / resume timing ───────────────────────────────────

describe("pause/resume", () => {
  it("freezes position during pause", () => {
    const engine = new CursorEngine({ bpm: 120, beatsPerMeasure: 4 });
    engine.start(0);

    engine.pause(1000); // 2 beats elapsed
    const posAtPause = engine.getPosition(1000);

    // Time passes during pause...
    const posLater = engine.getPosition(5000);

    // Position should be the same
    expect(posLater.totalBeats).toBeCloseTo(posAtPause.totalBeats, 2);
    expect(posLater.currentBar).toBe(posAtPause.currentBar);
  });

  it("resumes without counting paused time", () => {
    const engine = new CursorEngine({ bpm: 120, beatsPerMeasure: 4 });
    engine.start(0);

    engine.pause(1000);   // 2 beats in
    engine.resume(3000);  // paused for 2 seconds

    // After resume + 0.5 more seconds → 3 beats total (2 pre-pause + 1 post-resume)
    // At 120 BPM: 0.5s = 1 beat
    const pos = engine.getPosition(3500);
    expect(pos.totalBeats).toBeCloseTo(3.0, 1);
  });
});

// ── Finish condition ────────────────────────────────────────

describe("finish", () => {
  it("transitions to finished when totalMeasures is reached", () => {
    const engine = new CursorEngine({
      bpm: 120,
      beatsPerMeasure: 4,
      totalMeasures: 2,
    });
    engine.start(0);

    // 2 measures × 4 beats × 0.5s/beat = 4s
    engine.getPosition(4000);
    expect(engine.getState()).toBe("finished");
  });

  it("caps beats at total when finished", () => {
    const engine = new CursorEngine({
      bpm: 120,
      beatsPerMeasure: 4,
      totalMeasures: 2,
    });
    engine.start(0);

    // 10 seconds in → way past 2 measures
    const pos = engine.getPosition(10000);
    expect(pos.totalBeats).toBe(8); // 2 measures × 4 beats
  });

  it("does not finish when totalMeasures is 0 (unlimited)", () => {
    const engine = new CursorEngine({
      bpm: 120,
      beatsPerMeasure: 4,
      totalMeasures: 0,
    });
    engine.start(0);

    engine.getPosition(60000); // 1 minute
    expect(engine.getState()).toBe("playing");
  });
});

// ── Resync to bar ───────────────────────────────────────────

describe("resyncToBar", () => {
  it("jumps cursor to the start of a specific bar", () => {
    const engine = new CursorEngine({ bpm: 120, beatsPerMeasure: 4 });
    engine.start(0);

    // Currently at 2 beats (1 second in)
    engine.resyncToBar(3, 1000); // jump to bar 3

    const pos = engine.getPosition(1000);
    // Bar 3 starts at beat 8
    expect(pos.totalBeats).toBeCloseTo(8.0, 1);
    expect(pos.currentBar).toBe(3);
    expect(pos.currentBeat).toBeCloseTo(1.0, 1);
  });

  it("resync forward then continue", () => {
    const engine = new CursorEngine({ bpm: 120, beatsPerMeasure: 4 });
    engine.start(0);

    engine.resyncToBar(2, 0); // jump to bar 2 at time 0

    // After 1 second (2 beats), should be at bar 2, beat 3
    const pos = engine.getPosition(1000);
    expect(pos.currentBar).toBe(2);
    expect(pos.currentBeat).toBeCloseTo(3.0, 1);
  });
});

// ── BPM changes ─────────────────────────────────────────────

describe("setBpm", () => {
  it("changes tempo immediately", () => {
    const engine = new CursorEngine({ bpm: 120, beatsPerMeasure: 4 });
    engine.start(0);

    // At 120 BPM, 1s = 2 beats
    let pos = engine.getPosition(1000);
    expect(pos.totalBeats).toBeCloseTo(2.0, 1);

    // Change to 60 BPM → 1 beat per second
    engine.setBpm(60);
    // After 1 more second at 60 BPM: getPosition computes from total elapsed
    // Total elapsed = 2s → at 60 BPM = 2 beats
    // Note: setBpm changes rate for all elapsed time from start
    pos = engine.getPosition(2000);
    expect(pos.totalBeats).toBeCloseTo(2.0, 1);
  });

  it("ignores invalid BPM", () => {
    const engine = new CursorEngine({ bpm: 120 });
    engine.setBpm(0);
    engine.start(0);
    const pos = engine.getPosition(1000);
    expect(pos.totalBeats).toBeCloseTo(2.0, 1); // still 120 BPM
  });
});

// ── Stop and reset ──────────────────────────────────────────

describe("stop", () => {
  it("resets everything back to idle", () => {
    const engine = new CursorEngine({ bpm: 120, beatsPerMeasure: 4 });
    engine.start(0);
    engine.getPosition(2000);

    engine.stop();
    expect(engine.getState()).toBe("idle");

    const pos = engine.getPosition();
    expect(pos.currentTime).toBe(0);
    expect(pos.totalBeats).toBe(0);
  });
});

// ── Count-in ────────────────────────────────────────────────

describe("count-in", () => {
  it("delays beat counting by countInBeats", () => {
    const engine = new CursorEngine({
      bpm: 120,
      beatsPerMeasure: 4,
      countInBeats: 4,
    });
    engine.start(0);

    // 4 count-in beats at 120 BPM = 2 seconds
    // At 2 seconds, totalBeats should be 0 (count-in just finished)
    const posAtCountInEnd = engine.getPosition(2000);
    expect(posAtCountInEnd.totalBeats).toBeCloseTo(0, 1);

    // At 3 seconds = 2 beats past count-in
    const posAfterCountIn = engine.getPosition(3000);
    expect(posAfterCountIn.totalBeats).toBeCloseTo(2.0, 1);
  });
});

// ── Drift-free timing ───────────────────────────────────────

describe("drift-free timing", () => {
  it("produces consistent positions regardless of query frequency", () => {
    const engine = new CursorEngine({ bpm: 120, beatsPerMeasure: 4 });
    engine.start(0);

    // Query at many irregular intervals, final position at 5000ms
    engine.getPosition(100);
    engine.getPosition(237);
    engine.getPosition(1001);
    engine.getPosition(2999);
    engine.getPosition(4500);

    const pos = engine.getPosition(5000);
    // 5s at 120 BPM = 10 beats exactly
    expect(pos.totalBeats).toBeCloseTo(10.0, 1);
    expect(pos.currentBar).toBe(3);
    expect(pos.currentBeat).toBeCloseTo(3.0, 1);
  });
});
