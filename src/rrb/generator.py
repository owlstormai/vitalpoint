import random
from datetime import date, timedelta
from pathlib import Path

import yaml

from rrb.archetypes import ARCHETYPES

AS_OF = date(2026, 8, 1)
N_MONTHS = 15

CANARY_WORDS = [
    "walrus", "quasar", "bassoon", "glacier", "topaz", "merlot", "falcon",
    "nimbus", "juniper", "cobalt", "saffron", "obsidian", "tundra", "lyric",
    "harbor", "ember", "fjord", "zephyr", "onyx", "prairie",
]

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
        _gen_usage(conn, rng, acct)
        _gen_tickets(conn, rng, acct, labels[acct["account_id"]])
        _gen_documents(conn, rng, acct, labels[acct["account_id"]])
        lab = labels[acct["account_id"]]
        lab["drivers"] = [d for d in lab["drivers"] if d in lab["evidence"]]
    conn.commit()
    return labels
