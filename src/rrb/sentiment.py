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
