from pathlib import Path

from fastapi.testclient import TestClient

from rrb.cli import main as cli_main
from rrb.templates import FAVICON_SVG
from rrb.web import create_app

ROOT = Path(__file__).resolve().parent.parent


def test_static_file_matches_the_constant():
    """Vercel serves public/favicon.svg from its CDN while the app serves the
    constant, so a drift between them would show two different icons."""
    served = (ROOT / "public" / "favicon.svg").read_text().strip()
    assert served == FAVICON_SVG.strip()


def test_app_serves_the_icon(tmp_path):
    db = tmp_path / "rrb.sqlite"
    cli_main(["make-data", "--seed", "42", "--accounts", "5",
              "--db", str(db), "--labels", str(tmp_path / "l.yaml")])
    client = TestClient(create_app(str(db)))

    r = client.get("/favicon.svg")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert "<svg" in r.text

    # every page must actually point at it, or the tab falls back to /favicon.ico
    for path in ("/", "/brief/acct_0000"):
        assert 'rel="icon"' in client.get(path).text
        assert "/favicon.svg" in client.get(path).text
