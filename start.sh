#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "🛰️  Sentinel Timelapse Generator — Setup & Launch"
echo "================================================="

# 1. Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo ""
    echo "📦 Creating Python virtual environment..."
    python3 -m venv .venv
fi

# 2. Activate it
source .venv/bin/activate

# 3. Install dependencies
echo ""
echo "📥 Installing dependencies (this may take a minute)..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# 4. Create output directory
mkdir -p backend/output

# 5. Launch the server
echo ""
echo "🚀 Starting FastAPI server on http://localhost:8000"
echo "   Press Ctrl+C to stop."
echo ""
cd backend
python main.py
