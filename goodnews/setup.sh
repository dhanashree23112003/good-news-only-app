#!/bin/bash
# setup.sh — One-time setup for Good News Only
# Run this once: bash setup.sh

set -e   # exit on any error

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   Good News Only — Setup Script      ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── Check Python version ──────────────────────────────────────────────────────
echo "→ Checking Python..."
python3 --version || { echo "❌ Python 3.9+ required. Install it from python.org"; exit 1; }

# ── Create virtualenv ─────────────────────────────────────────────────────────
echo "→ Creating virtual environment..."
cd backend
python3 -m venv venv
source venv/bin/activate

# ── Install dependencies ──────────────────────────────────────────────────────
echo ""
echo "→ Installing dependencies (this takes a few minutes on first run)..."
echo "  Note: PyTorch is ~700MB. Subsequent runs use the cached install."
echo ""
pip install --upgrade pip --quiet
pip install -r requirements.txt

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start the app:"
echo "  1. cd backend && source venv/bin/activate"
echo "  2. uvicorn main:app --reload"
echo "  3. Open frontend/index.html in your browser"
echo ""
echo "The first load will download the sentiment model (~500MB)."
echo "After that, it's fast and cached locally."
