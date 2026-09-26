#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

echo "=== Starting Adaptive Reading Coach Frontend ==="

if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies via npm..."
    npm install
fi

echo "Starting Next.js development server on http://localhost:3000..."
exec npm run dev
