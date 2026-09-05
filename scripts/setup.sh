#!/usr/bin/env bash
set -e

echo "======================================================="
echo " ClarION — Automated Environment & Dependency Setup "
echo "======================================================="

# 1. Setup Virtual Environment if missing
if [ ! -d ".venv" ]; then
    echo "📦 Creating Python virtual environment in .venv..."
    python3 -m venv .venv
else
    echo "✅ Python virtual environment already exists in .venv"
fi

# 2. Install/Update Python dependencies
echo "📥 Checking Python requirements..."
.venv/bin/pip install -r apps/backend/requirements.txt --quiet
.venv/bin/pip install -r LAYER2/layer2/requirements.txt --quiet

# 3. Install Node.js dependencies
echo "📦 Checking npm dependencies..."
npm install --quiet
npm install --prefix apps/frontend --quiet

<<<<<<< HEAD
# 4. Initialize Database Schema
echo "🗄️ Initializing Database schema..."
if [ -f "LAYER2/layer2/.env" ]; then
    (cd LAYER2/layer2 && ../../.venv/bin/python -m alembic upgrade head)
    .venv/bin/python scripts/init_db.py
else
    echo "⚠️ LAYER2/layer2/.env not found, skipping database migrations."
fi

=======
>>>>>>> main
echo "======================================================="
echo " 🎉 Setup Complete! You can now run:"
echo "   - npm run dev           (starts Layer 2, Backend, & Frontend)"
echo "   - npm run dev:backend   (starts Layer 1 / Layer 4 Backend)"
echo "   - npm run dev:layer2    (starts Layer 2 Central Repo)"
echo "   - npm run dev:frontend  (starts Vite React Frontend)"
echo "======================================================="
