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
