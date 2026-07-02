#!/bin/bash
# ─────────────────────────────────────────────────────────────
#  Startup script — runs both services.
#  FastAPI (port 8000) starts in background.
#  Vite dev server (port 5173) runs in foreground and keeps Replit alive.
# ─────────────────────────────────────────────────────────────
set -e

echo "📦 Installing Python dependencies..."
pip install -r requirements.txt -q

echo "📦 Installing Node dependencies..."
cd react-frontend
npm install --prefer-offline --no-audit --progress=false 2>/dev/null
cd ..

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

echo "🖥️  Starting Vite dev server (React) on port 5173..."
cd react-frontend
npm run dev -- --host 0.0.0.0 --port 5173