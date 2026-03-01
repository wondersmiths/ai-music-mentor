# AI Music Mentor

AI Music Mentor is a practice tool that listens to you play an instrument or sing, compares your performance against a reference, and gives you actionable feedback in real time. It uses audio analysis to detect pitch, timing, and dynamics, then surfaces specific things to work on — not vague encouragement.

## MVP Scope

The first version supports **one instrument (piano)** and **single voice (monophonic input)**. No chords, no multi-track, no ensemble. The goal is to nail the core loop — listen, analyze, respond — before expanding to other instruments or polyphonic input.

## Local Development

**Prerequisites:** Node.js 20+, Python 3.11+

```bash
# Clone and enter the repo
git clone <repo-url>
cd ai-music-mentor

# Frontend
cd frontend
npm install
npm run dev

# Backend
cd ../backend
npm install
npm run dev

# AI service
cd ../ai
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Each service runs independently. The frontend expects the backend at `localhost:3001` and the backend expects the AI service at `localhost:8000`. Configure these in `.env` files if your ports differ.
