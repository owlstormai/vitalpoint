from fastapi.testclient import TestClient

from rrb.cli import main
from rrb.web import create_app


def _client(tmp_path):
    db = tmp_path / "rrb.sqlite"
    main(["make-data", "--seed", "42", "--accounts", "15",
          "--db", str(db), "--labels", str(tmp_path / "l.yaml")])
    return TestClient(create_app(str(db)))


def test_dashboard_lists_accounts(tmp_path):
    client = _client(tmp_path)
    r = client.get("/")
    assert r.status_code == 200
    assert "acct_0000" in r.text and "Risk" in r.text


def test_dashboard_filters_by_specialty(tmp_path):
    client = _client(tmp_path)
    all_rows = client.get("/").text.count("acct_")
    dental = client.get("/?specialty=dental").text
    assert dental.count("acct_") <= all_rows


def test_brief_page_renders(tmp_path):
    client = _client(tmp_path)
    r = client.get("/brief/acct_0002")
    assert r.status_code == 200
    assert "Renewal Risk Brief" in r.text


def test_unknown_account_404(tmp_path):
    client = _client(tmp_path)
    assert client.get("/brief/acct_9999").status_code == 404
