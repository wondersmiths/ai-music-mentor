FROM python:3.11-slim

WORKDIR /app

# System deps for opencv-headless and pdf2image
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 poppler-utils tesseract-ocr && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps (cached layer — only re-runs when requirements change)
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ai/ ./ai/
COPY backend/ ./backend/

# Railway injects PORT at runtime
ENV PORT=8001
ENV ENVIRONMENT=production
ENV PYTHONUNBUFFERED=1

EXPOSE ${PORT}

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health')" || exit 1

CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --timeout-keep-alive 30
