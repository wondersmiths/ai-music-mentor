FROM python:3.11-slim

WORKDIR /app

# System deps for opencv-headless and pdf2image
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 poppler-utils && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ai/ ./ai/
COPY backend/ ./backend/
COPY tests/ ./tests/

# Railway injects PORT at runtime
ENV PORT=8001
ENV ENVIRONMENT=production

EXPOSE ${PORT}

CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --timeout-keep-alive 30
