# AI Music Mentor — User Guide

## Getting Started

### Prerequisites

- Node.js 20+
- Python 3.11+
- A modern browser with Web Audio API support
- A microphone

### Starting the Backend

```bash
cd backend
pip install -r requirements.txt
python3 -m backend.main
```

The backend runs on `http://127.0.0.1:8001` by default.

### Starting the Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs on `http://localhost:3000` by default.

### Environment Variables

**Backend (`.env`):**

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Backend bind address |
| `PORT` | `8001` | Backend port |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed frontend origins |
| `ANTHROPIC_API_KEY` | — | Optional, enables Claude Vision score OCR |
| `ENVIRONMENT` | `development` | Set to `production` for global rate limiting |

**Frontend (`frontend/.env.local`):**

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://127.0.0.1:8001` | Backend API URL |

---

## Account & Login

### Registering

1. Navigate to `/login` and click the **Register** tab.
2. Enter a username (min 2 characters) and password (min 4 characters).
3. Optionally set a display name and role (**Student** or **Teacher**).
4. Click **Create Account** — you'll be logged in and redirected to the home page.

### Logging In

1. Navigate to `/login`, enter your credentials, and click **Login**.
2. Your session token is stored in the browser — you stay logged in until you log out.

### Security

- Accounts lock for 15 minutes after 5 failed password attempts.
- Rate limiting applies: 10 login attempts and 5 registration attempts per minute per IP.
- Lockout and rate-limit errors appear in an amber warning box.

---

## Practice

The Practice page (`/practice`) is the core of the app. It supports three exercise types.

### Exercise Types

#### Long Tone

Hold a single sustained note. The app measures your pitch accuracy and stability.

- Select a **target note** from D4 to D6 (frequency shown in Hz).
- A stability meter shows drift direction (Sharp, Flat, or Stable) and mean deviation.

#### Scale

Play a sequence of notes in jianpu notation along with a metronome.

- **Presets:** D Major, Pentatonic, Descending, Up & Down.
- **Custom:** Enter your own jianpu notation.

#### Melody

Play a melody — similar to scales but with more complex notation.

- **Presets:** Twinkle Twinkle, Mo Li Hua (Jasmine Flower).
- **Custom:** Enter jianpu notation or load from the Score Library.

### Configuring a Session

- **Instrument:** Select from the dropdown (Erhu, Violin, Flute, Cello, Trumpet, Clarinet, Zhongruan).
- **BPM:** Adjust tempo from 40 to 240.
- **Browse Library:** Load a saved score directly into the melody exercise.

### During Recording

- **Pitch display:** Shows current note, frequency (Hz), and cents deviation (color-coded).
  - Green: within ±10 cents (in tune)
  - Yellow: within ±25 cents (acceptable)
  - Red: beyond ±25 cents (out of tune)
- **Deviation bar:** Visual -50¢ to +50¢ range with a moving marker.
- **Metronome:** 4 beat-pulse dots with an accent on beat 1.
- **Jianpu strip:** Highlights the active note in blue, grays out past notes.
- **Cursor info:** Shows current bar and beat position.
- **Timer:** Elapsed time out of 60 seconds (max recording length).

Your browser will prompt for microphone access on first use — this must be granted.

### Results

After stopping, the backend evaluates your performance and shows:

- **Overall score** (0–100, color-coded)
- **Sub-scores:** Pitch, Stability, Slide (erhu-specific), Rhythm
- **Textual feedback** with specific suggestions
- **Recommended next exercise** type
- Buttons to **Try Again** or start a **New Exercise**

---

## Jianpu Notation Format

Jianpu (numbered musical notation) is used throughout the app:

| Symbol | Meaning |
|--------|---------|
| `1` – `7` | Note degrees (Do Re Mi Fa Sol La Ti) |
| `0` | Rest |
| `-` | Sustain / hold previous note |
| `\|` | Measure separator |
| Space | Note separator |
| `1̇` (dot above) | Octave up |
| `1̲` (dot below) | Octave down |

**Example:** `1 1 5 5 | 6 6 5 - | 4 4 3 3 | 2 2 1 -` = Twinkle Twinkle Little Star

---

## Score Library

The Score Library page (`/scores`) displays all available scores in two sections:

- **Built-in Scores:** Pre-loaded scores (D Major Scale, Pentatonic Scale, Twinkle Twinkle, Mo Li Hua, Long Tone D5). These cannot be deleted.
- **My Scores:** Your personal saved scores. These can be deleted.

Each score card shows the title, jianpu notation, key signature, and instrument.

### Using Scores in Practice

1. Go to the **Practice** page.
2. Select the **Melody** exercise type.
3. Click **Browse Library** to open the score browser.
4. Select a score — its notation loads into the exercise automatically.

### Adding Scores via API

```bash
curl -X POST http://127.0.0.1:8001/api/scores \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My Custom Melody",
    "jianpu_notation": "1 2 3 5 | 6 6 5 - | 5 3 5 6 | 5 - - -",
    "key_signature": "1=D",
    "instrument": "erhu"
  }'
```

Only `title` and `jianpu_notation` are required.

---

## Dashboard

The Dashboard (`/dashboard`) requires login and shows your practice overview.

### Stats

Four summary cards at the top:

- **Total Sessions** — all-time practice session count
- **Total Exercises** — number of individual exercises completed
- **Current Streak** — consecutive days practiced
- **Best Streak** — longest streak achieved

### Weekly Goal

Set targets for sessions per week and minutes per week. Progress bars show how close you are. Goals reset each Monday.

- Sessions: 1–30 per week
- Minutes: 10–600 per week

### Skills

A 2x2 grid showing your scores in four areas:

- **Pitch** — note accuracy
- **Stability** — tone steadiness
- **Slide** — slide technique quality (erhu-specific)
- **Rhythm** — timing precision

Color coding: green (80%+), yellow (60%+), red (below 60%).

### Recommendation

A personalized suggestion for your next exercise based on your weakest skill areas.

### Session History

A table of your 20 most recent sessions showing date, exercise count, score, and duration.

---

## Teacher Features

Teachers access the Teacher Dashboard at `/teacher` (requires a teacher-role account).

### Viewing Student Progress

See a list of your students with their skill scores (Pitch, Stability, Slide, Rhythm) and total session count.

### Creating Assignments

1. Enter the student's username.
2. Set an exercise title (required).
3. Optionally select a score from the library, add notes, and set a due date.
4. Click **Create Assignment**.

### Viewing Assignments

All your created assignments appear as cards showing title, student name, status (pending/completed), due date, and notes.

---

## Health & Status Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Basic liveness check |
| `GET /health/ready` | Database connectivity check |
| `GET /version` | App version |
| `GET /instruments` | List of supported instruments |

---

## Database

The app uses SQLite by default (`ai_music_mentor.db` in the project root). Tables and migrations run automatically on startup. To reset all data, delete the database file and restart the backend.
