"""Vercel entrypoint: exports a module-level ASGI `app`.

Vercel looks for a FastAPI instance at import time, so the app is built here
rather than through the CLI. Two things differ from local development:

* the dataset is read from the committed `data/rrb.sqlite` — the demo is a
  fixed, deterministic snapshot, so shipping it beats generating it per boot;
* SQLite is opened read-only, because a serverless filesystem is read-only and
  a normal open can fail when SQLite tries to place a journal next to the file.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# the package lives under src/; add it explicitly so the entrypoint imports
# whether or not the builder installed the project itself
sys.path.insert(0, str(ROOT / "src"))

from rrb.web import create_app  # noqa: E402  (must follow the path setup)

DB = ROOT / "data" / "rrb.sqlite"

if not DB.exists():  # fail loudly at boot rather than 500 on every request
    raise RuntimeError(
        f"dataset missing at {DB}. Run `rrb make-data` and commit it, or set "
        "the deployment to build it before packaging.")

app = create_app(str(DB), read_only=True)
