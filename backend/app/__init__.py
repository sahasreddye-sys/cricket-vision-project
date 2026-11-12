import sys
from pathlib import Path

# Make the shared `pitchvision` analytics package importable when the backend is
# started from the backend/ folder without installing the package.
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
