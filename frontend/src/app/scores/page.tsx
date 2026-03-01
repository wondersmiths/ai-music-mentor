"use client";

import React, { useCallback, useEffect, useState } from "react";
import { listScores, deleteScore, saveScore, type SavedScore } from "@/lib/api";

export default function ScoresPage() {
  const [scores, setScores] = useState<SavedScore[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [authUser, setAuthUser] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newNotation, setNewNotation] = useState("");
  const [newKey, setNewKey] = useState("");
  const [newInstrument, setNewInstrument] = useState("");

  useEffect(() => {
    if (typeof window !== "undefined") {
      setAuthUser(localStorage.getItem("auth_username"));
    }
  }, []);

  const fetchScores = useCallback(async () => {
    try {
      setError("");
      const data = await listScores();
      setScores(data);
    } catch {
      setError("Failed to load scores");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchScores();
  }, [fetchScores]);

  const handleDelete = useCallback(
    async (id: number) => {
      try {
        await deleteScore(id);
        setScores((prev) => prev.filter((s) => s.id !== id));
      } catch {
        setError("Failed to delete score");
      }
    },
    [],
  );

  const handleCreate = useCallback(async () => {
    if (!newTitle.trim() || !newNotation.trim()) return;
    setCreating(true);
    setError("");
    try {
      const created = await saveScore({
        title: newTitle.trim(),
        jianpu_notation: newNotation.trim(),
        key_signature: newKey.trim() || undefined,
        instrument: newInstrument.trim() || undefined,
      });
      setScores((prev) => [...prev, created]);
      setNewTitle("");
      setNewNotation("");
      setNewKey("");
      setNewInstrument("");
      setShowCreate(false);
    } catch {
      setError("Failed to save score");
    } finally {
      setCreating(false);
    }
  }, [newTitle, newNotation, newKey, newInstrument]);

  const builtinScores = scores.filter((s) => s.is_builtin);
  const userScores = scores.filter((s) => !s.is_builtin);

  return (
    <div style={styles.page}>
      <header style={styles.header}>
        <div>
          <h1 style={styles.h1}>Score Library</h1>
          <p style={styles.subtitle}>
            Browse built-in exercises and your saved scores
          </p>
        </div>
        <a href="/" style={styles.backLink}>Home</a>
      </header>

      {error && <div style={styles.error}>{error}</div>}

      {loading ? (
        <p style={styles.loading}>Loading scores...</p>
      ) : (
        <>
          {/* Built-in scores */}
          <section style={styles.section}>
            <h2 style={styles.sectionTitle}>
              Built-in Scores ({builtinScores.length})
            </h2>
            {builtinScores.length === 0 ? (
              <p style={styles.empty}>No built-in scores available.</p>
            ) : (
              <div style={styles.grid}>
                {builtinScores.map((s) => (
                  <ScoreCard key={s.id} score={s} />
                ))}
              </div>
            )}
          </section>

          {/* User scores */}
          <section style={styles.section}>
            <div style={styles.sectionHeader}>
              <h2 style={styles.sectionTitle}>
                My Scores ({userScores.length})
              </h2>
              {authUser && (
                <button
                  style={styles.newBtn}
                  onClick={() => setShowCreate((v) => !v)}
                >
                  {showCreate ? "Cancel" : "+ New Score"}
                </button>
              )}
            </div>

            {authUser && showCreate && (
              <div style={styles.createForm}>
                <label style={styles.formLabel}>
                  Title *
                  <input
                    style={styles.formInput}
                    value={newTitle}
                    onChange={(e) => setNewTitle(e.target.value)}
                    placeholder="e.g. My Practice Melody"
                  />
                </label>
                <label style={styles.formLabel}>
                  Jianpu Notation *
                  <textarea
                    style={styles.formTextarea}
                    value={newNotation}
                    onChange={(e) => setNewNotation(e.target.value)}
                    placeholder="e.g. 1 1 5 5 | 6 6 5 - | 4 4 3 3 | 2 2 1 -"
                    rows={3}
                  />
                </label>
                <div style={styles.formRow}>
                  <label style={styles.formLabel}>
                    Key Signature
                    <input
                      style={styles.formInput}
                      value={newKey}
                      onChange={(e) => setNewKey(e.target.value)}
                      placeholder="e.g. 1=D"
                    />
                  </label>
                  <label style={styles.formLabel}>
                    Instrument
                    <input
                      style={styles.formInput}
                      value={newInstrument}
                      onChange={(e) => setNewInstrument(e.target.value)}
                      placeholder="e.g. erhu"
                    />
                  </label>
                </div>
                <button
                  style={{
                    ...styles.saveBtn,
                    ...(creating || !newTitle.trim() || !newNotation.trim()
                      ? styles.saveBtnDisabled
                      : {}),
                  }}
                  disabled={creating || !newTitle.trim() || !newNotation.trim()}
                  onClick={handleCreate}
                >
                  {creating ? "Saving..." : "Save Score"}
                </button>
              </div>
            )}

            {!authUser ? (
              <p style={styles.empty}>
                <a href="/login" style={styles.link}>Log in</a> to save and
                manage your own scores.
              </p>
            ) : userScores.length === 0 && !showCreate ? (
              <p style={styles.empty}>
                No saved scores yet. Click &quot;+ New Score&quot; to create one.
              </p>
            ) : (
              <div style={styles.grid}>
                {userScores.map((s) => (
                  <ScoreCard
                    key={s.id}
                    score={s}
                    onDelete={() => handleDelete(s.id)}
                  />
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}

function ScoreCard({
  score,
  onDelete,
}: {
  score: SavedScore;
  onDelete?: () => void;
}) {
  return (
    <div style={styles.card}>
      <div style={styles.cardTop}>
        <h3 style={styles.cardTitle}>{score.title}</h3>
        {score.is_builtin && <span style={styles.badge}>Built-in</span>}
      </div>
      <p style={styles.notation}>{score.jianpu_notation}</p>
      <div style={styles.cardMeta}>
        {score.key_signature && (
          <span style={styles.metaItem}>Key: {score.key_signature}</span>
        )}
        {score.instrument && (
          <span style={styles.metaItem}>{score.instrument}</span>
        )}
      </div>
      {onDelete && (
        <button style={styles.deleteBtn} onClick={onDelete}>
          Delete
        </button>
      )}
    </div>
  );
}

// ── Styles ──────────────────────────────────────────────────

const styles: Record<string, React.CSSProperties> = {
  page: {
    maxWidth: 840,
    margin: "0 auto",
    padding: "32px 20px",
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 32,
  },
  h1: { fontSize: 22, fontWeight: 700, color: "#1e293b", margin: 0 },
  subtitle: { fontSize: 14, color: "#64748b", margin: "4px 0 0 0" },
  backLink: {
    fontSize: 14,
    fontWeight: 500,
    color: "#3b82f6",
    textDecoration: "none",
  },
  error: {
    padding: "8px 12px",
    backgroundColor: "#fef2f2",
    color: "#dc2626",
    borderRadius: 6,
    marginBottom: 16,
    fontSize: 14,
  },
  loading: { fontSize: 14, color: "#64748b" },
  section: { marginBottom: 32 },
  sectionHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: 600,
    color: "#1e293b",
    margin: 0,
  },
  newBtn: {
    padding: "6px 14px",
    backgroundColor: "#3b82f6",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
  },
  createForm: {
    padding: 16,
    border: "1px solid #e2e8f0",
    borderRadius: 10,
    backgroundColor: "#f8fafc",
    marginBottom: 12,
    display: "flex",
    flexDirection: "column" as const,
    gap: 12,
  },
  formLabel: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 4,
    fontSize: 13,
    fontWeight: 500,
    color: "#475569",
    flex: 1,
  },
  formInput: {
    padding: "8px 10px",
    border: "1px solid #cbd5e1",
    borderRadius: 6,
    fontSize: 14,
    outline: "none",
  },
  formTextarea: {
    padding: "8px 10px",
    border: "1px solid #cbd5e1",
    borderRadius: 6,
    fontSize: 14,
    outline: "none",
    resize: "vertical" as const,
    fontFamily: "monospace",
  },
  formRow: {
    display: "flex",
    gap: 12,
  },
  saveBtn: {
    padding: "8px 16px",
    backgroundColor: "#22c55e",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
    alignSelf: "flex-start" as const,
  },
  saveBtnDisabled: {
    opacity: 0.5,
    cursor: "not-allowed",
  },
  empty: { fontSize: 14, color: "#94a3b8" },
  link: { color: "#3b82f6", textDecoration: "none", fontWeight: 500 },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(2, 1fr)",
    gap: 12,
  },
  card: {
    padding: 16,
    border: "1px solid #e2e8f0",
    borderRadius: 10,
    backgroundColor: "#fff",
  },
  cardTop: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
  },
  cardTitle: {
    fontSize: 14,
    fontWeight: 600,
    color: "#1e293b",
    margin: 0,
  },
  badge: {
    fontSize: 11,
    fontWeight: 600,
    color: "#3b82f6",
    backgroundColor: "#eff6ff",
    padding: "2px 8px",
    borderRadius: 4,
  },
  notation: {
    fontSize: 13,
    color: "#475569",
    lineHeight: 1.5,
    margin: "0 0 8px 0",
    whiteSpace: "nowrap" as const,
    overflow: "hidden",
    textOverflow: "ellipsis",
  },
  cardMeta: {
    display: "flex",
    gap: 12,
    fontSize: 12,
    color: "#94a3b8",
  },
  metaItem: {},
  deleteBtn: {
    marginTop: 8,
    padding: "4px 10px",
    backgroundColor: "transparent",
    color: "#ef4444",
    border: "1px solid #fecaca",
    borderRadius: 4,
    fontSize: 12,
    cursor: "pointer",
  },
};
