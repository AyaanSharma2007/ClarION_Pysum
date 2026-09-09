"""
Root conftest.py for ClarION workspace.
Ensures root, apps/backend, and layer2 are in sys.path so test discovery works seamlessly across modules.
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "apps" / "backend"
LAYER2_DIR = ROOT_DIR / "layer2"

for p in [ROOT_DIR, BACKEND_DIR, LAYER2_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
