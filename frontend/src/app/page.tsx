"use client";

import React, { useCallback, useEffect, useState } from "react";

const FEATURES = [
  {
    title: "Practice",
    href: "/practice",
    description:
      "Record exercises with real-time pitch detection, guided metronome, and instant AI evaluation. No account needed.",
    icon: "\u{1F3B5}",
    authRequired: false,
  },
  {
    title: "Dashboard",
    href: "/dashboard",
    description:
      "Track your skill progress, view session history, manage streaks, and set weekly goals. Requires login.",
    icon: "\u{1F4CA}",
    authRequired: true,
  },
  {
    title: "Score Library",
    href: "/practice",
    description:
      "Browse built-in scores and upload your own sheet music from within the practice page.",
    icon: "\u{1F4DA}",
    authRequired: false,
  },
  {
    title: "Teacher",
    href: "/teacher",
    description:
      "Create assignments, monitor student progress, and manage your studio. Requires login.",
    icon: "\u{1F393}",
    authRequired: true,
  },
];

const STEPS = [
  { num: 1, text: "Choose an exercise — long tone, scale, or melody" },
  { num: 2, text: "Hit record and play along with the metronome" },
  { num: 3, text: "Get instant AI feedback on pitch and rhythm" },
];

const INSTRUMENTS = [
  "Erhu (二胡)",
  "Violin",
  "Flute",
  "Cello",
  "Trumpet",
  "Clarinet",
  "Zhongruan (中阮)",
];

export default function Home() {
  const [authUser, setAuthUser] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      setAuthUser(localStorage.getItem("auth_username"));
    }
  }, []);

  const handleLogout = useCallback(() => {
    localStorage.removeItem("auth_token");
    localStorage.removeItem("auth_username");
    setAuthUser(null);
  }, []);

  return (
    <div style={styles.app}>
      {/* Header */}
      <header style={styles.header}>
        <h1 style={styles.h1}>AI Music Mentor</h1>
        <div style={styles.authArea}>
          {authUser ? (
            <>
              <span style={styles.authUser}>{authUser}</span>
              <button style={styles.logoutBtn} onClick={handleLogout}>
                Logout
              </button>
            </>
          ) : (
            <a href="/login" style={styles.loginLink}>
              Login
            </a>
          )}
        </div>
      </header>

      {/* Hero */}
      <section style={styles.hero}>
        <h2 style={styles.heroTitle}>Your AI-powered music practice partner</h2>
        <p style={styles.heroSub}>
          Record your playing, get instant pitch and rhythm analysis, and follow
          a personalised practice plan — all in your browser.
        </p>
        <a href="/practice" style={styles.ctaBtn}>
          Start Practicing
        </a>
      </section>

      {/* Feature cards */}
      <section style={styles.grid}>
        {FEATURES.map((f) => (
          <a
            key={f.title}
            href={f.authRequired && !authUser ? "/login" : f.href}
            style={styles.card}
          >
            <span style={styles.cardIcon}>{f.icon}</span>
            <h3 style={styles.cardTitle}>{f.title}</h3>
            <p style={styles.cardDesc}>{f.description}</p>
          </a>
        ))}
      </section>

      {/* Quick start */}
      <section style={styles.quickStart}>
        <h3 style={styles.qsTitle}>Quick Start</h3>
        <div style={styles.steps}>
          {STEPS.map((s) => (
            <div key={s.num} style={styles.step}>
              <span style={styles.stepNum}>{s.num}</span>
              <span style={styles.stepText}>{s.text}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer style={styles.footer}>
        <span style={styles.footerLabel}>Supported instruments:</span>
        <span style={styles.footerList}>{INSTRUMENTS.join(" · ")}</span>
      </footer>
    </div>
  );
}

// ── Styles ──────────────────────────────────────────────────

const styles: Record<string, React.CSSProperties> = {
  app: {
    maxWidth: 840,
    margin: "0 auto",
    padding: "32px 20px",
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 40,
  },
  h1: { fontSize: 22, fontWeight: 700, color: "#1e293b", margin: 0 },
  authArea: { display: "flex", alignItems: "center", gap: 8 },
  authUser: { fontSize: 13, color: "#475569", fontWeight: 500 },
  logoutBtn: {
    padding: "4px 10px",
    backgroundColor: "transparent",
    color: "#64748b",
    border: "1px solid #cbd5e1",
    borderRadius: 4,
    fontSize: 12,
    cursor: "pointer",
  },
  loginLink: {
    fontSize: 14,
    fontWeight: 500,
    color: "#3b82f6",
    textDecoration: "none",
  },

  /* Hero */
  hero: {
    textAlign: "center" as const,
    marginBottom: 48,
  },
  heroTitle: {
    fontSize: 28,
    fontWeight: 700,
    color: "#0f172a",
    margin: "0 0 12px 0",
  },
  heroSub: {
    fontSize: 16,
    color: "#475569",
    lineHeight: 1.6,
    maxWidth: 560,
    margin: "0 auto 24px auto",
  },
  ctaBtn: {
    display: "inline-block",
    padding: "12px 28px",
    backgroundColor: "#22c55e",
    color: "#fff",
    borderRadius: 8,
    fontSize: 15,
    fontWeight: 600,
    textDecoration: "none",
  },

  /* Feature cards */
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(2, 1fr)",
    gap: 16,
    marginBottom: 48,
  },
  card: {
    padding: 20,
    border: "1px solid #e2e8f0",
    borderRadius: 12,
    textDecoration: "none",
    color: "inherit",
    transition: "box-shadow .15s",
  },
  cardIcon: { fontSize: 28, display: "block", marginBottom: 8 },
  cardTitle: {
    fontSize: 16,
    fontWeight: 600,
    color: "#1e293b",
    margin: "0 0 6px 0",
  },
  cardDesc: {
    fontSize: 13,
    color: "#64748b",
    lineHeight: 1.5,
    margin: 0,
  },

  /* Quick start */
  quickStart: {
    backgroundColor: "#f8fafc",
    border: "1px solid #e2e8f0",
    borderRadius: 12,
    padding: 24,
    marginBottom: 40,
  },
  qsTitle: {
    fontSize: 16,
    fontWeight: 600,
    color: "#1e293b",
    margin: "0 0 16px 0",
  },
  steps: { display: "flex", flexDirection: "column" as const, gap: 12 },
  step: { display: "flex", alignItems: "center", gap: 12 },
  stepNum: {
    width: 28,
    height: 28,
    borderRadius: "50%",
    backgroundColor: "#3b82f6",
    color: "#fff",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 13,
    fontWeight: 700,
    flexShrink: 0,
  },
  stepText: { fontSize: 14, color: "#334155" },

  /* Footer */
  footer: {
    textAlign: "center" as const,
    fontSize: 13,
    color: "#94a3b8",
  },
  footerLabel: { fontWeight: 600, marginRight: 6 },
  footerList: {},
};
