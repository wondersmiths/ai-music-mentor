"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  getProgress,
  getRecommendation,
  getSessionHistory,
  getStreak,
  getWeeklyGoal,
  setWeeklyGoal,
  type ProgressData,
  type RecommendationData,
  type SessionHistoryData,
  type StreakData,
  type WeeklyGoalData,
} from "@/lib/api";

export default function DashboardPage() {
  const [username, setUsername] = useState<string | null>(null);
  const [progress, setProgress] = useState<ProgressData | null>(null);
  const [recommendation, setRecommendation] = useState<RecommendationData | null>(null);
  const [history, setHistory] = useState<SessionHistoryData | null>(null);
  const [streak, setStreak] = useState<StreakData | null>(null);
  const [goal, setGoal] = useState<WeeklyGoalData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Goal setter state
  const [goalSessions, setGoalSessions] = useState(5);
  const [goalMinutes, setGoalMinutes] = useState(60);
  const [settingGoal, setSettingGoal] = useState(false);

  useEffect(() => {
    const user = typeof window !== "undefined" ? localStorage.getItem("auth_username") : null;
    if (!user) {
      setError("Please login to view your dashboard");
      setLoading(false);
      return;
    }
    setUsername(user);

    Promise.all([
      getProgress(user).catch(() => null),
      getRecommendation(user).catch(() => null),
      getSessionHistory(user).catch(() => null),
      getStreak(user).catch(() => null),
      getWeeklyGoal(user).catch(() => null),
    ]).then(([prog, rec, hist, str, gl]) => {
      setProgress(prog);
      setRecommendation(rec);
      setHistory(hist);
      setStreak(str);
      setGoal(gl);
      setLoading(false);
    });
  }, []);

  const handleSetGoal = useCallback(async () => {
    setSettingGoal(true);
    try {
      const result = await setWeeklyGoal({
        target_sessions: goalSessions,
        target_minutes: goalMinutes,
      });
      setGoal(result);
    } catch {
      // ignore
    }
    setSettingGoal(false);
  }, [goalSessions, goalMinutes]);

  if (loading) {
    return (
      <div style={styles.app}>
        <p style={styles.loading}>Loading dashboard...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={styles.app}>
        <header style={styles.header}>
          <a href="/" style={styles.backLink}>&larr; Home</a>
          <h1 style={styles.h1}>Dashboard</h1>
        </header>
        <div style={styles.error}>{error}</div>
        <a href="/login" style={styles.loginBtn}>Login</a>
      </div>
    );
  }

  const totalExercises = progress?.skills.reduce((acc, s) => acc + s.exercise_count, 0) ?? 0;
  const totalSessions = progress?.total_sessions ?? 0;

  const getSkillScore = (area: string) =>
    progress?.skills.find((s) => s.skill_area === area)?.score ?? 0;

  return (
    <div style={styles.app}>
      <header style={styles.header}>
        <a href="/" style={styles.backLink}>&larr; Home</a>
        <h1 style={styles.h1}>Dashboard</h1>
      </header>

      {/* Stats summary */}
      <div style={styles.statsRow}>
        <div style={styles.statCard}>
          <div style={styles.statValue}>{totalSessions}</div>
          <div style={styles.statLabel}>Sessions</div>
        </div>
        <div style={styles.statCard}>
          <div style={styles.statValue}>{totalExercises}</div>
          <div style={styles.statLabel}>Exercises</div>
        </div>
        <div style={styles.statCard}>
          <div style={styles.statValue}>{streak?.current_streak ?? 0}</div>
          <div style={styles.statLabel}>Day Streak</div>
        </div>
        <div style={styles.statCard}>
          <div style={styles.statValue}>{streak?.longest_streak ?? 0}</div>
          <div style={styles.statLabel}>Best Streak</div>
        </div>
      </div>

      {/* Streak display */}
      {streak && streak.current_streak > 0 && (
        <div style={styles.streakBanner}>
          {streak.current_streak} day streak! Keep it going!
        </div>
      )}

      {/* Weekly goal */}
      <div style={styles.section}>
        <h2 style={styles.sectionTitle}>Weekly Goal</h2>
        {goal ? (
          <div style={styles.goalCard}>
            <div style={styles.goalRow}>
              <span>Sessions: {goal.completed_sessions} / {goal.target_sessions}</span>
              <div style={styles.goalTrack}>
                <div
                  style={{
                    ...styles.goalFill,
                    width: `${Math.min(100, (goal.completed_sessions / goal.target_sessions) * 100)}%`,
                  }}
                />
              </div>
            </div>
            <div style={styles.goalRow}>
              <span>Minutes: {Math.round(goal.completed_minutes)} / {goal.target_minutes}</span>
              <div style={styles.goalTrack}>
                <div
                  style={{
                    ...styles.goalFill,
                    width: `${Math.min(100, (goal.completed_minutes / goal.target_minutes) * 100)}%`,
                    backgroundColor: "#8b5cf6",
                  }}
                />
              </div>
            </div>
          </div>
        ) : (
          <div style={styles.goalSetter}>
            <label style={styles.goalLabel}>
              Sessions/week:
              <input
                type="number"
                min={1}
                max={30}
                value={goalSessions}
                onChange={(e) => setGoalSessions(Number(e.target.value) || 5)}
                style={styles.goalInput}
              />
            </label>
            <label style={styles.goalLabel}>
              Minutes/week:
              <input
                type="number"
                min={10}
                max={600}
                value={goalMinutes}
                onChange={(e) => setGoalMinutes(Number(e.target.value) || 60)}
                style={styles.goalInput}
              />
            </label>
            <button
              style={styles.goalBtn}
              onClick={handleSetGoal}
              disabled={settingGoal}
            >
              {settingGoal ? "Setting..." : "Set Goal"}
            </button>
          </div>
        )}
      </div>

      {/* Skill bars */}
      <div style={styles.section}>
        <h2 style={styles.sectionTitle}>Skills</h2>
        <div style={styles.skillGrid}>
          {["pitch", "stability", "slide", "rhythm"].map((area) => (
            <SkillBar key={area} label={area} score={getSkillScore(area)} />
          ))}
        </div>
      </div>

      {/* Recommendation */}
      {recommendation && (
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>Recommendation</h2>
          <div style={styles.recCard}>
            <div style={styles.recExercise}>
              {recommendation.recommended_exercise.replace("_", " ")}
            </div>
            <p style={styles.recMessage}>{recommendation.message}</p>
            {recommendation.focus_areas.length > 0 && (
              <div style={styles.recFocus}>
                Focus: {recommendation.focus_areas.join(", ")}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Session history */}
      <div style={styles.section}>
        <h2 style={styles.sectionTitle}>Recent Sessions</h2>
        {history && history.sessions.length > 0 ? (
          <div style={styles.historyTable}>
            <div style={styles.historyHeader}>
              <span style={styles.historyCol}>Date</span>
              <span style={styles.historyCol}>Exercises</span>
              <span style={styles.historyCol}>Score</span>
              <span style={styles.historyCol}>Duration</span>
            </div>
            {history.sessions.map((s) => (
              <div key={s.session_id} style={styles.historyRow}>
                <span style={styles.historyCol}>
                  {s.started_at ? new Date(s.started_at).toLocaleDateString() : "—"}
                </span>
                <span style={styles.historyCol}>{s.exercise_count}</span>
                <span style={{
                  ...styles.historyCol,
                  color: s.overall_score
                    ? s.overall_score >= 80
                      ? "#22c55e"
                      : s.overall_score >= 60
                        ? "#eab308"
                        : "#ef4444"
                    : "#94a3b8",
                  fontWeight: 600,
                }}>
                  {s.overall_score ? `${Math.round(s.overall_score)}%` : "—"}
                </span>
                <span style={styles.historyCol}>
                  {s.duration_s > 0 ? `${Math.round(s.duration_s)}s` : "—"}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p style={styles.emptyText}>No sessions yet. Start practicing!</p>
        )}
      </div>
    </div>
  );
}

function SkillBar({ label, score }: { label: string; score: number }) {
  const color = score >= 80 ? "#22c55e" : score >= 60 ? "#eab308" : "#ef4444";
  return (
    <div style={styles.skillBarContainer}>
      <div style={styles.skillBarLabel}>
        <span style={{ textTransform: "capitalize" as const }}>{label}</span>
        <span style={{ fontWeight: 700 }}>{Math.round(score)}%</span>
      </div>
      <div style={styles.skillBarTrack}>
        <div
          style={{
            height: "100%",
            borderRadius: 4,
            transition: "width 0.5s ease",
            width: `${score}%`,
            backgroundColor: color,
          }}
        />
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  app: {
    maxWidth: 960,
    margin: "0 auto",
    padding: "24px 16px",
    fontFamily: "Inter, system-ui, sans-serif",
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: 16,
    marginBottom: 24,
  },
  h1: { fontSize: 22, fontWeight: 700, color: "#1e293b", margin: 0 },
  backLink: { fontSize: 14, color: "#3b82f6", textDecoration: "none", fontWeight: 500 },
  loading: { textAlign: "center" as const, color: "#64748b", padding: "40px 0" },
  error: { padding: "8px 12px", backgroundColor: "#fef2f2", color: "#dc2626", borderRadius: 6, marginBottom: 16, fontSize: 14 },
  loginBtn: {
    display: "inline-block",
    padding: "8px 16px",
    backgroundColor: "#3b82f6",
    color: "#fff",
    borderRadius: 6,
    fontSize: 14,
    fontWeight: 500,
    textDecoration: "none",
  },

  // Stats
  statsRow: { display: "flex", gap: 12, marginBottom: 20 },
  statCard: {
    flex: 1,
    textAlign: "center" as const,
    padding: "16px 8px",
    backgroundColor: "#fff",
    borderRadius: 8,
    border: "1px solid #e2e8f0",
  },
  statValue: { fontSize: 24, fontWeight: 700, color: "#1e293b" },
  statLabel: { fontSize: 12, color: "#64748b", marginTop: 4 },

  // Streak
  streakBanner: {
    padding: "10px 16px",
    backgroundColor: "#fef3c7",
    color: "#92400e",
    borderRadius: 8,
    fontSize: 14,
    fontWeight: 600,
    textAlign: "center" as const,
    marginBottom: 20,
  },

  // Section
  section: { marginBottom: 24 },
  sectionTitle: { fontSize: 16, fontWeight: 600, color: "#1e293b", margin: "0 0 12px 0" },

  // Weekly goal
  goalCard: { padding: 16, backgroundColor: "#fff", borderRadius: 8, border: "1px solid #e2e8f0" },
  goalRow: { display: "flex", alignItems: "center", gap: 12, marginBottom: 8, fontSize: 13, color: "#475569" },
  goalTrack: { flex: 1, height: 8, backgroundColor: "#e2e8f0", borderRadius: 4, overflow: "hidden" },
  goalFill: { height: "100%", borderRadius: 4, backgroundColor: "#22c55e", transition: "width 0.5s" },
  goalSetter: { display: "flex", gap: 12, alignItems: "flex-end" },
  goalLabel: { display: "flex", flexDirection: "column" as const, gap: 4, fontSize: 13, fontWeight: 500, color: "#475569" },
  goalInput: { width: 80, padding: "6px 8px", border: "1px solid #cbd5e1", borderRadius: 6, fontSize: 14, textAlign: "center" as const },
  goalBtn: { padding: "8px 16px", backgroundColor: "#3b82f6", color: "#fff", border: "none", borderRadius: 6, fontSize: 14, fontWeight: 500, cursor: "pointer" },

  // Skills
  skillGrid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 },
  skillBarContainer: {},
  skillBarLabel: { display: "flex", justifyContent: "space-between", fontSize: 13, color: "#475569", marginBottom: 4 },
  skillBarTrack: { height: 8, backgroundColor: "#e2e8f0", borderRadius: 4, overflow: "hidden" },

  // Recommendation
  recCard: { padding: 16, backgroundColor: "#eff6ff", borderRadius: 8, border: "1px solid #bfdbfe" },
  recExercise: { fontSize: 16, fontWeight: 600, color: "#1e40af", textTransform: "capitalize" as const, marginBottom: 4 },
  recMessage: { fontSize: 14, color: "#475569", lineHeight: 1.5, margin: "0 0 8px 0" },
  recFocus: { fontSize: 13, color: "#64748b" },

  // History
  historyTable: { backgroundColor: "#fff", borderRadius: 8, border: "1px solid #e2e8f0", overflow: "hidden" },
  historyHeader: { display: "flex", padding: "8px 12px", backgroundColor: "#f8fafc", borderBottom: "1px solid #e2e8f0", fontSize: 12, fontWeight: 600, color: "#64748b" },
  historyRow: { display: "flex", padding: "8px 12px", borderBottom: "1px solid #f1f5f9", fontSize: 13, color: "#475569" },
  historyCol: { flex: 1 },
  emptyText: { fontSize: 14, color: "#94a3b8", textAlign: "center" as const, padding: "20px 0" },
};
