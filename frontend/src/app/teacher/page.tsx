"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  getMe,
  listAssignments,
  createAssignment,
  getStudentProgress,
  listScores,
  type UserInfo,
  type AssignmentData,
  type SavedScore,
  type ProgressData,
} from "@/lib/api";

export default function TeacherPage() {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [assignments, setAssignments] = useState<AssignmentData[]>([]);
  const [scores, setScores] = useState<SavedScore[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Assignment form
  const [studentUsername, setStudentUsername] = useState("");
  const [assignTitle, setAssignTitle] = useState("");
  const [assignScoreId, setAssignScoreId] = useState<number | "">("");
  const [assignNotes, setAssignNotes] = useState("");
  const [assignDueDate, setAssignDueDate] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  // Student progress viewer
  const [selectedStudentId, setSelectedStudentId] = useState<number | null>(null);
  const [studentProgress, setStudentProgress] = useState<ProgressData | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const me = await getMe();
        if (me.role !== "teacher") {
          setError("This page is for teachers only.");
          setLoading(false);
          return;
        }
        setUser(me);

        const [assignData, scoreData] = await Promise.all([
          listAssignments().catch(() => []),
          listScores().catch(() => []),
        ]);
        setAssignments(assignData);
        setScores(scoreData);
      } catch {
        setError("Please login as a teacher to access this page.");
      }
      setLoading(false);
    })();
  }, []);

  const handleCreateAssignment = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError("");
    setCreating(true);
    try {
      const newAssignment = await createAssignment({
        student_username: studentUsername,
        title: assignTitle,
        score_id: assignScoreId ? Number(assignScoreId) : undefined,
        notes: assignNotes || undefined,
        due_date: assignDueDate || undefined,
      });
      setAssignments((prev) => [newAssignment, ...prev]);
      setStudentUsername("");
      setAssignTitle("");
      setAssignScoreId("");
      setAssignNotes("");
      setAssignDueDate("");
    } catch (err: unknown) {
      const detail = err && typeof err === "object" && "detail" in err
        ? (err as { detail: string }).detail
        : "Failed to create assignment";
      setCreateError(detail);
    }
    setCreating(false);
  }, [studentUsername, assignTitle, assignScoreId, assignNotes, assignDueDate]);

  const handleViewStudentProgress = useCallback(async (studentId: number) => {
    if (selectedStudentId === studentId) {
      setSelectedStudentId(null);
      setStudentProgress(null);
      return;
    }
    try {
      const prog = await getStudentProgress(studentId);
      setStudentProgress(prog);
      setSelectedStudentId(studentId);
    } catch {
      // ignore
    }
  }, [selectedStudentId]);

  if (loading) {
    return (
      <div style={styles.app}>
        <p style={styles.loading}>Loading...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={styles.app}>
        <header style={styles.header}>
          <a href="/" style={styles.backLink}>&larr; Home</a>
          <h1 style={styles.h1}>Teacher Dashboard</h1>
        </header>
        <div style={styles.error}>{error}</div>
        <a href="/login" style={styles.loginBtn}>Login</a>
      </div>
    );
  }

  // Unique students from assignments
  const studentMap = new Map<number, string>();
  for (const a of assignments) {
    if (a.student_username) {
      studentMap.set(a.student_id, a.student_username);
    }
  }

  return (
    <div style={styles.app}>
      <header style={styles.header}>
        <a href="/" style={styles.backLink}>&larr; Home</a>
        <h1 style={styles.h1}>Teacher Dashboard</h1>
      </header>

      {/* Student list */}
      {studentMap.size > 0 && (
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>Your Students</h2>
          <div style={styles.studentList}>
            {Array.from(studentMap.entries()).map(([id, name]) => (
              <div key={id} style={styles.studentCard}>
                <span style={styles.studentName}>{name}</span>
                <button
                  style={styles.viewBtn}
                  onClick={() => handleViewStudentProgress(id)}
                >
                  {selectedStudentId === id ? "Hide" : "View Progress"}
                </button>
              </div>
            ))}
          </div>

          {/* Student progress detail */}
          {studentProgress && selectedStudentId && (
            <div style={styles.progressDetail}>
              <h3 style={styles.progressTitle}>
                {studentProgress.username} — {studentProgress.total_sessions} sessions
              </h3>
              <div style={styles.skillGrid}>
                {studentProgress.skills.map((s) => (
                  <div key={s.skill_area} style={styles.skillItem}>
                    <span style={{ textTransform: "capitalize" as const }}>{s.skill_area}</span>
                    <span style={{ fontWeight: 700 }}>{Math.round(s.score)}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Create assignment form */}
      <div style={styles.section}>
        <h2 style={styles.sectionTitle}>Assign Exercise</h2>
        {createError && <div style={styles.error}>{createError}</div>}
        <form onSubmit={handleCreateAssignment} style={styles.form}>
          <label style={styles.label}>
            Student username
            <input
              type="text"
              value={studentUsername}
              onChange={(e) => setStudentUsername(e.target.value)}
              style={styles.input}
              required
            />
          </label>
          <label style={styles.label}>
            Title
            <input
              type="text"
              value={assignTitle}
              onChange={(e) => setAssignTitle(e.target.value)}
              style={styles.input}
              required
            />
          </label>
          <label style={styles.label}>
            Score (optional)
            <select
              value={assignScoreId}
              onChange={(e) => setAssignScoreId(e.target.value ? Number(e.target.value) : "")}
              style={styles.input}
            >
              <option value="">No score</option>
              {scores.map((s) => (
                <option key={s.id} value={s.id}>{s.title}</option>
              ))}
            </select>
          </label>
          <label style={styles.label}>
            Notes (optional)
            <input
              type="text"
              value={assignNotes}
              onChange={(e) => setAssignNotes(e.target.value)}
              style={styles.input}
            />
          </label>
          <label style={styles.label}>
            Due date (optional)
            <input
              type="date"
              value={assignDueDate}
              onChange={(e) => setAssignDueDate(e.target.value)}
              style={styles.input}
            />
          </label>
          <button
            type="submit"
            style={{
              ...styles.submitBtn,
              ...(creating ? styles.disabled : {}),
            }}
            disabled={creating}
          >
            {creating ? "Creating..." : "Create Assignment"}
          </button>
        </form>
      </div>

      {/* Assignment list */}
      <div style={styles.section}>
        <h2 style={styles.sectionTitle}>Assignments</h2>
        {assignments.length > 0 ? (
          <div style={styles.assignmentList}>
            {assignments.map((a) => (
              <div key={a.id} style={styles.assignmentCard}>
                <div style={styles.assignmentHeader}>
                  <span style={styles.assignmentTitle}>{a.title}</span>
                  <span style={{
                    ...styles.statusBadge,
                    backgroundColor: a.status === "completed" ? "#dcfce7" : "#fef3c7",
                    color: a.status === "completed" ? "#16a34a" : "#d97706",
                  }}>
                    {a.status}
                  </span>
                </div>
                <div style={styles.assignmentMeta}>
                  Student: {a.student_username || a.student_id}
                  {a.due_date ? ` | Due: ${a.due_date}` : ""}
                </div>
                {a.notes && <div style={styles.assignmentNotes}>{a.notes}</div>}
              </div>
            ))}
          </div>
        ) : (
          <p style={styles.emptyText}>No assignments yet.</p>
        )}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  app: { maxWidth: 960, margin: "0 auto", padding: "24px 16px", fontFamily: "Inter, system-ui, sans-serif" },
  header: { display: "flex", alignItems: "center", gap: 16, marginBottom: 24 },
  h1: { fontSize: 22, fontWeight: 700, color: "#1e293b", margin: 0 },
  backLink: { fontSize: 14, color: "#3b82f6", textDecoration: "none", fontWeight: 500 },
  loading: { textAlign: "center" as const, color: "#64748b", padding: "40px 0" },
  error: { padding: "8px 12px", backgroundColor: "#fef2f2", color: "#dc2626", borderRadius: 6, marginBottom: 16, fontSize: 14 },
  loginBtn: { display: "inline-block", padding: "8px 16px", backgroundColor: "#3b82f6", color: "#fff", borderRadius: 6, fontSize: 14, fontWeight: 500, textDecoration: "none" },

  section: { marginBottom: 24 },
  sectionTitle: { fontSize: 16, fontWeight: 600, color: "#1e293b", margin: "0 0 12px 0" },

  // Students
  studentList: { display: "flex", flexDirection: "column" as const, gap: 8, marginBottom: 12 },
  studentCard: { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 12px", backgroundColor: "#fff", borderRadius: 6, border: "1px solid #e2e8f0" },
  studentName: { fontSize: 14, fontWeight: 600, color: "#1e293b" },
  viewBtn: { padding: "4px 12px", backgroundColor: "#3b82f6", color: "#fff", border: "none", borderRadius: 4, fontSize: 12, fontWeight: 500, cursor: "pointer" },
  progressDetail: { padding: 12, backgroundColor: "#f8fafc", borderRadius: 8, border: "1px solid #e2e8f0", marginBottom: 12 },
  progressTitle: { fontSize: 14, fontWeight: 600, color: "#1e293b", margin: "0 0 8px 0" },
  skillGrid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 },
  skillItem: { display: "flex", justifyContent: "space-between", fontSize: 13, color: "#475569", padding: "4px 8px", backgroundColor: "#fff", borderRadius: 4 },

  // Form
  form: { display: "flex", flexDirection: "column" as const, gap: 12 },
  label: { display: "flex", flexDirection: "column" as const, gap: 4, fontSize: 13, fontWeight: 500, color: "#475569" },
  input: { padding: "8px 12px", border: "1px solid #cbd5e1", borderRadius: 6, fontSize: 14, outline: "none" },
  submitBtn: { padding: "10px 16px", backgroundColor: "#8b5cf6", color: "#fff", border: "none", borderRadius: 6, fontSize: 15, fontWeight: 600, cursor: "pointer", marginTop: 4 },
  disabled: { opacity: 0.5, pointerEvents: "none" as const },

  // Assignments
  assignmentList: { display: "flex", flexDirection: "column" as const, gap: 8 },
  assignmentCard: { padding: 12, backgroundColor: "#fff", borderRadius: 8, border: "1px solid #e2e8f0" },
  assignmentHeader: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 },
  assignmentTitle: { fontSize: 14, fontWeight: 600, color: "#1e293b" },
  statusBadge: { padding: "2px 8px", borderRadius: 4, fontSize: 11, fontWeight: 600, textTransform: "uppercase" as const },
  assignmentMeta: { fontSize: 12, color: "#64748b", marginBottom: 4 },
  assignmentNotes: { fontSize: 13, color: "#475569", fontStyle: "italic" },
  emptyText: { fontSize: 14, color: "#94a3b8", textAlign: "center" as const, padding: "20px 0" },
};
