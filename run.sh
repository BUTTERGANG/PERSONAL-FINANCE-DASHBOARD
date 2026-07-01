#!/bin/bash
# ─────────────────────────────────────────────────────────────
#  Startup script — runs both services.
#  FastAPI (port 8000) starts in background.
#  Streamlit (port 8501) runs in foreground and keeps Replit alive.
# ─────────────────────────────────────────────────────────────
set -e

echo "📦 Installing dependencies..."
pip install -r requirements.txt -q

echo "🔐 Checking for encryption key..."
if [ -z "$ENCRYPTION_KEY" ]; then
  echo "⚠️  WARNING: ENCRYPTION_KEY not set. Run: python scripts/generate_key.py"
  echo "   Then add it to Replit Secrets or your .env file."
fi

echo "🚀 Starting FastAPI backend on port 8000..."
uvicorn backend.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --log-level warning &
BACKEND_PID=$!

# Kill backend when this script exits
trap "echo '🛑 Shutting down backend...'; kill $BACKEND_PID 2>/dev/null" EXIT

# Give the backend a moment to initialize
sleep 2

echo "🖥️  Starting Streamlit frontend on port 8501..."
streamlit run frontend/app.py \
  --server.port 8501 \
  --server.address 0.0.0.0 \
  --server.headless true \
  --browser.gatherUsageStats false \
  --theme.base dark
