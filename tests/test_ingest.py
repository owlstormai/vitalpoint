import csv
from pathlib import Path

import pytest
import yaml

from rrb.db import connect, init_db
from rrb.generator import generate
from rrb.ingest import ingest, load_mapping, write_export

ROOT = Path(__file__).resolve().parent.parent
MAPPING = ROOT / "data" / "mappings" / "example_crm.yaml"


@pytest.fixture
def source(tmp_path):
    """A generated dataset plus its export in a customer's column names."""
    conn = init_db(tmp_path / "source.sqlite")
    generate(conn, seed=42, n_accounts=25)
    mapping = load_mapping(MAPPING)
    write_export(conn, tmp_path / "export", mapping)
    return conn, tmp_path / "export", mapping


def _rows(conn, table):
    return [tuple(r) for r in conn.execute(f"SELECT * FROM {table} ORDER BY 1")]


def test_round_trip_preserves_every_mapped_field(source, tmp_path):
    """Foreign-shaped CSVs in, canonical database out, nothing lost."""
    src, export_dir, mapping = source
    dest = init_db(tmp_path / "dest.sqlite")
    report = ingest(dest, export_dir, mapping)
    assert report.ok, report.errors

    for table in ("usage_metrics", "tickets", "documents"):
        assert _rows(src, table) == _rows(dest, table), table

    # accounts match on every column a customer would actually supply;
    # `archetype` is our synthetic ground-truth label and correctly defaults
    original = {r["account_id"]: dict(r) for r in src.execute("SELECT * FROM accounts")}
    loaded = {r["account_id"]: dict(r) for r in dest.execute("SELECT * FROM accounts")}
    assert set(original) == set(loaded)
    for acct_id, row in original.items():
        for column, value in row.items():
            if column != "archetype":
                assert loaded[acct_id][column] == value, f"{acct_id}.{column}"


def test_missing_required_column_is_fatal_and_named(source, tmp_path):
    """A customer whose export lacks a renewal date must be told exactly that,
    rather than getting a half-loaded database."""
    src, export_dir, mapping = source
    accounts = export_dir / "accounts.csv"
    rows = list(csv.DictReader(accounts.open()))
    keep = [c for c in rows[0] if c != "Contract End Date"]
    with accounts.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keep, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    dest = init_db(tmp_path / "dest.sqlite")
    report = ingest(dest, export_dir, mapping)
    assert not report.ok
    assert any("contract_end" in e for e in report.errors)
    assert report.loaded.get("accounts", 0) == 0


def test_us_date_format_is_accepted(tmp_path):
    """CRM exports routinely use MM/DD/YYYY; that must not be a migration."""
    (tmp_path / "accounts.csv").write_text(
        "Account ID,Account Name,Contract End Date\n"
        "a1,Cedar Family Practice,03/14/2027\n")
    mapping = {"files": {"accounts": {
        "file": "accounts.csv",
        "columns": {"account_id": "Account ID", "name": "Account Name",
                    "contract_end": "Contract End Date"}}}}
    conn = init_db(tmp_path / "d.sqlite")
    report = ingest(conn, tmp_path, mapping)
    assert report.ok, report.errors
    row = conn.execute("SELECT * FROM accounts").fetchone()
    assert row["contract_end"] == "2027-03-14"
    assert row["specialty"] == "unknown"  # unmapped optional field defaults


def test_orphan_child_rows_are_reported_not_silently_dropped(tmp_path):
    """A ticket pointing at an account that isn't in the export is the classic
    migration failure — it must surface as a warning naming the row."""
    (tmp_path / "accounts.csv").write_text(
        "Account ID,Account Name,Contract End Date\na1,Cedar,2027-01-01\n")
    (tmp_path / "tickets.csv").write_text(
        "Ticket ID,Organization ID,Created At,Subject\n"
        "t1,a1,2026-01-05,Sync broken\n"
        "t2,GHOST,2026-01-06,Ticket for an unknown account\n")
    mapping = {"files": {
        "accounts": {"file": "accounts.csv",
                     "columns": {"account_id": "Account ID",
                                 "name": "Account Name",
                                 "contract_end": "Contract End Date"}},
        "tickets": {"file": "tickets.csv",
                    "columns": {"ticket_id": "Ticket ID",
                                "account_id": "Organization ID",
                                "opened_at": "Created At",
                                "subject": "Subject"}}}}
    conn = init_db(tmp_path / "d.sqlite")
    report = ingest(conn, tmp_path, mapping)
    assert report.ok
    assert report.loaded["tickets"] == 1
    assert any("GHOST" in w for w in report.warnings)


def test_mapping_file_rejects_unknown_tables(tmp_path):
    bad = tmp_path / "m.yaml"
    bad.write_text(yaml.safe_dump({"files": {"invoices": {"file": "x.csv"}}}))
    with pytest.raises(ValueError, match="unknown tables"):
        load_mapping(bad)
