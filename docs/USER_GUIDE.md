# AI Music Mentor — User Guide

## Table of Contents

1. [Getting Started](#getting-started)
2. [Practice Session](#practice-session)
3. [Score Library](#score-library)
4. [Dashboard](#dashboard)
5. [Teacher / Student Workflow](#teacher--student-workflow)
6. [API Reference](#api-reference)
7. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Prerequisites

- A modern browser (Chrome, Edge, or Firefox recommended)
- A working microphone — USB or built-in
- Node.js 18+ and Python 3.10+ (for local development)

### Running the App

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload          # http://localhost:8000

# Frontend
cd frontend
npm install
npm run dev                        # http://localhost:3000
```

### Creating an Account

1. Navigate to `/login`.
2. Enter a username and password, then click **Register**.
3. After registration you are automatically logged in and an auth token is stored in your browser.

To log out, click the **Logout** button in the top-right corner of any page.

---

## Practice Session

Open `/practice` to start a practice session.

### 1. Select an Exercise

| Type | What it does |
|------|-------------|
| **Long Tone** | Hold a single note — the app measures pitch accuracy and stability over time. |
| **Scale** | Play a sequence of notes (e.g. D Major, Pentatonic). Choose a preset or enter custom jianpu. |
| **Melody** | Play a short melody. Choose a built-in piece or paste your own jianpu string. |

You can also load a score from the **Score Library** (built-in + your saved scores).

### 2. Configure

- **Instrument** — pick your instrument (Erhu, Violin, Flute, etc.). This tunes the pitch detection frequency range.
- **BPM** — set the metronome tempo (40–240).
- **Metronome** — toggle on/off; gives audible clicks during recording.

### 3. Record

Click **Start Recording**. A count-in plays, then the app begins:

- Real-time **pitch detection** — your current note is shown live.
- **Jianpu notation strip** — highlights the expected note as you play.
- A **stability analyser** tracks how steady your tone is (with vibrato tolerance).
- A **cursor engine** follows your position in the score.

### 4. Evaluation

After you click **Stop**, the recording is sent to the backend for evaluation. The backend returns:

| Metric | Description |
|--------|-------------|
| **Accuracy** | How many notes matched the expected pitches (%). |
| **Rhythm** | How closely your timing matched the beat grid (%). |
| **Stability** | Tone steadiness (long tones only). |
| **Intonation** | Average cents deviation from target pitches. |

You also receive:

- A **summary** paragraph describing your performance.
- **Issue list** — specific measures/notes that need work, with severity (error / warning / info).
- **Practice drills** — targeted exercises with suggested tempo, repetitions, and tips.
- **Warmup suggestion** for next time.

---

## Score Library

The score library is accessible from the Practice page's exercise picker.

### Built-in Scores

The app ships with a set of built-in scores (jianpu notation) covering common exercises and well-known pieces. These cannot be deleted.

### Uploading Scores

From the old practice page or via API you can upload an image (PNG/JPG) or PDF of sheet music. The backend uses OCR to parse it into structured jianpu/western notation with pitches and durations.

- Single page: `POST /api/score/parse`
- Multi-page: `POST /api/score/parse-multi` (up to 20 pages)

### Saving Scores

After parsing, click **Save to Library** to store the score under your account. Saved scores appear alongside built-in scores when choosing an exercise.

### Deleting Scores

Only your own saved scores can be deleted. Built-in scores are permanent.

---

## Dashboard

Open `/dashboard` (you must be logged in).

### Skills Overview

Four skill areas are tracked:

| Skill | What it measures |
|-------|-----------------|
| **Pitch** | Overall intonation accuracy across sessions. |
| **Stability** | Tone steadiness and vibrato control. |
| **Slide** | Slide/glissando technique (erhu-specific). |
| **Rhythm** | Timing precision relative to the beat grid. |

Each skill shows a 0–100 score and tracks your trend over time.

### Session History

A table of your recent sessions (up to 20) showing:

- Date and duration
- Exercise type and title
- Accuracy / rhythm scores
- Link to detailed results

### Streaks

- **Current streak** — consecutive days with at least one session.
- **Longest streak** — your all-time record.
- **Last practice date**.

### Weekly Goals

Set a target number of sessions and total minutes per week. The dashboard shows your progress toward each goal for the current week.

---

## Teacher / Student Workflow

Open `/teacher` (you must be logged in).

### Roles

When you register, you can choose to be a **student** or **teacher**. Teachers can:

1. **Create assignments** — pick a score from the library, assign it to a student by username, add notes and a due date.
2. **View student progress** — see a student's skill scores, session history, and assignment completion.

Students see their received assignments on the Teacher page and can start practising directly from an assignment.

### Creating an Assignment

1. Go to `/teacher`.
2. Fill in the student's username, select a score, add optional notes and due date.
3. Click **Create Assignment**.

### Viewing Student Progress

Click on a student's name in your assignments list to view their skill breakdown and recent sessions.

---

## API Reference

All endpoints are served from the backend (default `http://localhost:8000`).

### Authentication

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/register` | No | Register a new user; returns JWT token |
| POST | `/api/auth/login` | No | Log in; returns JWT token |
| GET | `/api/auth/me` | Yes | Get current user info |

### Score Parsing

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/score/parse` | No | Upload image/PDF, get structured score JSON |
| POST | `/api/score/parse-multi` | No | Upload multiple pages (up to 20) |

### Practice (Real-time)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/practice/start` | No | Begin practice session with score + tempo |
| POST | `/api/practice/frame` | No | Send ~2 s WAV audio chunk for alignment |
| POST | `/api/practice/stop` | No | Stop session, get analysis + practice plan |

### Evaluation

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/analyze` | No | Analyse WAV chunk — pitches, onsets, tempo |
| POST | `/api/evaluate` | No | Full evaluation of a practice recording |

### Training Sessions

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/session/start` | No | Start training session |
| POST | `/api/session/result` | No | Save exercise result |
| POST | `/api/session/end` | No | End session, compute scores, update streaks |
| GET | `/api/progress/{username}` | No | Skill progress (pitch, stability, slide, rhythm) |
| GET | `/api/progress/{username}/recommend` | No | Next exercise recommendation |
| GET | `/api/sessions/{username}/history` | No | Recent session history (default limit 20) |

### Score Library

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/scores` | Optional | List built-in + user scores |
| POST | `/api/scores` | Yes | Save a score |
| DELETE | `/api/scores/{score_id}` | Yes | Delete a user score |

### Teacher

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/assignments` | Yes | Create assignment |
| GET | `/api/assignments` | Yes | List assignments (teacher: given, student: received) |
| GET | `/api/students/{id}/progress` | Yes | View student progress |

### Streaks & Goals

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/streaks/{username}` | No | Current/longest streak, last practice date |
| POST | `/api/goals` | Yes | Set weekly goal (sessions + minutes) |
| GET | `/api/goals/{username}` | No | Current week goal + progress |

### System

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness probe |
| GET | `/health/ready` | Readiness probe (checks DB) |
| GET | `/version` | App version |
| GET | `/instruments` | Supported instruments list |

---

## Troubleshooting

### Microphone Access

- The browser will ask for microphone permission the first time you record. **Allow** it.
- If you accidentally denied permission, open your browser's site settings and re-enable the microphone for `localhost:3000`.
- Chrome: click the lock icon in the address bar → Site settings → Microphone → Allow.
- Make sure no other app (Zoom, Discord) is exclusively holding the mic.

### No Sound Detected

- Check that your microphone is plugged in and selected as the system default.
- Increase the input volume in your OS sound settings.
- Try a different browser — Chrome generally has the best Web Audio API support.

### Upload Fails

- Maximum single-file size is configured on the backend (`MAX_UPLOAD_BYTES`). Default is 10 MB.
- Multi-page uploads support up to 20 files at 5× the single-file limit.
- Accepted formats: PNG, JPG, JPEG, PDF.

### Evaluation Takes Too Long

- The backend calls an AI model for detailed feedback. If the model endpoint is slow or down, evaluation may time out.
- Check backend logs for errors: `uvicorn main:app --reload --log-level debug`.

### CORS Errors

- The backend allows configurable origins via the `CORS_ORIGINS` environment variable.
- For local development, ensure the frontend origin (`http://localhost:3000`) is included.

### Rate Limiting

- In production, the API is rate-limited to 60 requests per 60-second window.
- If you hit the limit, wait a minute and retry.

### Database Issues

- The app uses SQLite by default (`ai_music_mentor.db` in the project root).
- To reset, delete the database file and restart the backend — tables are auto-created on startup.
