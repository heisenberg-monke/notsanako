#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

echo "=== Starting Adaptive Reading Coach Backend ==="

if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment in $DIR/venv..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "Installing / verifying backend dependencies..."
pip install -r requirements.txt

echo "Starting FastAPI server on http://localhost:8000..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
