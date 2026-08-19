"""Map a customer's exports onto the canonical schema, with validation.

The schema in db.py is the *target*, not an assumption about anyone's systems.
A real customer arrives with a Salesforce account export, a Zendesk ticket
export and a usage report, each using its own column names. This module makes
that translation an artifact rather than a conversation:

    their CSVs + a mapping file  ->  validation report  ->  canonical SQLite

Two design choices worth knowing. Validation collects *every* problem and
returns a report instead of raising on the first bad row, because the useful
output for a customer is "here are the 14 things wrong with this export", not
the first one alphabetically. And the same mapping file can run backwards
(`write_export`) to emit CSVs in their column names, which gives us a
round-trip test: foreign-shaped export -> ingest -> identical database.
"""
import csv
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import yaml

# Canonical schema contract. `required` fields must be mapped to a real column
# in the source file; `optional` fields fall back to the given default when a
# customer's system simply does not track them.
CANONICAL: dict[str, dict] = {
    "accounts": {
        "key": "account_id",
        "required": ["account_id", "name", "contract_end"],
        "optional": {"specialty": "unknown", "city": "", "state": "",
                     "seats": 0, "arr": 0, "contract_start": "",
                     "auto_renew": 1, "archetype": "client"},
        "ints": ["seats", "arr", "auto_renew"],
        "dates": ["contract_start", "contract_end"],
    },
    "usage_metrics": {
        "required": ["account_id", "month", "logins"],
        "optional": {"active_users": 0, "appointments": 0},
        "ints": ["logins", "active_users", "appointments"],
        "dates": [],
    },
    "tickets": {
        "required": ["ticket_id", "account_id", "opened_at", "subject"],
        "optional": {"closed_at": None, "severity": "normal",
                     "status": "closed"},
        "ints": [],
        "dates": ["opened_at", "closed_at"],
    },
    "documents": {
        "required": ["doc_id", "account_id", "doc_type", "doc_date", "body"],
        "optional": {"title": ""},
        "ints": [],
        "dates": ["doc_date"],
    },
}

COLUMN_ORDER = {
    "accounts": ["account_id", "name", "specialty", "city", "state", "seats",
                 "arr", "contract_start", "contract_end", "auto_renew",
                 "archetype"],
    "usage_metrics": ["account_id", "month", "logins", "active_users",
                      "appointments"],
    "tickets": ["ticket_id", "account_id", "opened_at", "closed_at",
                "severity", "status", "subject"],
    "documents": ["doc_id", "account_id", "doc_type", "doc_date", "title",
                  "body"],
}

# Formats seen in real exports. ISO first because it is unambiguous; the US
# formats are accepted because CRM exports routinely use them.
DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d",
                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S")


@dataclass
class IngestReport:
    """What happened, in enough detail to hand back to the customer."""
    loaded: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)    # fatal: nothing loaded
    warnings: list[str] = field(default_factory=list)  # row skipped, rest fine

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        lines = []
        for table, n in self.loaded.items():
            lines.append(f"  {table:<15} {n:>6} rows")
        if self.warnings:
            lines.append(f"  {len(self.warnings)} warning(s):")
            lines += [f"    - {w}" for w in self.warnings[:10]]
            if len(self.warnings) > 10:
                lines.append(f"    ... and {len(self.warnings) - 10} more")
        if self.errors:
            lines.append(f"  {len(self.errors)} error(s):")
            lines += [f"    - {e}" for e in self.errors]
        return "\n".join(lines) or "  (nothing loaded)"


def load_mapping(path: str | Path) -> dict:
    mapping = yaml.safe_load(Path(path).read_text())
    unknown = set(mapping.get("files", {})) - set(CANONICAL)
    if unknown:
        raise ValueError(f"mapping references unknown tables: {sorted(unknown)}")
    return mapping


def _parse_date(value: str) -> str | None:
    """Normalize to ISO. Returns None when the value is empty or unparseable —
    callers decide whether that is fatal for the field in question."""
    value = (value or "").strip()
    if not value:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _coerce_int(value) -> int | None:
    text = str(value or "").strip().replace(",", "").replace("$", "")
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def ingest(conn, csv_dir: str | Path, mapping: dict) -> IngestReport:
    """Load mapped CSVs into an initialized canonical database."""
    csv_dir = Path(csv_dir)
    report = IngestReport()
    known_accounts: set[str] = set()

    # accounts first: child tables are checked against it for referential
    # integrity, which is the failure that silently ruins a real migration
    for table in ("accounts", "usage_metrics", "tickets", "documents"):
        spec = mapping.get("files", {}).get(table)
        if spec is None:
            if table == "accounts":
                report.errors.append("mapping has no 'accounts' file")
            continue
        path = csv_dir / spec["file"]
        if not path.exists():
            report.errors.append(f"{table}: file not found: {spec['file']}")
            continue

        columns = spec.get("columns", {})
        rules = CANONICAL[table]
        with path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            header = set(reader.fieldnames or [])

            missing = [f for f in rules["required"]
                       if f not in columns or columns[f] not in header]
            if missing:
                for f in missing:
                    src = columns.get(f)
                    why = ("not mapped" if src is None
                           else f"mapped to '{src}', which is not in the file")
                    report.errors.append(f"{table}.{f}: {why}")
                continue

            rows, skipped = [], 0
            for n, raw in enumerate(reader, start=2):  # row 1 is the header
                record, bad = {}, None
                for canonical_field in COLUMN_ORDER[table]:
                    if canonical_field in columns:
                        value = raw.get(columns[canonical_field], "")
                    elif canonical_field in rules["optional"]:
                        value = rules["optional"][canonical_field]
                    else:
                        value = ""
                    if canonical_field in rules["ints"]:
                        coerced = _coerce_int(value)
                        if coerced is None:
                            coerced = rules["optional"].get(canonical_field, 0)
                        value = coerced
                    elif canonical_field in rules["dates"]:
                        parsed = _parse_date(str(value) if value else "")
                        if parsed is None:
                            if canonical_field in rules["required"]:
                                bad = (f"{table} row {n}: unparseable "
                                       f"{canonical_field} "
                                       f"'{raw.get(columns.get(canonical_field, ''), '')}'")
                            else:
                                # fall back to the declared default rather than
                                # None: closed_at is genuinely nullable, but
                                # contract_start is NOT NULL and an absent one
                                # must not fail the whole load
                                parsed = rules["optional"].get(canonical_field)
                        value = parsed
                    record[canonical_field] = value

                if bad:
                    report.warnings.append(bad)
                    skipped += 1
                    continue
                if table == "accounts":
                    known_accounts.add(record["account_id"])
                elif record.get("account_id") not in known_accounts:
                    report.warnings.append(
                        f"{table} row {n}: account_id "
                        f"'{record.get('account_id')}' is not in accounts")
                    skipped += 1
                    continue
                rows.append(tuple(record[c] for c in COLUMN_ORDER[table]))

            if rows:
                placeholders = ",".join("?" * len(COLUMN_ORDER[table]))
                conn.executemany(
                    f"INSERT OR REPLACE INTO {table} VALUES ({placeholders})",
                    rows)
            report.loaded[table] = len(rows)
            if skipped:
                report.warnings.append(f"{table}: skipped {skipped} row(s)")

    conn.commit()
    return report


def write_export(conn, out_dir: str | Path, mapping: dict) -> dict[str, int]:
    """Run the mapping backwards: emit CSVs using the customer's column names.

    This exists so the mapping layer can be demonstrated (and tested) against
    data shaped like someone else's system rather than like ours.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = {}
    for table, spec in mapping.get("files", {}).items():
        columns = spec.get("columns", {})
        fields = [f for f in COLUMN_ORDER[table] if f in columns]
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        path = out_dir / spec["file"]
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow([columns[f] for f in fields])
            for r in rows:
                writer.writerow([r[f] for f in fields])
        written[table] = len(rows)
    return written
