# Renewal Risk Brief Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline-first RAG system that generates one-page, fully-cited renewal risk briefs for 300 synthetic SMB medical-practice accounts, with CI-gated tenant isolation.

**Architecture:** Two stores — SQLite as system of record (accounts, contracts, tickets, usage, narrative documents) and an in-memory hybrid BM25 + TF-IDF index whose only retrieval API is per-account scoped. A seeded generator composes the dataset from ~12 hand-authored archetypes and plants ground-truth labels, canary phrases, and withheld evidence that the eval harness scores against.

**Tech Stack:** Python 3.12, uv, sqlite3 (stdlib), scikit-learn (TF-IDF), PyYAML, FastAPI + uvicorn, pytest, optional `anthropic`.

**Conventions for every task:** run commands from the repo root `/Users/wojnickiphd/claude/GIthubProjects/vitalpoint`. The venv python is `.venv/bin/python`; pytest is `.venv/bin/python -m pytest`. Commit after every green test run. The dataset "today" is the constant `AS_OF = 2026-08-01`.

---

### Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `src/rrb/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_scaffold.py`
- Create: `.gitignore`

- [ ] **Step 1: Write files**

`pyproject.toml`:

```toml
[project]
name = "rrb"
version = "0.1.0"
description = "Renewal Risk Brief — cited, tenant-isolated renewal risk briefs from synthetic SMB data"
requires-python = ">=3.12"
dependencies = [
    "scikit-learn>=1.4",
    "pyyaml>=6.0",
    "fastapi>=0.110",
    "uvicorn>=0.29",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "httpx>=0.27"]
llm = ["anthropic>=0.40"]

[project.scripts]
rrb = "rrb.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/rrb"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`src/rrb/__init__.py`:

```python
__version__ = "0.1.0"
```

`tests/__init__.py`: empty file.

`tests/test_scaffold.py`:

```python
import rrb


def test_package_imports():
    assert rrb.__version__ == "0.1.0"
```

`.gitignore`:

```
.venv/
__pycache__/
*.egg-info/
data/rrb.sqlite
data/golden/labels.yaml
.pytest_cache/
```

- [ ] **Step 2: Create venv, install, run test**

```bash
uv venv --python 3.12 && uv pip install -e ".[dev]"
.venv/bin/python -m pytest tests/test_scaffold.py -v
```

Expected: 1 passed.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml src tests .gitignore uv.lock 2>/dev/null; git add -A && git commit -m "feat: scaffold rrb package"
```

---

### Task 2: SQLite schema and connection module

**Files:**
- Create: `src/rrb/db.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

`tests/test_db.py`:

```python
import sqlite3

from rrb.db import connect, init_db


def test_init_db_creates_tables(tmp_path):
    conn = init_db(tmp_path / "t.sqlite")
    names = {
        r["name"]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"accounts", "usage_metrics", "tickets", "documents"} <= names


def test_connect_returns_row_factory(tmp_path):
    conn = init_db(tmp_path / "t.sqlite")
    conn.execute(
        "INSERT INTO accounts VALUES ('a1','Acme Dental','dental','Austin','TX',"
        "5,6000,'2025-09-01','2026-08-31',1,'healthy_quiet')"
    )
    row = conn.execute("SELECT * FROM accounts").fetchone()
    assert isinstance(row, sqlite3.Row)
    assert row["specialty"] == "dental"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rrb.db'`

- [ ] **Step 3: Write implementation**

`src/rrb/db.py`:

```python
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
  account_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  specialty TEXT NOT NULL,
  city TEXT NOT NULL,
  state TEXT NOT NULL,
  seats INTEGER NOT NULL,
  arr INTEGER NOT NULL,
  contract_start TEXT NOT NULL,
  contract_end TEXT NOT NULL,
  auto_renew INTEGER NOT NULL,
  archetype TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS usage_metrics (
  account_id TEXT NOT NULL REFERENCES accounts(account_id),
  month TEXT NOT NULL,
  logins INTEGER NOT NULL,
  active_users INTEGER NOT NULL,
  appointments INTEGER NOT NULL,
  PRIMARY KEY (account_id, month)
);
CREATE TABLE IF NOT EXISTS tickets (
  ticket_id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES accounts(account_id),
  opened_at TEXT NOT NULL,
  closed_at TEXT,
  severity TEXT NOT NULL,
  status TEXT NOT NULL,
  subject TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
  doc_id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES accounts(account_id),
  doc_type TEXT NOT NULL,
  doc_date TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL
);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path: str | Path) -> sqlite3.Connection:
    conn = connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_db.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/rrb/db.py tests/test_db.py && git commit -m "feat: sqlite schema and connection helpers"
```

---

### Task 3: Archetype library (hand-authored content)

The narrative texture of the whole dataset lives here. Ticket arcs and QBR paragraphs deliberately use phrases that Task 11's sentiment lexicon matches — keep them in sync.

**Files:**
- Create: `src/rrb/archetypes.py`
- Test: `tests/test_archetypes.py`

- [ ] **Step 1: Write the failing test**

`tests/test_archetypes.py`:

```python
from rrb.archetypes import ARCHETYPES, DRIVERS


def test_twelve_archetypes():
    assert len(ARCHETYPES) == 12


def test_archetype_shape():
    for key, a in ARCHETYPES.items():
        assert a.key == key
        assert a.risk in {"low", "medium", "high"}
        assert a.satisfaction in {"frustrated", "neutral", "happy"}
        assert set(a.drivers) <= set(DRIVERS)
        assert len(a.ticket_arcs) >= 2
        assert len(a.qbr_paragraphs) >= 2
        assert a.clause
        assert a.weight >= 1
        assert 0.3 <= a.usage_trend <= 1.3


def test_driver_archetypes_have_marker_arcs():
    # every driver an archetype claims must have a ticket arc or QBR paragraph
    # tagged with that driver so the generator can record evidence doc ids
    for a in ARCHETYPES.values():
        tagged = {d for d, _, _ in a.ticket_arcs} | {d for d, _ in a.qbr_paragraphs}
        for d in a.drivers:
            assert d in tagged, f"{a.key} missing evidence fragment for {d}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_archetypes.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

`src/rrb/archetypes.py`. Ticket arcs are `(driver_tag, subject, body)`; QBR paragraphs are `(driver_tag, text)`. Use tag `"none"` for flavor fragments not tied to a driver. `usage_trend` is the quarter-over-quarter multiplier applied to usage volume.

```python
from dataclasses import dataclass, field

DRIVERS = [
    "usage_decline",
    "high_ticket_volume",
    "unresolved_tickets",
    "champion_departed",
    "billing_dispute",
    "onboarding_incomplete",
    "price_sensitivity",
    "competitor_evaluation",
    "outage_impact",
    "expansion_interest",
    "low_seat_utilization",
]


@dataclass(frozen=True)
class Archetype:
    key: str
    risk: str
    satisfaction: str
    drivers: list[str]
    usage_trend: float
    tickets_per_month: float
    severity: str
    ticket_arcs: list[tuple[str, str, str]]
    qbr_paragraphs: list[tuple[str, str]]
    clause: str
    weight: int


ARCHETYPES: dict[str, Archetype] = {a.key: a for a in [
    Archetype(
        key="healthy_quiet", risk="low", satisfaction="happy", drivers=[],
        usage_trend=1.02, tickets_per_month=0.3, severity="low",
        ticket_arcs=[
            ("none", "Question about appointment reminders",
             "Quick question — can reminder texts go out 48 hours ahead instead of 24? "
             "No rush, the team is very happy with the scheduler overall."),
            ("none", "Report export column order",
             "The monthly production report exports columns in a different order than the "
             "on-screen view. Minor thing, everything else works great for us."),
        ],
        qbr_paragraphs=[
            ("none", "Front desk reports the system has been smooth all quarter; staff say "
             "scheduling is easier than their previous vendor and adoption is strong."),
            ("none", "No open escalations. Office manager praised the reminder feature and "
             "said patients love the confirmation texts."),
        ],
        clause="Renewal: this agreement renews automatically for successive one-year terms "
               "unless either party gives 60 days written notice.",
        weight=6),
    Archetype(
        key="stable_low_touch", risk="low", satisfaction="neutral", drivers=[],
        usage_trend=0.99, tickets_per_month=0.2, severity="low",
        ticket_arcs=[
            ("none", "Password reset for new hire",
             "We have a new hygienist starting Monday and need a login created. Thanks."),
            ("none", "Insurance code list update",
             "Is there a way to bulk-update the insurance fee schedule for the new year? "
             "We did it manually last time."),
        ],
        qbr_paragraphs=[
            ("none", "Quiet quarter. Usage steady, no complaints raised, though the office "
             "rarely responds to check-in emails."),
            ("none", "The practice uses core scheduling only; billing module remains unused. "
             "No issues reported."),
        ],
        clause="Renewal: annual term with automatic renewal unless cancelled with 30 days "
               "notice before the anniversary date.",
        weight=5),
    Archetype(
        key="expansion_candidate", risk="low", satisfaction="happy",
        drivers=["expansion_interest"],
        usage_trend=1.12, tickets_per_month=0.5, severity="low",
        ticket_arcs=[
            ("expansion_interest", "Adding a second location",
             "We are opening a second office in the spring and want to know how "
             "multi-location scheduling works and what additional seats would cost."),
            ("none", "Training session for new associates",
             "We hired two associates and would like a refresher training session. The team "
             "really likes the platform and wants everyone fluent on it."),
        ],
        qbr_paragraphs=[
            ("expansion_interest", "Practice is growing; owner asked about multi-location "
             "support and additional seats for a planned second office."),
            ("none", "Usage climbing month over month. Strong champion in the office manager, "
             "who demos features to the rest of the staff."),
        ],
        clause="Renewal: annual auto-renewal; additional seats may be added mid-term at the "
               "then-current per-seat rate, prorated.",
        weight=3),
    Archetype(
        key="usage_declining", risk="high", satisfaction="neutral",
        drivers=["usage_decline", "low_seat_utilization"],
        usage_trend=0.65, tickets_per_month=0.4, severity="low",
        ticket_arcs=[
            ("usage_decline", "Deactivating two user accounts",
             "Please deactivate the logins for our two departed front desk staff. We are "
             "running with a smaller team for now."),
            ("none", "Question on data export",
             "How do we export our full patient schedule history to CSV? We want a local "
             "copy of our records."),
        ],
        qbr_paragraphs=[
            ("usage_decline", "Logins have fallen steadily this quarter and several licensed "
             "seats have not been used in over sixty days."),
            ("low_seat_utilization", "The practice is paying for more seats than active "
             "users; office manager was noncommittal about plans for the unused licenses."),
        ],
        clause="Renewal: one-year term, auto-renews unless 60 days notice; seat count may "
               "only be reduced at renewal.",
        weight=4),
    Archetype(
        key="support_burned", risk="high", satisfaction="frustrated",
        drivers=["high_ticket_volume", "unresolved_tickets"],
        usage_trend=0.97, tickets_per_month=3.0, severity="high",
        ticket_arcs=[
            ("high_ticket_volume", "Claims sync failing again",
             "This is the third time reporting this — claims submitted through the portal "
             "are stuck in pending. This is unacceptable for a billing workflow we depend "
             "on daily. Please escalate."),
            ("unresolved_tickets", "Still waiting on ticket from last month",
             "Our calendar double-booking issue from last month is still not fixed. Staff "
             "have lost confidence in support and the front desk has given up on the "
             "waitlist feature entirely."),
            ("none", "Printer integration broken after update",
             "After the last update, route slips stopped printing. Workaround is manual "
             "printing which wastes time every single day."),
        ],
        qbr_paragraphs=[
            ("high_ticket_volume", "Difficult quarter: ticket volume roughly tripled and the "
             "office manager described support response times as extremely frustrating."),
            ("unresolved_tickets", "Two severity-high tickets remain open past thirty days. "
             "The practice administrator said they are evaluating alternatives if the sync "
             "issue is not resolved before renewal."),
        ],
        clause="Renewal: annual term with auto-renewal; customer may terminate for material "
               "breach uncured within 30 days of written notice.",
        weight=3),
    Archetype(
        key="champion_left", risk="high", satisfaction="neutral",
        drivers=["champion_departed", "usage_decline"],
        usage_trend=0.8, tickets_per_month=0.5, severity="normal",
        ticket_arcs=[
            ("champion_departed", "Admin transfer request",
             "Our office manager, who set up the system, has left the practice. Please "
             "transfer administrator rights to the new practice coordinator."),
            ("usage_decline", "Where are the training materials?",
             "The person who knew the system best is gone and the new staff cannot find the "
             "training guides. Usage of the reporting module has basically stopped."),
        ],
        qbr_paragraphs=[
            ("champion_departed", "The internal champion departed in the spring; the new "
             "coordinator inherited the system without training and has no relationship "
             "with our team."),
            ("usage_decline", "Feature usage narrowing to basic scheduling since the admin "
             "change; reporting and billing modules idle for two months."),
        ],
        clause="Renewal: auto-renews annually unless either party provides 45 days written "
               "notice prior to term end.",
        weight=3),
    Archetype(
        key="billing_dispute", risk="medium", satisfaction="frustrated",
        drivers=["billing_dispute"],
        usage_trend=1.0, tickets_per_month=1.0, severity="normal",
        ticket_arcs=[
            ("billing_dispute", "Overcharged on last invoice",
             "Our June invoice charged us for 12 seats but our contract says 10. This is "
             "the second billing error this year and we are disputing the charge until a "
             "credit is issued."),
            ("billing_dispute", "Credit memo still not applied",
             "The promised credit from the seat overcharge has not appeared on this month's "
             "statement. Frankly this is getting ridiculous and our bookkeeper is upset."),
        ],
        qbr_paragraphs=[
            ("billing_dispute", "Relationship strained by repeated invoicing errors; a "
             "disputed overcharge is still pending with accounts receivable."),
            ("none", "Product usage itself is healthy — the dispute is entirely about "
             "billing accuracy, not functionality."),
        ],
        clause="Fees: seat count is fixed at 10 for the term; overage billing requires a "
               "signed order form. Disputed amounts due within 15 days of resolution.",
        weight=3),
    Archetype(
        key="onboarding_stuck", risk="high", satisfaction="frustrated",
        drivers=["onboarding_incomplete", "low_seat_utilization"],
        usage_trend=0.9, tickets_per_month=1.5, severity="normal",
        ticket_arcs=[
            ("onboarding_incomplete", "Data migration still incomplete",
             "Six months in and our historical patient records are still not migrated. "
             "Half the staff refuse to use the system until their charts are in it."),
            ("low_seat_utilization", "Only two of nine staff logging in",
             "We bought nine seats but only the front desk actually uses the system. The "
             "onboarding sessions kept getting rescheduled and never finished."),
        ],
        qbr_paragraphs=[
            ("onboarding_incomplete", "Implementation stalled: migration of legacy records "
             "remains incomplete and the clinical staff never completed training."),
            ("low_seat_utilization", "Seat utilization is under a third; the practice owner "
             "questioned paying for licenses nobody uses."),
        ],
        clause="Onboarding: vendor shall complete data migration and two training sessions "
               "within 90 days of contract start.",
        weight=3),
    Archetype(
        key="price_sensitive", risk="medium", satisfaction="neutral",
        drivers=["price_sensitivity"],
        usage_trend=1.0, tickets_per_month=0.5, severity="low",
        ticket_arcs=[
            ("price_sensitivity", "Question about renewal pricing",
             "We received the renewal notice and the per-seat price went up 8 percent. As a "
             "small practice we need to understand what we are getting for the increase."),
            ("none", "Downgrade options",
             "Is there a cheaper tier without the billing module? We only use scheduling and "
             "reminders and are reviewing all our software costs this year."),
        ],
        qbr_paragraphs=[
            ("price_sensitivity", "Office manager flagged budget pressure and asked about "
             "the lower tier ahead of renewal; price increase letter did not land well."),
            ("none", "Product satisfaction is fine; the conversation is entirely about "
             "cost justification."),
        ],
        clause="Fees: pricing may increase up to 8% at renewal with 90 days notice.",
        weight=4),
    Archetype(
        key="feature_gap_shopper", risk="medium", satisfaction="neutral",
        drivers=["competitor_evaluation"],
        usage_trend=0.95, tickets_per_month=0.8, severity="normal",
        ticket_arcs=[
            ("competitor_evaluation", "Does the platform support online intake forms?",
             "Patients keep asking to fill forms before arriving. A rep from a competitor "
             "demoed digital intake to us last week and we want to know your roadmap."),
            ("competitor_evaluation", "Two-way patient texting timeline",
             "We have asked about two-way texting for a year. We are comparing options "
             "before our renewal and this feature gap is the main sticking point."),
        ],
        qbr_paragraphs=[
            ("competitor_evaluation", "The practice is actively comparing us against a "
             "competitor that offers digital intake and two-way texting; renewal decision "
             "hinges on the roadmap conversation."),
            ("none", "Core scheduling usage remains steady and staff are comfortable with "
             "the current workflows."),
        ],
        clause="Renewal: annual term, 60 days notice to cancel; no exclusivity obligations.",
        weight=3),
    Archetype(
        key="outage_affected", risk="medium", satisfaction="frustrated",
        drivers=["outage_impact"],
        usage_trend=0.92, tickets_per_month=2.0, severity="high",
        ticket_arcs=[
            ("outage_impact", "System down during Monday clinic hours",
             "The scheduler was unreachable for three hours on our busiest morning. We had "
             "to run the front desk on paper. What is the plan to make sure this outage "
             "never happens again?"),
            ("outage_impact", "Requesting SLA credit for outage",
             "Per our agreement we are requesting the service credit for last month's "
             "downtime. Staff confidence took a real hit and patients noticed."),
        ],
        qbr_paragraphs=[
            ("outage_impact", "The March outage dominated the review; the practice asked for "
             "the incident report and the SLA credit and wants uptime commitments in "
             "writing."),
            ("none", "Aside from the incident, feature usage is normal and staff remain "
             "generally productive on the platform."),
        ],
        clause="Service levels: 99.5% monthly uptime; credits of 5% of monthly fees per "
               "full hour of unscheduled downtime, capped at 30%.",
        weight=2),
    Archetype(
        key="silent_churn", risk="medium", satisfaction="neutral",
        drivers=["usage_decline"],
        usage_trend=0.75, tickets_per_month=0.1, severity="low",
        ticket_arcs=[
            ("usage_decline", "How to archive old schedules",
             "We are tidying up our records. How do we archive last year's schedules? "
             "Also, is there a data export option?"),
            ("none", "Update billing contact",
             "Please change the billing contact email to our accountant's address."),
        ],
        qbr_paragraphs=[
            ("usage_decline", "Engagement is drifting down and the practice has gone quiet — "
             "no response to the last two check-in attempts, logins down by a quarter."),
            ("none", "No support burden at all, which combined with falling usage may "
             "indicate disengagement rather than health."),
        ],
        clause="Renewal: auto-renews for one-year terms unless 30 days notice is given.",
        weight=3),
]}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_archetypes.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/rrb/archetypes.py tests/test_archetypes.py && git commit -m "feat: hand-authored account archetype library"
```

---

### Task 4: Generator — accounts table

**Files:**
- Create: `src/rrb/generator.py`
- Test: `tests/test_generator_accounts.py`

- [ ] **Step 1: Write the failing test**

`tests/test_generator_accounts.py`:

```python
from rrb.db import init_db
from rrb.generator import generate


def _rows(conn, sql):
    return [tuple(r) for r in conn.execute(sql)]


def test_generates_requested_account_count(tmp_path):
    conn = init_db(tmp_path / "a.sqlite")
    generate(conn, seed=42, n_accounts=30)
    assert conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 30


def test_specialty_and_location_mix(tmp_path):
    conn = init_db(tmp_path / "a.sqlite")
    generate(conn, seed=42, n_accounts=60)
    specs = {r["specialty"] for r in conn.execute("SELECT specialty FROM accounts")}
    states = {r["state"] for r in conn.execute("SELECT state FROM accounts")}
    assert len(specs) >= 6
    assert len(states) >= 8


def test_deterministic_same_seed(tmp_path):
    c1 = init_db(tmp_path / "a.sqlite")
    c2 = init_db(tmp_path / "b.sqlite")
    generate(c1, seed=7, n_accounts=25)
    generate(c2, seed=7, n_accounts=25)
    assert _rows(c1, "SELECT * FROM accounts ORDER BY account_id") == _rows(
        c2, "SELECT * FROM accounts ORDER BY account_id")


def test_different_seed_differs(tmp_path):
    c1 = init_db(tmp_path / "a.sqlite")
    c2 = init_db(tmp_path / "b.sqlite")
    generate(c1, seed=7, n_accounts=25)
    generate(c2, seed=8, n_accounts=25)
    assert _rows(c1, "SELECT * FROM accounts ORDER BY account_id") != _rows(
        c2, "SELECT * FROM accounts ORDER BY account_id")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_generator_accounts.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

`src/rrb/generator.py` (first slice — accounts only; later tasks extend this file):

```python
import random
from datetime import date

from rrb.archetypes import ARCHETYPES

AS_OF = date(2026, 8, 1)
N_MONTHS = 15

SPECIALTIES = [
    "dental", "family medicine", "pediatrics", "dermatology",
    "physical therapy", "behavioral health", "optometry",
    "chiropractic", "urgent care", "podiatry",
]

CITIES = [
    ("Austin", "TX"), ("Columbus", "OH"), ("Tucson", "AZ"), ("Boise", "ID"),
    ("Raleigh", "NC"), ("Spokane", "WA"), ("Madison", "WI"), ("Reno", "NV"),
    ("Knoxville", "TN"), ("Des Moines", "IA"), ("Albany", "NY"),
    ("Springfield", "MO"), ("Fort Collins", "CO"), ("Savannah", "GA"),
    ("Portland", "ME"), ("Eugene", "OR"), ("Lancaster", "PA"),
    ("Sioux Falls", "SD"), ("Baton Rouge", "LA"), ("Provo", "UT"),
]

NAME_STEMS = [
    "Riverside", "Summit", "Lakeview", "Cedar", "Maple", "Northgate",
    "Brightpath", "Harbor", "Willow", "Stonebridge", "Sunrise", "Elm Street",
    "Parkside", "Blue Ridge", "Meadow", "Crescent", "Oakwood", "Foothill",
    "Silver Lake", "Canyon",
]

SUFFIX_BY_SPECIALTY = {
    "dental": ["Dental Group", "Family Dentistry", "Dental Care"],
    "family medicine": ["Family Practice", "Medical Group", "Primary Care"],
    "pediatrics": ["Pediatrics", "Children's Clinic"],
    "dermatology": ["Dermatology", "Skin Clinic"],
    "physical therapy": ["Physical Therapy", "Rehab & PT"],
    "behavioral health": ["Behavioral Health", "Counseling Center"],
    "optometry": ["Eye Care", "Vision Center"],
    "chiropractic": ["Chiropractic", "Spine & Wellness"],
    "urgent care": ["Urgent Care", "Walk-In Clinic"],
    "podiatry": ["Foot & Ankle", "Podiatry Group"],
}


def _pick_archetype(rng: random.Random) -> str:
    keys, weights = zip(*[(a.key, a.weight) for a in ARCHETYPES.values()])
    return rng.choices(keys, weights=weights, k=1)[0]


def _make_account(rng: random.Random, i: int) -> dict:
    specialty = rng.choice(SPECIALTIES)
    stem = rng.choice(NAME_STEMS)
    suffix = rng.choice(SUFFIX_BY_SPECIALTY[specialty])
    city, state = rng.choice(CITIES)
    seats = rng.choice([3, 4, 5, 6, 8, 10, 12, 15, 20, 30, 45, 60, 90])
    end_month = rng.randrange(12)  # renewal within the next 12 months
    contract_end = date(2026, 8, 15) if end_month == 0 else _add_months(
        date(2026, 8, 15), end_month)
    contract_start = _add_months(contract_end, -12)
    return {
        "account_id": f"acct_{i:04d}",
        "name": f"{stem} {suffix}",
        "specialty": specialty,
        "city": city,
        "state": state,
        "seats": seats,
        "arr": seats * rng.choice([900, 1080, 1200, 1440]),
        "contract_start": contract_start.isoformat(),
        "contract_end": contract_end.isoformat(),
        "auto_renew": 1 if rng.random() < 0.8 else 0,
        "archetype": _pick_archetype(rng),
    }


def _add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, min(d.day, 28))


def generate(conn, seed: int, n_accounts: int) -> dict:
    """Populate the db; returns golden labels {account_id: {...}}."""
    rng = random.Random(seed)
    labels: dict[str, dict] = {}
    for i in range(n_accounts):
        acct = _make_account(rng, i)
        conn.execute(
            "INSERT INTO accounts VALUES (:account_id,:name,:specialty,:city,"
            ":state,:seats,:arr,:contract_start,:contract_end,:auto_renew,"
            ":archetype)", acct)
        arch = ARCHETYPES[acct["archetype"]]
        labels[acct["account_id"]] = {
            "archetype": arch.key,
            "risk": arch.risk,
            "satisfaction": arch.satisfaction,
            "drivers": list(arch.drivers),
            "evidence": {},
            "canary": None,
            "withheld": [],
        }
    conn.commit()
    return labels
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_generator_accounts.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/rrb/generator.py tests/test_generator_accounts.py && git commit -m "feat: seeded account generation with specialty/location mix"
```

---

### Task 5: Generator — usage metrics and ticket rows

**Files:**
- Modify: `src/rrb/generator.py`
- Test: `tests/test_generator_metrics.py`

- [ ] **Step 1: Write the failing test**

`tests/test_generator_metrics.py`:

```python
from rrb.db import init_db
from rrb.generator import N_MONTHS, generate


def test_usage_rows_per_account(tmp_path):
    conn = init_db(tmp_path / "a.sqlite")
    generate(conn, seed=42, n_accounts=10)
    n = conn.execute("SELECT COUNT(*) FROM usage_metrics").fetchone()[0]
    assert n == 10 * N_MONTHS


def test_declining_archetype_usage_falls(tmp_path):
    conn = init_db(tmp_path / "a.sqlite")
    generate(conn, seed=42, n_accounts=120)
    row = conn.execute(
        "SELECT account_id FROM accounts WHERE archetype='usage_declining' LIMIT 1"
    ).fetchone()
    assert row, "seed 42 with 120 accounts should include usage_declining"
    months = [r["logins"] for r in conn.execute(
        "SELECT logins FROM usage_metrics WHERE account_id=? ORDER BY month",
        (row["account_id"],))]
    assert sum(months[-3:]) < sum(months[:3]) * 0.8


def test_ticket_volume_tracks_archetype(tmp_path):
    conn = init_db(tmp_path / "a.sqlite")
    generate(conn, seed=42, n_accounts=120)
    burned = conn.execute(
        "SELECT COUNT(*) n FROM tickets t JOIN accounts a USING(account_id) "
        "WHERE a.archetype='support_burned'").fetchone()["n"]
    quiet = conn.execute(
        "SELECT COUNT(*) n FROM tickets t JOIN accounts a USING(account_id) "
        "WHERE a.archetype='healthy_quiet'").fetchone()["n"]
    n_burned = conn.execute(
        "SELECT COUNT(*) n FROM accounts WHERE archetype='support_burned'"
    ).fetchone()["n"]
    n_quiet = conn.execute(
        "SELECT COUNT(*) n FROM accounts WHERE archetype='healthy_quiet'"
    ).fetchone()["n"]
    assert n_burned and n_quiet
    assert burned / n_burned > 3 * (quiet / max(n_quiet, 1))


def test_some_tickets_left_open(tmp_path):
    conn = init_db(tmp_path / "a.sqlite")
    generate(conn, seed=42, n_accounts=120)
    open_n = conn.execute(
        "SELECT COUNT(*) FROM tickets WHERE status='open'").fetchone()[0]
    assert open_n > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_generator_metrics.py -v`
Expected: FAIL (0 usage rows).

- [ ] **Step 3: Extend the generator**

Add to `src/rrb/generator.py` (new helpers + calls from `generate`):

```python
from datetime import timedelta


def _months_list() -> list[str]:
    # N_MONTHS month-strings ending the month before AS_OF (2025-05 .. 2026-07)
    out = []
    for back in range(N_MONTHS, 0, -1):
        out.append(_add_months(AS_OF.replace(day=1), -back).strftime("%Y-%m"))
    return out


def _gen_usage(conn, rng, acct: dict) -> None:
    arch = ARCHETYPES[acct["archetype"]]
    seats = acct["seats"]
    base_logins = seats * 22.0
    active = min(seats, max(1, round(seats * rng.uniform(0.75, 1.0))))
    monthly_mult = arch.usage_trend ** (1 / 3)  # quarterly trend → monthly
    level = 1.0
    for month in _months_list():
        level *= monthly_mult
        jitter = rng.uniform(0.9, 1.1)
        logins = max(1, round(base_logins * level * jitter))
        act = max(1, min(seats, round(active * level * jitter)))
        appts = max(0, round(logins * rng.uniform(2.5, 3.5)))
        conn.execute(
            "INSERT INTO usage_metrics VALUES (?,?,?,?,?)",
            (acct["account_id"], month, logins, act, appts))


def _gen_tickets(conn, rng, acct: dict, labels: dict) -> None:
    arch = ARCHETYPES[acct["archetype"]]
    n = max(0, round(rng.gauss(arch.tickets_per_month * N_MONTHS,
                               arch.tickets_per_month)))
    arcs = arch.ticket_arcs
    for j in range(n):
        driver, subject, body = arcs[j % len(arcs)]
        opened = AS_OF - timedelta(days=rng.randrange(7, N_MONTHS * 30))
        # unresolved_tickets archetypes keep recent tickets open a long time
        stays_open = (driver == "unresolved_tickets" or
                      (arch.severity == "high" and rng.random() < 0.25) or
                      rng.random() < 0.05)
        closed = None if stays_open else (
            opened + timedelta(days=rng.randrange(1, 14))).isoformat()
        tid = f"tick_{acct['account_id'][5:]}_{j:03d}"
        conn.execute(
            "INSERT INTO tickets VALUES (?,?,?,?,?,?,?)",
            (tid, acct["account_id"], opened.isoformat(), closed,
             arch.severity, "open" if closed is None else "closed", subject))
```

In `generate`, after the `INSERT INTO accounts` and labels bookkeeping for each account, call:

```python
        _gen_usage(conn, rng, acct)
        _gen_tickets(conn, rng, acct, labels[acct["account_id"]])
```

- [ ] **Step 4: Run all tests**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: all pass (including determinism tests from Task 4 — usage/tickets are inside the same seeded rng stream).

- [ ] **Step 5: Commit**

```bash
git add src/rrb/generator.py tests/test_generator_metrics.py && git commit -m "feat: usage metrics and ticket rows track archetypes"
```

---

### Task 6: Generator — narrative documents, canaries, withheld evidence, golden labels

**Files:**
- Modify: `src/rrb/generator.py`
- Create: `scripts/make_dataset.py`
- Test: `tests/test_generator_docs.py`

- [ ] **Step 1: Write the failing test**

`tests/test_generator_docs.py`:

```python
import yaml

from rrb.db import init_db
from rrb.generator import generate, write_labels


def _gen(tmp_path, n=80):
    conn = init_db(tmp_path / "a.sqlite")
    labels = generate(conn, seed=42, n_accounts=n)
    return conn, labels


def test_every_account_has_docs_and_canary(tmp_path):
    conn, labels = _gen(tmp_path)
    for acct_id, lab in labels.items():
        docs = conn.execute(
            "SELECT doc_type, body FROM documents WHERE account_id=?",
            (acct_id,)).fetchall()
        types = {d["doc_type"] for d in docs}
        assert "contract" in types
        assert lab["canary"] and any(lab["canary"] in d["body"] for d in docs)


def test_canaries_unique_and_absent_elsewhere(tmp_path):
    conn, labels = _gen(tmp_path)
    canaries = [l["canary"] for l in labels.values()]
    assert len(set(canaries)) == len(canaries)
    for acct_id, lab in labels.items():
        hit = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE account_id != ? AND body LIKE ?",
            (acct_id, f"%{lab['canary']}%")).fetchone()[0]
        assert hit == 0


def test_withheld_accounts_have_no_qbr(tmp_path):
    conn, labels = _gen(tmp_path, n=120)
    withheld = [a for a, l in labels.items() if "qbr_notes" in l["withheld"]]
    kept = [a for a, l in labels.items() if "qbr_notes" not in l["withheld"]]
    assert withheld and kept
    for a in withheld:
        n = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE account_id=? AND doc_type='qbr'",
            (a,)).fetchone()[0]
        assert n == 0
    n = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE account_id=? AND doc_type='qbr'",
        (kept[0],)).fetchone()[0]
    assert 2 <= n <= 4


def test_driver_evidence_recorded(tmp_path):
    conn, labels = _gen(tmp_path, n=120)
    flagged = [l for l in labels.values() if l["drivers"]]
    assert flagged
    for lab in flagged:
        for d in lab["drivers"]:
            assert d in lab["evidence"], f"no evidence doc for {d}"


def test_write_labels_roundtrip(tmp_path):
    conn, labels = _gen(tmp_path, n=10)
    p = tmp_path / "labels.yaml"
    write_labels(labels, p)
    assert yaml.safe_load(p.read_text()) == labels
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_generator_docs.py -v`
Expected: FAIL (`write_labels` missing / no documents).

- [ ] **Step 3: Extend the generator**

Add to `src/rrb/generator.py`:

```python
from pathlib import Path

import yaml

CANARY_WORDS = [
    "walrus", "quasar", "bassoon", "glacier", "topaz", "merlot", "falcon",
    "nimbus", "juniper", "cobalt", "saffron", "obsidian", "tundra", "lyric",
    "harbor", "ember", "fjord", "zephyr", "onyx", "prairie",
]


def _canary(rng, acct_id: str) -> str:
    w1, w2 = rng.sample(CANARY_WORDS, 2)
    return f"internal ref {w1}-{w2}-{acct_id[5:]}"


def _gen_documents(conn, rng, acct: dict, lab: dict) -> None:
    arch = ARCHETYPES[acct["archetype"]]
    acct_id = acct["account_id"]
    lab["canary"] = _canary(rng, acct_id)
    doc_n = 0

    def _add(doc_type: str, doc_date, title: str, body: str) -> str:
        nonlocal doc_n
        doc_id = f"doc_{acct_id[5:]}_{doc_n:03d}"
        doc_n += 1
        conn.execute("INSERT INTO documents VALUES (?,?,?,?,?,?)",
                     (doc_id, acct_id, doc_type, doc_date.isoformat(), title, body))
        return doc_id

    # contract excerpt — canary lives here so every account carries one
    body = (f"Contract excerpt for {acct['name']} ({acct['specialty']}, "
            f"{acct['city']}, {acct['state']}).\n\n{arch.clause}\n\n"
            f"Term: {acct['contract_start']} through {acct['contract_end']}. "
            f"Annual fee ${acct['arr']:,} for {acct['seats']} seats. "
            f"({lab['canary']})")
    _add("contract", date.fromisoformat(acct["contract_start"]),
         f"Master Subscription Agreement — {acct['name']}", body)

    # ticket body documents mirror the ticket rows' arcs; record evidence
    for j, (driver, subject, tbody) in enumerate(arch.ticket_arcs):
        doc_date = AS_OF - timedelta(days=rng.randrange(14, 200))
        doc_id = _add("ticket", doc_date, subject,
                      f"Support ticket from {acct['name']}: {tbody}")
        if driver in lab["drivers"] and driver not in lab["evidence"]:
            lab["evidence"][driver] = doc_id

    # QBR notes — quarterly; a slice of accounts has them withheld
    if rng.random() < 0.12:
        lab["withheld"].append("qbr_notes")
    else:
        n_qbr = rng.randrange(2, 5)
        paras = arch.qbr_paragraphs
        for q in range(n_qbr):
            driver, text = paras[q % len(paras)]
            doc_date = AS_OF - timedelta(days=90 * (q + 1) - rng.randrange(0, 20))
            doc_id = _add(
                "qbr", doc_date, f"QBR notes — {acct['name']} Q{q + 1}",
                f"Quarterly business review, {acct['name']} "
                f"({acct['specialty']}). {text}")
            if driver in lab["drivers"] and driver not in lab["evidence"]:
                lab["evidence"][driver] = doc_id
    conn.commit()


def write_labels(labels: dict, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(yaml.safe_dump(labels, sort_keys=True))
```

In `generate`, after `_gen_tickets(...)`, add:

```python
        _gen_documents(conn, rng, acct, labels[acct["account_id"]])
```

**Evidence fallback:** a driver may only appear in QBR paragraphs of a withheld account. After `_gen_documents` in `generate`, add a guard that backfills evidence from ticket docs, and if a driver still has no evidence doc, drop it from `drivers` (label must match what's findable):

```python
        lab = labels[acct["account_id"]]
        lab["drivers"] = [d for d in lab["drivers"] if d in lab["evidence"]]
```

`scripts/make_dataset.py`:

```python
"""Build the synthetic dataset: sqlite db + golden labels."""
import argparse
from pathlib import Path

from rrb.db import init_db
from rrb.generator import generate, write_labels

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--accounts", type=int, default=300)
    ap.add_argument("--db", default=ROOT / "data" / "rrb.sqlite")
    ap.add_argument("--labels", default=ROOT / "data" / "golden" / "labels.yaml")
    args = ap.parse_args()
    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)
    conn = init_db(db_path)
    labels = generate(conn, seed=args.seed, n_accounts=args.accounts)
    write_labels(labels, args.labels)
    print(f"wrote {args.accounts} accounts → {db_path} and {args.labels}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests, then build the real dataset once**

```bash
.venv/bin/python -m pytest tests/ -v
.venv/bin/python scripts/make_dataset.py
```

Expected: tests pass; script prints `wrote 300 accounts → …`.

- [ ] **Step 5: Commit**

```bash
git add src/rrb/generator.py scripts/make_dataset.py tests/test_generator_docs.py && git commit -m "feat: narrative docs, canaries, withheld evidence, golden labels"
```

---

### Task 7: Chunker

**Files:**
- Create: `src/rrb/chunker.py`
- Test: `tests/test_chunker.py`

- [ ] **Step 1: Write the failing test**

`tests/test_chunker.py`:

```python
from rrb.chunker import chunk_documents
from rrb.db import init_db
from rrb.generator import generate


def test_chunks_carry_metadata(tmp_path):
    conn = init_db(tmp_path / "a.sqlite")
    generate(conn, seed=42, n_accounts=20)
    chunks = chunk_documents(conn)
    assert chunks
    for c in chunks:
        assert c.account_id.startswith("acct_")
        assert c.doc_type in {"contract", "ticket", "qbr"}
        assert c.doc_date and c.title and c.text.strip()
        assert len(c.text.split()) <= 160


def test_chunk_ids_unique(tmp_path):
    conn = init_db(tmp_path / "a.sqlite")
    generate(conn, seed=42, n_accounts=20)
    chunks = chunk_documents(conn)
    ids = [c.chunk_id for c in chunks]
    assert len(set(ids)) == len(ids)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_chunker.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

`src/rrb/chunker.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    account_id: str
    doc_type: str
    doc_date: str
    title: str
    text: str


def _split(body: str, max_words: int = 150) -> list[str]:
    parts, current = [], []
    for para in [p.strip() for p in body.split("\n\n") if p.strip()]:
        if sum(len(p.split()) for p in current) + len(para.split()) > max_words:
            if current:
                parts.append("\n\n".join(current))
            current = [para]
        else:
            current.append(para)
    if current:
        parts.append("\n\n".join(current))
    return parts or [body]


def chunk_documents(conn) -> list[Chunk]:
    chunks: list[Chunk] = []
    for row in conn.execute(
            "SELECT * FROM documents ORDER BY account_id, doc_id"):
        for k, text in enumerate(_split(row["body"])):
            chunks.append(Chunk(
                chunk_id=f"{row['doc_id']}#c{k}",
                doc_id=row["doc_id"],
                account_id=row["account_id"],
                doc_type=row["doc_type"],
                doc_date=row["doc_date"],
                title=row["title"],
                text=text,
            ))
    return chunks
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_chunker.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/rrb/chunker.py tests/test_chunker.py && git commit -m "feat: paragraph chunker with per-chunk account metadata"
```

---

### Task 8: Scoped hybrid index (the tenant-isolation star)

Design intent: `HybridIndex` exposes **no** unscoped search. `for_account()` returns an `AccountScope` that builds its BM25/TF-IDF structures **only from that account's chunks** — other tenants' text never enters the scoped scoring path, which is stronger than post-filtering ranked results.

**Files:**
- Create: `src/rrb/index.py`
- Test: `tests/test_index.py`

- [ ] **Step 1: Write the failing test**

`tests/test_index.py`:

```python
import pytest

from rrb.chunker import chunk_documents
from rrb.db import init_db
from rrb.generator import generate
from rrb.index import HybridIndex


def _index(tmp_path, n=40):
    conn = init_db(tmp_path / "a.sqlite")
    labels = generate(conn, seed=42, n_accounts=n)
    return HybridIndex(chunk_documents(conn)), labels


def test_no_unscoped_retrieval_api(tmp_path):
    index, _ = _index(tmp_path)
    for name in ("retrieve", "search", "query"):
        assert not hasattr(index, name)


def test_scope_returns_only_own_account(tmp_path):
    index, labels = _index(tmp_path)
    acct = next(iter(labels))
    hits = index.for_account(acct).retrieve("billing invoice scheduling", k=8)
    assert hits
    assert all(h.chunk.account_id == acct for h in hits)


def test_unknown_account_raises(tmp_path):
    index, _ = _index(tmp_path)
    with pytest.raises(KeyError):
        index.for_account("acct_9999")


def test_canary_never_leaks_across_scopes(tmp_path):
    index, labels = _index(tmp_path, n=60)
    ids = list(labels)
    for other in ids[:10]:
        canary = labels[other]["canary"]
        for acct in ids:
            if acct == other:
                continue
            hits = index.for_account(acct).retrieve(canary, k=5)
            assert all(canary not in h.chunk.text for h in hits)


def test_exact_phrase_found_in_own_scope(tmp_path):
    index, labels = _index(tmp_path)
    acct, lab = next(iter(labels.items()))
    hits = index.for_account(acct).retrieve(lab["canary"], k=5)
    assert any(lab["canary"] in h.chunk.text for h in hits)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_index.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

`src/rrb/index.py`:

```python
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from rrb.chunker import Chunk

RRF_K = 60
_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


@dataclass(frozen=True)
class Retrieved:
    chunk: Chunk
    score: float


class _BM25:
    def __init__(self, docs: list[list[str]], k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.docs = docs
        self.doc_len = [len(d) for d in docs]
        self.avg_len = sum(self.doc_len) / max(len(docs), 1)
        self.tf = [Counter(d) for d in docs]
        df: Counter = Counter()
        for d in docs:
            df.update(set(d))
        n = len(docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5))
                    for t, c in df.items()}

    def scores(self, query: list[str]) -> list[float]:
        out = []
        for i in range(len(self.docs)):
            s = 0.0
            for t in query:
                if t not in self.tf[i]:
                    continue
                f = self.tf[i][t]
                denom = f + self.k1 * (
                    1 - self.b + self.b * self.doc_len[i] / self.avg_len)
                s += self.idf.get(t, 0.0) * f * (self.k1 + 1) / denom
            out.append(s)
        return out


class AccountScope:
    """Retrieval over exactly one account's chunks. Built from scoped chunks
    only — other tenants' text is not present in any scoring structure."""

    def __init__(self, account_id: str, chunks: list[Chunk]):
        self.account_id = account_id
        self._chunks = chunks
        self._bm25 = _BM25([_tokens(c.text) for c in chunks])
        self._vec = TfidfVectorizer()
        self._mat = self._vec.fit_transform([c.text for c in chunks])

    def retrieve(self, query: str, k: int = 5) -> list[Retrieved]:
        if not self._chunks:
            return []
        bm = self._bm25.scores(_tokens(query))
        dense = cosine_similarity(
            self._vec.transform([query]), self._mat)[0]
        rrf: defaultdict[int, float] = defaultdict(float)
        for ranking in (bm, dense):
            order = sorted(range(len(self._chunks)),
                           key=lambda i: ranking[i], reverse=True)
            for rank, i in enumerate(order):
                if ranking[i] > 0:
                    rrf[i] += 1.0 / (RRF_K + rank + 1)
        top = sorted(rrf.items(), key=lambda kv: kv[1], reverse=True)[:k]
        return [Retrieved(self._chunks[i], s) for i, s in top]


class HybridIndex:
    """Holds all chunks grouped by account. Deliberately exposes no unscoped
    search — the only way to retrieve is through for_account()."""

    def __init__(self, chunks: list[Chunk]):
        self._by_account: dict[str, list[Chunk]] = defaultdict(list)
        for c in chunks:
            self._by_account[c.account_id].append(c)
        self._scopes: dict[str, AccountScope] = {}

    @property
    def account_ids(self) -> list[str]:
        return sorted(self._by_account)

    def for_account(self, account_id: str) -> AccountScope:
        if account_id not in self._by_account:
            raise KeyError(f"unknown account: {account_id}")
        if account_id not in self._scopes:
            self._scopes[account_id] = AccountScope(
                account_id, self._by_account[account_id])
        return self._scopes[account_id]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_index.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/rrb/index.py tests/test_index.py && git commit -m "feat: scoped hybrid BM25+TF-IDF index with no unscoped search API"
```

---

### Task 9: Risk signals from SQLite

**Files:**
- Create: `src/rrb/signals.py`
- Test: `tests/test_signals.py`

- [ ] **Step 1: Write the failing test**

`tests/test_signals.py`:

```python
from rrb.db import init_db
from rrb.generator import generate
from rrb.signals import compute_signals


def _first(conn, archetype):
    return conn.execute(
        "SELECT account_id FROM accounts WHERE archetype=? LIMIT 1",
        (archetype,)).fetchone()["account_id"]


def test_signal_fields(tmp_path):
    conn = init_db(tmp_path / "a.sqlite")
    generate(conn, seed=42, n_accounts=120)
    s = compute_signals(conn, _first(conn, "healthy_quiet"))
    assert s.days_to_renewal > 0
    assert 0 <= s.seat_utilization <= 1.5
    assert s.avg_tickets_per_month >= 0
    assert isinstance(s.has_qbr_docs, bool)


def test_declining_account_negative_trend(tmp_path):
    conn = init_db(tmp_path / "a.sqlite")
    generate(conn, seed=42, n_accounts=120)
    s = compute_signals(conn, _first(conn, "usage_declining"))
    assert s.usage_change_pct < -10


def test_support_burned_has_old_open_ticket(tmp_path):
    conn = init_db(tmp_path / "a.sqlite")
    generate(conn, seed=42, n_accounts=200)
    s = compute_signals(conn, _first(conn, "support_burned"))
    assert s.avg_tickets_per_month > 1.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_signals.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

`src/rrb/signals.py`:

```python
from dataclasses import dataclass
from datetime import date

from rrb.generator import AS_OF, N_MONTHS


@dataclass(frozen=True)
class Signals:
    usage_change_pct: float      # last 3 months vs prior 3, logins
    avg_tickets_per_month: float
    open_high_severity: int
    max_open_ticket_age_days: int
    days_to_renewal: int
    seat_utilization: float      # last-month active users / seats
    has_qbr_docs: bool
    has_tickets: bool


def compute_signals(conn, account_id: str, as_of: date = AS_OF) -> Signals:
    acct = conn.execute("SELECT * FROM accounts WHERE account_id=?",
                        (account_id,)).fetchone()
    if acct is None:
        raise KeyError(account_id)
    logins = [r["logins"] for r in conn.execute(
        "SELECT logins FROM usage_metrics WHERE account_id=? ORDER BY month",
        (account_id,))]
    recent, prior = sum(logins[-3:]), sum(logins[-6:-3])
    change = 100.0 * (recent - prior) / prior if prior else 0.0

    n_tickets = conn.execute(
        "SELECT COUNT(*) FROM tickets WHERE account_id=?",
        (account_id,)).fetchone()[0]
    open_high = conn.execute(
        "SELECT COUNT(*) FROM tickets WHERE account_id=? AND status='open' "
        "AND severity='high'", (account_id,)).fetchone()[0]
    oldest_open = conn.execute(
        "SELECT MIN(opened_at) m FROM tickets WHERE account_id=? AND "
        "status='open'", (account_id,)).fetchone()["m"]
    max_age = ((as_of - date.fromisoformat(oldest_open)).days
               if oldest_open else 0)

    last_active = conn.execute(
        "SELECT active_users FROM usage_metrics WHERE account_id=? "
        "ORDER BY month DESC LIMIT 1", (account_id,)).fetchone()
    util = (last_active["active_users"] / acct["seats"]) if last_active else 0.0

    has_qbr = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE account_id=? AND doc_type='qbr'",
        (account_id,)).fetchone()[0] > 0

    return Signals(
        usage_change_pct=round(change, 1),
        avg_tickets_per_month=round(n_tickets / N_MONTHS, 2),
        open_high_severity=open_high,
        max_open_ticket_age_days=max_age,
        days_to_renewal=(date.fromisoformat(acct["contract_end"]) - as_of).days,
        seat_utilization=round(util, 2),
        has_qbr_docs=has_qbr,
        has_tickets=n_tickets > 0,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_signals.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/rrb/signals.py tests/test_signals.py && git commit -m "feat: deterministic risk signals from sqlite"
```

---

### Task 10: Satisfaction layer — lexicon scorer

Lexicon phrases must match the archetype fragments from Task 3 (that coupling is the point: planted vibe → measurable recovery).

**Files:**
- Create: `src/rrb/sentiment.py`
- Test: `tests/test_sentiment.py`

- [ ] **Step 1: Write the failing test**

`tests/test_sentiment.py`:

```python
from rrb.db import init_db
from rrb.generator import generate
from rrb.sentiment import score_satisfaction


def _docs(conn, archetype):
    acct = conn.execute(
        "SELECT account_id FROM accounts WHERE archetype=? LIMIT 1",
        (archetype,)).fetchone()["account_id"]
    return acct, conn.execute(
        "SELECT * FROM documents WHERE account_id=? AND doc_type IN "
        "('ticket','qbr')", (acct,)).fetchall()


def test_frustrated_archetype_scores_low(tmp_path):
    conn = init_db(tmp_path / "a.sqlite")
    generate(conn, seed=42, n_accounts=200)
    _, docs = _docs(conn, "support_burned")
    sat = score_satisfaction(docs)
    assert sat.label == "frustrated"
    assert sat.score < 40


def test_happy_archetype_scores_high(tmp_path):
    conn = init_db(tmp_path / "a.sqlite")
    generate(conn, seed=42, n_accounts=200)
    _, docs = _docs(conn, "healthy_quiet")
    sat = score_satisfaction(docs)
    assert sat.label == "happy"
    assert sat.score > 70


def test_quotes_are_verbatim_with_provenance(tmp_path):
    conn = init_db(tmp_path / "a.sqlite")
    generate(conn, seed=42, n_accounts=200)
    _, docs = _docs(conn, "support_burned")
    sat = score_satisfaction(docs)
    assert sat.quotes
    bodies = {d["doc_id"]: d["body"] for d in docs}
    for q in sat.quotes:
        assert q.text in bodies[q.doc_id]
        assert q.title and q.doc_date


def test_no_docs_returns_none_label(tmp_path):
    sat = score_satisfaction([])
    assert sat.label == "unknown" and sat.quotes == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_sentiment.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

`src/rrb/sentiment.py`:

```python
import re
from dataclasses import dataclass

FRUSTRATION = {
    "third time reporting": 4, "unacceptable": 4, "escalate": 3,
    "still not fixed": 4, "lost confidence": 4, "given up": 4,
    "evaluating alternatives": 5, "extremely frustrating": 5,
    "getting ridiculous": 4, "disputing the charge": 3, "upset": 3,
    "refuse to use": 4, "stalled": 3, "never finished": 3,
    "did not land well": 2, "sticking point": 2, "strained": 3,
    "wastes time": 2, "took a real hit": 3, "on paper": 2,
    "never happens again": 3, "questioned paying": 3,
}

SATISFACTION_MARKERS = {
    "very happy": 4, "works great": 4, "smooth": 3, "praised": 4,
    "patients love": 4, "easier than": 3, "adoption is strong": 3,
    "really likes": 4, "strong champion": 3, "no open escalations": 3,
    "climbing": 2, "growing": 2, "generally productive": 2,
    "comfortable with": 2, "healthy": 2, "steady": 1,
}


@dataclass(frozen=True)
class Quote:
    text: str
    doc_id: str
    title: str
    doc_date: str


@dataclass(frozen=True)
class Satisfaction:
    score: int          # 0-100
    label: str          # frustrated | neutral | happy | unknown
    quotes: list[Quote]


def _sentences(body: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", body) if s.strip()]


def score_satisfaction(docs) -> Satisfaction:
    if not docs:
        return Satisfaction(score=50, label="unknown", quotes=[])
    neg = pos = 0.0
    scored: list[tuple[float, Quote]] = []
    for d in docs:
        for sent in _sentences(d["body"]):
            low = sent.lower()
            s_neg = sum(w for p, w in FRUSTRATION.items() if p in low)
            s_pos = sum(w for p, w in SATISFACTION_MARKERS.items() if p in low)
            neg += s_neg
            pos += s_pos
            if s_neg or s_pos:
                scored.append((s_pos - s_neg, Quote(
                    text=sent, doc_id=d["doc_id"], title=d["title"],
                    doc_date=d["doc_date"])))
    total = neg + pos
    score = 50 if total == 0 else round(100 * pos / total)
    label = "frustrated" if score < 40 else ("happy" if score > 70 else "neutral")
    # most polarized quotes, matching the overall direction
    scored.sort(key=lambda t: t[0], reverse=(score > 50))
    quotes = [q for _, q in scored[:3]]
    return Satisfaction(score=score, label=label, quotes=quotes)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_sentiment.py -v`
Expected: 4 passed. If a label assertion fails, the fix is adjusting FRUSTRATION / SATISFACTION_MARKERS phrase weights to match Task 3's fragments — not loosening the test.

- [ ] **Step 5: Commit**

```bash
git add src/rrb/sentiment.py tests/test_sentiment.py && git commit -m "feat: lexicon satisfaction scorer with verbatim cited quotes"
```

---

### Task 11: Risk rubric

**Files:**
- Create: `src/rrb/scoring.py`
- Test: `tests/test_scoring.py`

- [ ] **Step 1: Write the failing test**

`tests/test_scoring.py`:

```python
from rrb.scoring import score_risk
from rrb.sentiment import Satisfaction
from rrb.signals import Signals


def _sig(**kw):
    base = dict(usage_change_pct=0.0, avg_tickets_per_month=0.3,
                open_high_severity=0, max_open_ticket_age_days=0,
                days_to_renewal=200, seat_utilization=0.9,
                has_qbr_docs=True, has_tickets=True)
    base.update(kw)
    return Signals(**base)


def _sat(label, score):
    return Satisfaction(score=score, label=label, quotes=[])


def test_healthy_is_low():
    r = score_risk(_sig(), _sat("happy", 85))
    assert r.level == "low" and not r.drivers


def test_steep_decline_plus_frustration_is_high():
    r = score_risk(
        _sig(usage_change_pct=-35, seat_utilization=0.4),
        _sat("frustrated", 25))
    assert r.level == "high"
    keys = {d.key for d in r.drivers}
    assert "usage_decline" in keys and "low_seat_utilization" in keys


def test_vibe_alone_lifts_risk():
    calm = score_risk(_sig(), _sat("happy", 85))
    vibes = score_risk(_sig(), _sat("frustrated", 20))
    assert vibes.points > calm.points
    assert vibes.level in {"medium", "high"}


def test_every_driver_has_detail_text():
    r = score_risk(
        _sig(usage_change_pct=-35, avg_tickets_per_month=2.5,
             open_high_severity=2, max_open_ticket_age_days=45,
             days_to_renewal=30, seat_utilization=0.3),
        _sat("frustrated", 10))
    assert r.level == "high"
    for d in r.drivers:
        assert d.detail
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_scoring.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

`src/rrb/scoring.py`:

```python
from dataclasses import dataclass

from rrb.sentiment import Satisfaction
from rrb.signals import Signals


@dataclass(frozen=True)
class Driver:
    key: str
    detail: str
    points: int


@dataclass(frozen=True)
class RiskResult:
    level: str            # low | medium | high
    points: int
    drivers: list[Driver]


def score_risk(sig: Signals, sat: Satisfaction) -> RiskResult:
    drivers: list[Driver] = []

    def add(key, detail, pts):
        drivers.append(Driver(key=key, detail=detail, points=pts))

    if sig.usage_change_pct <= -20:
        add("usage_decline",
            f"logins down {abs(sig.usage_change_pct):.0f}% quarter-over-quarter",
            25)
    elif sig.usage_change_pct <= -10:
        add("usage_decline",
            f"logins down {abs(sig.usage_change_pct):.0f}% quarter-over-quarter",
            12)
    if sig.avg_tickets_per_month >= 2.0:
        add("high_ticket_volume",
            f"{sig.avg_tickets_per_month:.1f} tickets/month average", 18)
    if sig.max_open_ticket_age_days >= 30:
        add("unresolved_tickets",
            f"oldest open ticket {sig.max_open_ticket_age_days} days "
            f"({sig.open_high_severity} open high-severity)", 15)
    if sig.seat_utilization < 0.5:
        add("low_seat_utilization",
            f"only {sig.seat_utilization:.0%} of paid seats active", 10)
    if sat.label == "frustrated":
        add("negative_sentiment",
            f"satisfaction score {sat.score}/100 from ticket and QBR tone", 25)
    elif sat.label == "neutral" and sat.score < 50:
        add("negative_sentiment",
            f"satisfaction score {sat.score}/100 trending negative", 8)

    points = sum(d.points for d in drivers)
    if sig.days_to_renewal < 90 and points > 0:
        points += 10  # imminent renewal amplifies existing risk
    level = "high" if points >= 45 else ("medium" if points >= 20 else "low")
    return RiskResult(level=level, points=points, drivers=drivers)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_scoring.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/rrb/scoring.py tests/test_scoring.py && git commit -m "feat: transparent weighted risk rubric"
```

---

### Task 12: Brief builder

**Files:**
- Create: `src/rrb/brief.py`
- Test: `tests/test_brief.py`

- [ ] **Step 1: Write the failing test**

`tests/test_brief.py`:

```python
from rrb.brief import build_brief
from rrb.chunker import chunk_documents
from rrb.db import init_db
from rrb.generator import generate
from rrb.index import HybridIndex


def _setup(tmp_path, n=120):
    conn = init_db(tmp_path / "a.sqlite")
    labels = generate(conn, seed=42, n_accounts=n)
    return conn, HybridIndex(chunk_documents(conn)), labels


def test_brief_has_all_sections(tmp_path):
    conn, index, labels = _setup(tmp_path)
    b = build_brief(conn, index, next(iter(labels)))
    for heading in ("# Renewal Risk Brief", "## Risk", "## Customer Sentiment",
                    "## Recent History", "## Recommended Actions",
                    "## What We Don't Know"):
        assert heading in b.markdown


def test_citations_are_faithful(tmp_path):
    conn, index, labels = _setup(tmp_path)
    for acct in list(labels)[:15]:
        b = build_brief(conn, index, acct)
        for cit in b.citations:
            body = conn.execute(
                "SELECT body FROM documents WHERE doc_id=?",
                (cit.doc_id,)).fetchone()["body"]
            assert cit.excerpt in body


def test_citations_scoped_to_account(tmp_path):
    conn, index, labels = _setup(tmp_path)
    for acct in list(labels)[:15]:
        b = build_brief(conn, index, acct)
        for cit in b.citations:
            owner = conn.execute(
                "SELECT account_id FROM documents WHERE doc_id=?",
                (cit.doc_id,)).fetchone()["account_id"]
            assert owner == acct


def test_withheld_qbr_appears_in_unknowns(tmp_path):
    conn, index, labels = _setup(tmp_path, n=200)
    withheld = [a for a, l in labels.items() if "qbr_notes" in l["withheld"]]
    assert withheld
    b = build_brief(conn, index, withheld[0])
    assert "qbr_notes" in b.unknowns
    normal = [a for a, l in labels.items() if not l["withheld"]][0]
    b2 = build_brief(conn, index, normal)
    assert "qbr_notes" not in b2.unknowns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_brief.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

`src/rrb/brief.py`:

```python
from dataclasses import dataclass, field

from rrb.index import HybridIndex
from rrb.scoring import RiskResult, score_risk
from rrb.sentiment import Satisfaction, score_satisfaction
from rrb.signals import Signals, compute_signals

DRIVER_QUERIES = {
    "usage_decline": "logins falling seats not used deactivate accounts",
    "high_ticket_volume": "escalate unacceptable failing again support",
    "unresolved_tickets": "still waiting not fixed open ticket",
    "champion_departed": "office manager left transfer administrator rights",
    "billing_dispute": "overcharged invoice credit dispute",
    "onboarding_incomplete": "migration incomplete training never finished",
    "price_sensitivity": "renewal pricing increase cheaper tier budget",
    "competitor_evaluation": "competitor comparing options feature roadmap",
    "outage_impact": "outage downtime unreachable SLA credit",
    "expansion_interest": "second location additional seats growing",
    "low_seat_utilization": "seats not used only two logging in licenses",
    "negative_sentiment": "frustrating lost confidence evaluating alternatives",
}

ACTIONS = {
    "usage_decline": "Schedule an adoption review call; walk through unused workflows.",
    "high_ticket_volume": "Assign a named support contact and weekly status call.",
    "unresolved_tickets": "Escalate open tickets to engineering with committed dates.",
    "champion_departed": "Offer onboarding/training for the new administrator.",
    "billing_dispute": "Resolve the disputed invoice and confirm the credit in writing.",
    "onboarding_incomplete": "Restart implementation with a completion plan and owner.",
    "price_sensitivity": "Prepare a value summary and tier options before renewal call.",
    "competitor_evaluation": "Share the product roadmap; set an executive touchpoint.",
    "outage_impact": "Deliver the incident report and apply SLA credits proactively.",
    "expansion_interest": "Send a multi-location proposal — expansion, not just renewal.",
    "low_seat_utilization": "Right-size seats or drive activation before renewal.",
    "negative_sentiment": "Have the account manager call to hear concerns directly.",
}


@dataclass(frozen=True)
class Citation:
    doc_id: str
    title: str
    doc_date: str
    excerpt: str


@dataclass
class Brief:
    account_id: str
    markdown: str
    risk: RiskResult
    satisfaction: Satisfaction
    signals: Signals
    citations: list[Citation] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)


def build_brief(conn, index: HybridIndex, account_id: str) -> Brief:
    acct = conn.execute("SELECT * FROM accounts WHERE account_id=?",
                        (account_id,)).fetchone()
    if acct is None:
        raise KeyError(account_id)
    sig = compute_signals(conn, account_id)
    narrative = conn.execute(
        "SELECT * FROM documents WHERE account_id=? AND doc_type IN "
        "('ticket','qbr')", (account_id,)).fetchall()
    sat = score_satisfaction(narrative)
    risk = score_risk(sig, sat)
    scope = index.for_account(account_id)

    citations: list[Citation] = []
    unknowns: list[str] = []
    if not sig.has_qbr_docs:
        unknowns.append("qbr_notes")
    if not sig.has_tickets:
        unknowns.append("support_tickets")

    lines = [
        f"# Renewal Risk Brief — {acct['name']}",
        f"*{acct['specialty'].title()} · {acct['city']}, {acct['state']} · "
        f"{acct['seats']} seats · ARR ${acct['arr']:,}*",
        f"*Renewal: {acct['contract_end']} "
        f"({sig.days_to_renewal} days) · "
        f"auto-renew: {'yes' if acct['auto_renew'] else 'no'}*",
        "",
        f"## Risk: {risk.level.upper()} ({risk.points} pts)",
    ]
    if risk.drivers:
        for d in risk.drivers:
            hits = scope.retrieve(DRIVER_QUERIES[d.key], k=1)
            if hits:
                c = hits[0].chunk
                excerpt = c.text[:180]
                citations.append(Citation(
                    doc_id=c.doc_id, title=c.title, doc_date=c.doc_date,
                    excerpt=excerpt))
                lines.append(
                    f"- **{d.key}** — {d.detail}. "
                    f"Evidence: “{excerpt}…” ({c.title}, {c.doc_date})")
            else:
                lines.append(f"- **{d.key}** — {d.detail}. "
                             f"(no supporting document found)")
                unknowns.append(d.key)
    else:
        lines.append("- No active risk drivers detected.")

    lines += ["", "## Customer Sentiment",
              f"Satisfaction: **{sat.score}/100 ({sat.label})**"]
    for q in sat.quotes:
        citations.append(Citation(doc_id=q.doc_id, title=q.title,
                                  doc_date=q.doc_date, excerpt=q.text))
        lines.append(f"> “{q.text}” — {q.title}, {q.doc_date}")

    lines += ["", "## Recent History",
              f"- Usage trend: {sig.usage_change_pct:+.0f}% logins "
              f"quarter-over-quarter (usage_metrics)",
              f"- Support: {sig.avg_tickets_per_month:.1f} tickets/month, "
              f"{sig.open_high_severity} open high-severity (tickets)",
              f"- Seat utilization: {sig.seat_utilization:.0%} (usage_metrics "
              f"÷ contract seats)"]

    lines += ["", "## Recommended Actions"]
    action_keys = [d.key for d in risk.drivers] or ["healthy"]
    for k in action_keys:
        lines.append(f"- {ACTIONS.get(k, 'Send renewal confirmation and a thank-you note.')}")

    lines += ["", "## What We Don't Know"]
    if unknowns:
        friendly = {
            "qbr_notes": "No QBR notes on file — sentiment relies on tickets only.",
            "support_tickets": "No support tickets on file — no support signal.",
        }
        for u in unknowns:
            lines.append(f"- {friendly.get(u, f'No evidence found for {u}.')}")
    else:
        lines.append("- All rubric signals had supporting evidence.")

    return Brief(account_id=account_id, markdown="\n".join(lines), risk=risk,
                 satisfaction=sat, signals=sig, citations=citations,
                 unknowns=unknowns)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_brief.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/rrb/brief.py tests/test_brief.py && git commit -m "feat: extractive one-page brief with faithful scoped citations"
```

---

### Task 13: Optional Claude prose upgrade

**Files:**
- Create: `src/rrb/llm.py`
- Test: `tests/test_llm.py`

- [ ] **Step 1: Write the failing test**

`tests/test_llm.py`:

```python
from rrb.llm import maybe_rewrite


class _FakeBrief:
    markdown = "# Renewal Risk Brief — X\n- **usage_decline** — down 30%."
    citations = []


def test_no_key_returns_original(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    b = _FakeBrief()
    assert maybe_rewrite(b) is b.markdown


def test_rewrite_uses_injected_client(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    def fake_call(prompt: str) -> str:
        assert "every claim must keep its citation" in prompt.lower()
        return "REWRITTEN\n" + _FakeBrief.markdown

    out = maybe_rewrite(_FakeBrief(), _call=fake_call)
    assert out.startswith("REWRITTEN")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_llm.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

`src/rrb/llm.py`:

```python
import os

PROMPT = """You are rewriting a renewal risk brief for readability.

Rules — non-negotiable:
- Every claim must keep its citation (title, date) exactly as given.
- Do not add facts, numbers, or judgments not present in the draft.
- Keep every section heading. Keep quotes verbatim.
- If unsure, keep the original sentence.

Draft brief:
{draft}
"""


def _anthropic_call(prompt: str) -> str:
    import anthropic

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def maybe_rewrite(brief, _call=None) -> str:
    """Return polished markdown when a key is present, else the draft."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return brief.markdown
    call = _call or _anthropic_call
    return call(PROMPT.format(draft=brief.markdown))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_llm.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/rrb/llm.py tests/test_llm.py && git commit -m "feat: optional Claude prose rewrite behind citation-preserving contract"
```

---

### Task 14: CLI

**Files:**
- Create: `src/rrb/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

`tests/test_cli.py`:

```python
from rrb.cli import main


def test_make_data_and_brief(tmp_path, capsys):
    db = tmp_path / "rrb.sqlite"
    labels = tmp_path / "labels.yaml"
    main(["make-data", "--seed", "42", "--accounts", "25",
          "--db", str(db), "--labels", str(labels)])
    assert db.exists() and labels.exists()

    main(["brief", "acct_0003", "--db", str(db)])
    out = capsys.readouterr().out
    assert "# Renewal Risk Brief" in out


def test_brief_all_writes_files(tmp_path, capsys):
    db = tmp_path / "rrb.sqlite"
    main(["make-data", "--seed", "42", "--accounts", "10",
          "--db", str(db), "--labels", str(tmp_path / "l.yaml")])
    outdir = tmp_path / "briefs"
    main(["brief", "--all", "--db", str(db), "--out", str(outdir)])
    files = list(outdir.glob("acct_*.md"))
    assert len(files) == 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

`src/rrb/cli.py`:

```python
import argparse
from pathlib import Path

from rrb.brief import build_brief
from rrb.chunker import chunk_documents
from rrb.db import connect, init_db
from rrb.generator import generate, write_labels
from rrb.index import HybridIndex
from rrb.llm import maybe_rewrite

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB = ROOT / "data" / "rrb.sqlite"
DEFAULT_LABELS = ROOT / "data" / "golden" / "labels.yaml"


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="rrb")
    sub = ap.add_subparsers(dest="cmd", required=True)

    mk = sub.add_parser("make-data", help="generate the synthetic dataset")
    mk.add_argument("--seed", type=int, default=42)
    mk.add_argument("--accounts", type=int, default=300)
    mk.add_argument("--db", default=str(DEFAULT_DB))
    mk.add_argument("--labels", default=str(DEFAULT_LABELS))

    br = sub.add_parser("brief", help="build brief(s)")
    br.add_argument("account_id", nargs="?")
    br.add_argument("--all", action="store_true")
    br.add_argument("--db", default=str(DEFAULT_DB))
    br.add_argument("--out", default=str(ROOT / "runs" / "briefs"))

    sv = sub.add_parser("serve", help="run the web dashboard")
    sv.add_argument("--db", default=str(DEFAULT_DB))
    sv.add_argument("--port", type=int, default=8078)

    args = ap.parse_args(argv)

    if args.cmd == "make-data":
        db_path = Path(args.db)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_path.unlink(missing_ok=True)
        conn = init_db(db_path)
        labels = generate(conn, seed=args.seed, n_accounts=args.accounts)
        write_labels(labels, args.labels)
        print(f"wrote {args.accounts} accounts → {db_path}")
        return

    if args.cmd == "brief":
        conn = connect(args.db)
        index = HybridIndex(chunk_documents(conn))
        if args.all:
            outdir = Path(args.out)
            outdir.mkdir(parents=True, exist_ok=True)
            for acct_id in index.account_ids:
                b = build_brief(conn, index, acct_id)
                (outdir / f"{acct_id}.md").write_text(maybe_rewrite(b))
            print(f"wrote {len(index.account_ids)} briefs → {outdir}")
        else:
            if not args.account_id:
                ap.error("account_id required unless --all")
            b = build_brief(conn, index, args.account_id)
            print(maybe_rewrite(b))
        return

    if args.cmd == "serve":
        import uvicorn

        from rrb.web import create_app
        uvicorn.run(create_app(args.db), host="127.0.0.1", port=args.port)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/rrb/cli.py tests/test_cli.py && git commit -m "feat: rrb CLI (make-data, brief, serve)"
```

---

### Task 15: Web dashboard

**Files:**
- Create: `src/rrb/web.py`
- Test: `tests/test_web.py`

- [ ] **Step 1: Write the failing test**

`tests/test_web.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_web.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

`src/rrb/web.py`:

```python
import html

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from rrb.brief import build_brief
from rrb.chunker import chunk_documents
from rrb.db import connect
from rrb.index import HybridIndex
from rrb.scoring import score_risk
from rrb.sentiment import score_satisfaction
from rrb.signals import compute_signals

PAGE = """<!doctype html><html><head><title>Renewal Risk Briefs</title>
<style>body{{font-family:system-ui;margin:2rem;max-width:70rem}}
table{{border-collapse:collapse;width:100%}}td,th{{padding:.4rem .6rem;
border-bottom:1px solid #ddd;text-align:left}}
.high{{color:#b00020;font-weight:600}}.medium{{color:#b06a00}}
.low{{color:#1b7a2f}}pre{{white-space:pre-wrap}}</style></head>
<body>{body}</body></html>"""


def create_app(db_path: str) -> FastAPI:
    app = FastAPI()
    conn = connect(db_path)
    conn2 = connect(db_path)
    index = HybridIndex(chunk_documents(conn2))
    _risk_cache: dict[str, tuple] = {}

    def _risk(acct_id: str):
        if acct_id not in _risk_cache:
            sig = compute_signals(conn, acct_id)
            docs = conn.execute(
                "SELECT * FROM documents WHERE account_id=? AND doc_type IN "
                "('ticket','qbr')", (acct_id,)).fetchall()
            r = score_risk(sig, score_satisfaction(docs))
            _risk_cache[acct_id] = (r.level, r.points, sig.days_to_renewal)
        return _risk_cache[acct_id]

    @app.get("/", response_class=HTMLResponse)
    def dashboard(specialty: str = "", state: str = "", risk: str = ""):
        q = "SELECT * FROM accounts WHERE 1=1"
        params: list = []
        if specialty:
            q += " AND specialty=?"; params.append(specialty)
        if state:
            q += " AND state=?"; params.append(state)
        rows = []
        for a in conn.execute(q + " ORDER BY account_id", params):
            level, points, days = _risk(a["account_id"])
            if risk and level != risk:
                continue
            rows.append((days, level, points, a))
        rows.sort(key=lambda t: ({"high": 0, "medium": 1, "low": 2}[t[1]], t[0]))
        trs = "".join(
            f"<tr><td><a href='/brief/{a['account_id']}'>{a['account_id']}</a>"
            f"</td><td>{html.escape(a['name'])}</td>"
            f"<td>{a['specialty']}</td><td>{a['city']}, {a['state']}</td>"
            f"<td class='{level}'>{level} ({points})</td>"
            f"<td>{a['contract_end']} ({days}d)</td></tr>"
            for days, level, points, a in rows)
        body = (f"<h1>Renewal Risk — {len(rows)} accounts</h1>"
                "<p>Filter: ?specialty=dental · ?state=TX · ?risk=high</p>"
                "<table><tr><th>Account</th><th>Name</th><th>Specialty</th>"
                "<th>Location</th><th>Risk</th><th>Renewal</th></tr>"
                f"{trs}</table>")
        return PAGE.format(body=body)

    @app.get("/brief/{account_id}", response_class=HTMLResponse)
    def brief(account_id: str):
        try:
            b = build_brief(conn, index, account_id)
        except KeyError:
            return HTMLResponse(PAGE.format(body="<h1>Not found</h1>"),
                                status_code=404)
        return PAGE.format(
            body=f"<p><a href='/'>← all accounts</a></p>"
                 f"<pre>{html.escape(b.markdown)}</pre>")

    return app
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_web.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/rrb/web.py tests/test_web.py && git commit -m "feat: dashboard web UI with risk-sorted account list"
```

---

### Task 16: Eval harness

**Files:**
- Create: `evals/run_evals.py`
- Test: `tests/test_evals.py`

- [ ] **Step 1: Write the failing test**

`tests/test_evals.py`:

```python
from rrb.cli import main as cli_main
from evals.run_evals import run_evals


def test_evals_pass_on_generated_dataset(tmp_path):
    db = tmp_path / "rrb.sqlite"
    labels = tmp_path / "labels.yaml"
    cli_main(["make-data", "--seed", "42", "--accounts", "150",
              "--db", str(db), "--labels", str(labels)])
    report = run_evals(str(db), str(labels))
    assert report["isolation_leaks"] == 0
    assert report["risk_accuracy"] >= 0.75
    assert report["satisfaction_accuracy"] >= 0.75
    assert report["citation_faithfulness"] == 1.0
    assert report["recall_at_5"] >= 0.75
    assert report["abstention_accuracy"] >= 0.9
    assert report["passed"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_evals.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'evals'`

- [ ] **Step 3: Write implementation**

Create `evals/__init__.py` (empty) and `evals/run_evals.py`:

```python
"""Eval harness. Gates: isolation is zero-tolerance; the rest have thresholds.

Run: .venv/bin/python -m evals.run_evals [--db PATH --labels PATH]
Exit code 1 on any gate failure (CI hooks on this).
"""
import argparse
import sys
from pathlib import Path

import yaml

from rrb.brief import DRIVER_QUERIES, build_brief
from rrb.chunker import chunk_documents
from rrb.db import connect
from rrb.index import HybridIndex
from rrb.scoring import score_risk
from rrb.sentiment import score_satisfaction
from rrb.signals import compute_signals

ROOT = Path(__file__).resolve().parent.parent

GATES = {
    "risk_accuracy": 0.75,
    "satisfaction_accuracy": 0.75,
    "citation_faithfulness": 1.0,
    "recall_at_5": 0.75,
    "abstention_accuracy": 0.9,
}


def run_evals(db_path: str, labels_path: str) -> dict:
    conn = connect(db_path)
    labels = yaml.safe_load(Path(labels_path).read_text())
    index = HybridIndex(chunk_documents(conn))
    ids = list(labels)

    # 1. tenant isolation: query every scope with every OTHER account's canary
    leaks = 0
    for victim in ids:
        canary = labels[victim]["canary"]
        for attacker in ids:
            if attacker == victim:
                continue
            for hit in index.for_account(attacker).retrieve(canary, k=5):
                if canary in hit.chunk.text or hit.chunk.account_id == victim:
                    leaks += 1

    # 2 + 3. risk and satisfaction vs planted ground truth
    risk_ok = sat_ok = sat_n = 0
    for acct_id, lab in labels.items():
        sig = compute_signals(conn, acct_id)
        docs = conn.execute(
            "SELECT * FROM documents WHERE account_id=? AND doc_type IN "
            "('ticket','qbr')", (acct_id,)).fetchall()
        sat = score_satisfaction(docs)
        risk = score_risk(sig, sat)
        if risk.level == lab["risk"]:
            risk_ok += 1
        if sat.label != "unknown":
            sat_n += 1
            if sat.label == lab["satisfaction"]:
                sat_ok += 1

    # 4. citation faithfulness + 6. abstention honesty, via built briefs
    cit_total = cit_ok = abst_ok = 0
    for acct_id, lab in labels.items():
        b = build_brief(conn, index, acct_id)
        for cit in b.citations:
            cit_total += 1
            body = conn.execute("SELECT body FROM documents WHERE doc_id=?",
                                (cit.doc_id,)).fetchone()["body"]
            if cit.excerpt in body:
                cit_ok += 1
        expected_unknown = "qbr_notes" in lab["withheld"]
        if ("qbr_notes" in b.unknowns) == expected_unknown:
            abst_ok += 1

    # 5. retrieval recall@5 on planted evidence
    rec_total = rec_ok = 0
    for acct_id, lab in labels.items():
        scope = index.for_account(acct_id)
        for driver, doc_id in lab["evidence"].items():
            rec_total += 1
            hits = scope.retrieve(DRIVER_QUERIES[driver], k=5)
            if any(h.chunk.doc_id == doc_id for h in hits):
                rec_ok += 1

    n = len(ids)
    report = {
        "accounts": n,
        "isolation_leaks": leaks,
        "risk_accuracy": round(risk_ok / n, 3),
        "satisfaction_accuracy": round(sat_ok / max(sat_n, 1), 3),
        "citation_faithfulness": round(cit_ok / max(cit_total, 1), 3),
        "recall_at_5": round(rec_ok / max(rec_total, 1), 3),
        "abstention_accuracy": round(abst_ok / n, 3),
    }
    report["passed"] = leaks == 0 and all(
        report[k] >= v for k, v in GATES.items())
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / "data" / "rrb.sqlite"))
    ap.add_argument("--labels",
                    default=str(ROOT / "data" / "golden" / "labels.yaml"))
    args = ap.parse_args()
    report = run_evals(args.db, args.labels)
    width = max(len(k) for k in report)
    for k, v in report.items():
        print(f"{k:<{width}}  {v}")
    if not report["passed"]:
        print("\nEVAL GATES FAILED", file=sys.stderr)
        sys.exit(1)
    print("\nall gates passed")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test; tune if gates fail**

Run: `.venv/bin/python -m pytest tests/test_evals.py -v`

Expected: PASS. If `risk_accuracy` or `satisfaction_accuracy` miss the gate, print the per-account confusion (add a temporary loop printing `acct_id, expected, got`) and tune, in this order: (1) `scoring.py` thresholds/weights, (2) archetype numeric params (`usage_trend`, `tickets_per_month`) in `archetypes.py`, (3) lexicon weights in `sentiment.py`. Do not lower the gates.

- [ ] **Step 5: Commit**

```bash
git add evals tests/test_evals.py && git commit -m "feat: eval harness with zero-tolerance isolation gate"
```

---

### Task 17: CI workflow, README, full-run verification

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `README.md`

- [ ] **Step 1: Write CI workflow**

`.github/workflows/ci.yml`:

```yaml
name: ci
on:
  push: {branches: [main]}
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv venv --python 3.12 && uv pip install -e ".[dev]"
      - run: .venv/bin/python -m pytest tests/ -q
      - run: .venv/bin/rrb make-data --seed 42 --accounts 300
      - run: .venv/bin/python -m evals.run_evals
```

- [ ] **Step 2: Write README**

`README.md` — cover, in this order (write real prose, not placeholders):

```markdown
# rrb — Renewal Risk Brief

**One-page, fully-cited renewal risk briefs for 300 synthetic SMB medical
practices — with CI-gated tenant isolation.**

[what it does: 6-step list — generate data / ingest / scoped retrieval /
risk rubric + satisfaction layer / brief with citations + "what we don't
know" / evals]

[why tenant isolation is the point: scoped-only API, canaries, zero-tolerance
eval — 2 paragraphs]

## Quickstart (no API keys required)
uv venv --python 3.12 && uv pip install -e ".[dev]"
.venv/bin/rrb make-data
.venv/bin/rrb brief acct_0042
.venv/bin/rrb serve          # dashboard at http://127.0.0.1:8078
.venv/bin/python -m pytest tests/ -q
.venv/bin/python -m evals.run_evals

[architecture diagram: ascii, generator → sqlite + docs → chunker → scoped
index → signals/sentiment/scoring → brief → web/cli]

[eval table: the 6 evals with their gates]

[optional Claude section: ANTHROPIC_API_KEY upgrades prose + satisfaction,
same citation contract]
```

- [ ] **Step 3: Full verification run**

```bash
.venv/bin/python -m pytest tests/ -q
.venv/bin/rrb make-data --seed 42 --accounts 300
.venv/bin/rrb brief acct_0042
.venv/bin/python -m evals.run_evals
```

Expected: all tests pass; a real brief prints with citations; evals print all gates passed. Then start the dashboard via the preview tools (launch config or `rrb serve`) and confirm `/` lists 300 accounts sorted by risk.

- [ ] **Step 4: Commit**

```bash
git add .github README.md && git commit -m "feat: CI workflow and README"
```

---

## Self-Review (run after writing, fixed inline)

1. **Spec coverage:** dataset w/ 300 accounts+specialty/location mix (T4–T6), archetypes (T3), two stores (T2, T8), scoped isolation + canaries (T6, T8, eval 1), risk rubric (T9, T11), satisfaction layer offline+Claude (T10, T13), brief format incl. unknowns (T12), evals 1–6 (T16), CLI+web (T14, T15), CI (T17). Physical per-account indexes: out of scope per spec §12 — README mentions as future work only.
2. **Placeholder scan:** README step in T17 intentionally specifies structure with real content requirements rather than full prose (author judgment at execution time); all code steps contain complete code.
3. **Type consistency:** `Chunk` fields, `Retrieved.chunk`, `Signals` fields, `Satisfaction.label` values, `RiskResult.drivers[].key` values, and `DRIVER_QUERIES` keys cross-checked across tasks 7–12 and 16.
