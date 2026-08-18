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
