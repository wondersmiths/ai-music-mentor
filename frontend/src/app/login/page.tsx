"use client";

import React, { useState } from "react";
import { register, login } from "@/lib/api";

type Mode = "login" | "register";

export default function LoginPage() {
  const [mode, setMode] = useState<Mode>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState("student");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (mode === "register") {
        const res = await register({
          username,
          password,
          display_name: displayName || undefined,
          role,
        });
        localStorage.setItem("auth_token", res.access_token);
        localStorage.setItem("auth_username", res.username);
      } else {
        const res = await login({ username, password });
        localStorage.setItem("auth_token", res.access_token);
        localStorage.setItem("auth_username", res.username);
      }
      window.location.href = "/";
    } catch (err: unknown) {
      const detail = err && typeof err === "object" && "detail" in err
        ? (err as { detail: string }).detail
        : "Something went wrong";
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <h1 style={styles.title}>AI Music Mentor</h1>

        {/* Mode toggle */}
        <div style={styles.toggle}>
          <button
            style={{
              ...styles.toggleBtn,
              ...(mode === "login" ? styles.toggleActive : {}),
            }}
            onClick={() => setMode("login")}
          >
            Login
          </button>
          <button
            style={{
              ...styles.toggleBtn,
              ...(mode === "register" ? styles.toggleActive : {}),
            }}
            onClick={() => setMode("register")}
          >
            Register
          </button>
        </div>

        {error && <div style={styles.error}>{error}</div>}

        <form onSubmit={handleSubmit} style={styles.form}>
          <label style={styles.label}>
            Username
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              style={styles.input}
              required
              minLength={2}
              autoComplete="username"
            />
          </label>

          <label style={styles.label}>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={styles.input}
              required
              minLength={4}
              autoComplete={mode === "register" ? "new-password" : "current-password"}
            />
          </label>

          {mode === "register" && (
            <>
              <label style={styles.label}>
                Display Name (optional)
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  style={styles.input}
                />
              </label>

              <label style={styles.label}>
                Role
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  style={styles.input}
                >
                  <option value="student">Student</option>
                  <option value="teacher">Teacher</option>
                </select>
              </label>
            </>
          )}

          <button
            type="submit"
            style={{
              ...styles.submit,
              ...(loading ? styles.disabled : {}),
            }}
            disabled={loading}
          >
            {loading
              ? "Please wait..."
              : mode === "login"
                ? "Login"
                : "Create Account"}
          </button>
        </form>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: 16,
    backgroundColor: "#f8fafc",
  },
  card: {
    width: "100%",
    maxWidth: 400,
    padding: 32,
    backgroundColor: "#fff",
    borderRadius: 12,
    border: "1px solid #e2e8f0",
  },
  title: {
    fontSize: 22,
    fontWeight: 700,
    color: "#1e293b",
    textAlign: "center" as const,
    margin: "0 0 24px 0",
  },
  toggle: {
    display: "flex",
    borderRadius: 6,
    overflow: "hidden",
    border: "1px solid #cbd5e1",
    marginBottom: 20,
  },
  toggleBtn: {
    flex: 1,
    padding: "8px 0",
    border: "none",
    backgroundColor: "#fff",
    color: "#64748b",
    fontSize: 14,
    fontWeight: 500,
    cursor: "pointer",
  },
  toggleActive: {
    backgroundColor: "#3b82f6",
    color: "#fff",
  },
  error: {
    padding: "8px 12px",
    backgroundColor: "#fef2f2",
    color: "#dc2626",
    borderRadius: 6,
    marginBottom: 16,
    fontSize: 14,
  },
  form: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 16,
  },
  label: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 4,
    fontSize: 13,
    fontWeight: 500,
    color: "#475569",
  },
  input: {
    padding: "8px 12px",
    border: "1px solid #cbd5e1",
    borderRadius: 6,
    fontSize: 14,
    outline: "none",
  },
  submit: {
    padding: "10px 16px",
    backgroundColor: "#3b82f6",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    fontSize: 15,
    fontWeight: 600,
    cursor: "pointer",
    marginTop: 4,
  },
  disabled: {
    opacity: 0.5,
    pointerEvents: "none" as const,
  },
};
