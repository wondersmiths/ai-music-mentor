import { describe, it, expect, vi, beforeEach } from "vitest";
import { SessionRecorder } from "../SessionRecorder";
import type { PitchFrame } from "../types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeFrame(frequency: number, confidence = 0.9, time = 0): PitchFrame {
  return { frequency, confidence, time };
}

// Stable mock for crypto.randomUUID
beforeEach(() => {
  vi.stubGlobal("crypto", {
    randomUUID: vi.fn().mockReturnValue("test-uuid-1234"),
  });
});

// ---------------------------------------------------------------------------
// Start / stop lifecycle
// ---------------------------------------------------------------------------

describe("start/stop lifecycle", () => {
  it("transitions idle → recording → stopped", () => {
    const rec = new SessionRecorder("long_tone");
    expect(rec.getState()).toBe("idle");

    rec.start();
    expect(rec.getState()).toBe("recording");

    rec.stop();
    expect(rec.getState()).toBe("stopped");
  });

  it("start() is a no-op when already recording", () => {
    const rec = new SessionRecorder("long_tone");
    rec.start();
    rec.pushFrame(makeFrame(440, 0.9, 0));
    rec.start(); // should not reset
    expect(rec.getFrameCount()).toBe(1);
  });

  it("stop() is a no-op when idle", () => {
    const rec = new SessionRecorder("long_tone");
    rec.stop();
    expect(rec.getState()).toBe("idle");
  });
});

// ---------------------------------------------------------------------------
// Frame recording
// ---------------------------------------------------------------------------

describe("frame recording", () => {
  it("records frames with rebased timestamps", () => {
    const rec = new SessionRecorder("long_tone");
    rec.start();

    rec.pushFrame(makeFrame(440, 0.9, 10.0));
    rec.pushFrame(makeFrame(441, 0.8, 10.5));
    rec.pushFrame(makeFrame(442, 0.7, 11.0));

    rec.stop();
    const session = rec.getSession()!;

    expect(session.frameCount).toBe(3);
    expect(session.frames[0].time).toBeCloseTo(0, 5);
    expect(session.frames[1].time).toBeCloseTo(0.5, 5);
    expect(session.frames[2].time).toBeCloseTo(1.0, 5);
    expect(session.frames[0].frequency).toBe(440);
    expect(session.frames[1].frequency).toBe(441);
    expect(session.frames[2].frequency).toBe(442);
  });
});

// ---------------------------------------------------------------------------
// Duration limit
// ---------------------------------------------------------------------------

describe("duration limit", () => {
  it("auto-stops when elapsed reaches maxDuration", () => {
    const rec = new SessionRecorder("long_tone", { maxDuration: 2 });
    rec.start();

    rec.pushFrame(makeFrame(440, 0.9, 0));
    rec.pushFrame(makeFrame(440, 0.9, 1.0));
    expect(rec.getState()).toBe("recording");

    // This frame is at exactly maxDuration — triggers auto-stop
    rec.pushFrame(makeFrame(440, 0.9, 2.0));
    expect(rec.getState()).toBe("stopped");
  });

  it("rejects frames after auto-stop", () => {
    const rec = new SessionRecorder("long_tone", { maxDuration: 1 });
    rec.start();

    rec.pushFrame(makeFrame(440, 0.9, 0));
    rec.pushFrame(makeFrame(440, 0.9, 1.0)); // triggers auto-stop

    const countBefore = rec.getFrameCount();
    rec.pushFrame(makeFrame(440, 0.9, 1.5)); // should be rejected
    expect(rec.getFrameCount()).toBe(countBefore);
  });
});

// ---------------------------------------------------------------------------
// Ignore when not recording
// ---------------------------------------------------------------------------

describe("ignore when not recording", () => {
  it("pushFrame in idle state has no effect", () => {
    const rec = new SessionRecorder("long_tone");
    rec.pushFrame(makeFrame(440, 0.9, 0));
    expect(rec.getFrameCount()).toBe(0);
  });

  it("pushFrame in stopped state has no effect", () => {
    const rec = new SessionRecorder("long_tone");
    rec.start();
    rec.pushFrame(makeFrame(440, 0.9, 0));
    rec.stop();

    rec.pushFrame(makeFrame(440, 0.9, 1));
    expect(rec.getFrameCount()).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// Zero-frequency filtering
// ---------------------------------------------------------------------------

describe("zero-frequency filtering", () => {
  it("excludes frames with frequency = 0", () => {
    const rec = new SessionRecorder("long_tone");
    rec.start();

    rec.pushFrame(makeFrame(440, 0.9, 0));
    rec.pushFrame(makeFrame(0, 0.9, 0.5)); // silence — skipped
    rec.pushFrame(makeFrame(441, 0.9, 1.0));

    expect(rec.getFrameCount()).toBe(2);
  });

  it("excludes frames with negative frequency", () => {
    const rec = new SessionRecorder("long_tone");
    rec.start();

    rec.pushFrame(makeFrame(-1, 0.9, 0));
    expect(rec.getFrameCount()).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// Session export
// ---------------------------------------------------------------------------

describe("session export", () => {
  it("returns correct PracticeSession shape", () => {
    const rec = new SessionRecorder("scale", { framesPerSecond: 25 });
    rec.start();

    rec.pushFrame(makeFrame(440, 0.9, 5.0));
    rec.pushFrame(makeFrame(441, 0.8, 5.5));
    rec.stop();

    const session = rec.getSession()!;

    expect(session.id).toBe("test-uuid-1234");
    expect(session.exerciseType).toBe("scale");
    expect(session.startedAt).toMatch(/^\d{4}-\d{2}-\d{2}T/); // ISO 8601
    expect(session.duration).toBeCloseTo(0.5, 5);
    expect(session.frameCount).toBe(2);
    expect(session.framesPerSecond).toBe(25);
    expect(session.frames).toHaveLength(2);
  });

  it("returns null when not stopped", () => {
    const rec = new SessionRecorder("long_tone");
    expect(rec.getSession()).toBeNull();

    rec.start();
    expect(rec.getSession()).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// JSON export
// ---------------------------------------------------------------------------

describe("JSON export", () => {
  it("produces valid parseable JSON matching the session", () => {
    const rec = new SessionRecorder("melody");
    rec.start();

    rec.pushFrame(makeFrame(440, 0.9, 0));
    rec.pushFrame(makeFrame(441, 0.8, 0.5));
    rec.stop();

    const json = rec.toJSON()!;
    expect(json).toBeTruthy();

    const parsed = JSON.parse(json);
    const session = rec.getSession()!;

    expect(parsed.id).toBe(session.id);
    expect(parsed.exerciseType).toBe(session.exerciseType);
    expect(parsed.frameCount).toBe(session.frameCount);
    expect(parsed.frames).toHaveLength(session.frames.length);
  });

  it("returns null when not stopped", () => {
    const rec = new SessionRecorder("long_tone");
    expect(rec.toJSON()).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Reset
// ---------------------------------------------------------------------------

describe("reset", () => {
  it("clears all data and returns to idle", () => {
    const rec = new SessionRecorder("long_tone");
    rec.start();
    rec.pushFrame(makeFrame(440, 0.9, 0));
    rec.pushFrame(makeFrame(441, 0.9, 0.5));
    rec.stop();

    expect(rec.getState()).toBe("stopped");
    expect(rec.getFrameCount()).toBe(2);

    rec.reset();
    expect(rec.getState()).toBe("idle");
    expect(rec.getFrameCount()).toBe(0);
    expect(rec.getElapsed()).toBe(0);
    expect(rec.getSession()).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Elapsed tracking
// ---------------------------------------------------------------------------

describe("elapsed tracking", () => {
  it("elapsed increases with frames", () => {
    const rec = new SessionRecorder("long_tone");
    rec.start();

    rec.pushFrame(makeFrame(440, 0.9, 0));
    expect(rec.getElapsed()).toBeCloseTo(0, 5);

    rec.pushFrame(makeFrame(440, 0.9, 1.5));
    expect(rec.getElapsed()).toBeCloseTo(1.5, 5);

    rec.pushFrame(makeFrame(440, 0.9, 3.0));
    expect(rec.getElapsed()).toBeCloseTo(3.0, 5);
  });
});

// ---------------------------------------------------------------------------
// Frame count
// ---------------------------------------------------------------------------

describe("frame count", () => {
  it("tracks accepted frame count", () => {
    const rec = new SessionRecorder("long_tone");
    rec.start();

    expect(rec.getFrameCount()).toBe(0);
    rec.pushFrame(makeFrame(440, 0.9, 0));
    expect(rec.getFrameCount()).toBe(1);
    rec.pushFrame(makeFrame(0, 0.9, 0.5)); // skipped (zero freq)
    expect(rec.getFrameCount()).toBe(1);
    rec.pushFrame(makeFrame(441, 0.5, 1.0));
    expect(rec.getFrameCount()).toBe(2);
  });
});

// ---------------------------------------------------------------------------
// Multiple sessions
// ---------------------------------------------------------------------------

describe("multiple sessions", () => {
  it("reset + re-record produces independent session", () => {
    const rec = new SessionRecorder("long_tone");

    // First session
    rec.start();
    rec.pushFrame(makeFrame(440, 0.9, 0));
    rec.pushFrame(makeFrame(441, 0.9, 0.5));
    rec.stop();
    const session1 = rec.getSession()!;
    expect(session1.frameCount).toBe(2);

    // Reset and record again
    rec.reset();
    rec.start();
    rec.pushFrame(makeFrame(880, 0.9, 10.0));
    rec.stop();
    const session2 = rec.getSession()!;

    expect(session2.frameCount).toBe(1);
    expect(session2.frames[0].frequency).toBe(880);
    expect(session2.frames[0].time).toBeCloseTo(0, 5); // rebased from 10.0
  });
});
