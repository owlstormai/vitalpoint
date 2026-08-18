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
