#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Virtualenv not found. Please create one with: uv venv"
    exit 1
fi

# Enable Demo Mode for interactive prototype
export ENABLE_DEMO_MODE=True

echo "--- MedResearch DMS: Applying Migrations ---"
python manage.py migrate

echo "--- MedResearch DMS: Seeding High-Fidelity Demo Data ---"
python manage.py seed_demo

echo "--- MedResearch DMS: Starting Server on http://localhost:8000 ---"
python manage.py runserver 0.0.0.0:8000
