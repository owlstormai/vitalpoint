"""Serialize briefs to JSON for downstream systems.

The brief is only half useful sitting in a web page — the account team lives in
a CRM. Everything the UI renders comes from the structured Brief object, so the
same object serializes cleanly to a payload a CRM adapter can map onto its own
fields (a Salesforce Account/Opportunity, an SAP business partner, a Gainsight
health score) without re-parsing prose.

Citations travel with every claim: a risk driver in a CRM is only actionable if
the rep can see the ticket or QBR note it came from.
"""
from dataclasses import asdict


def brief_to_dict(acct, b) -> dict:
    """Flatten a Brief plus its account row into a CRM-ready payload."""
    return {
        "account": {
            "id": acct["account_id"],
            "name": acct["name"],
            "specialty": acct["specialty"],
            "city": acct["city"],
            "state": acct["state"],
            "seats": acct["seats"],
            "arr": acct["arr"],
            "contract_start": acct["contract_start"],
            "contract_end": acct["contract_end"],
            "auto_renew": bool(acct["auto_renew"]),
        },
        "risk": {
            "level": b.risk.level,
            "points": b.risk.points,
            "drivers": [
                {
                    "key": d.key,
                    "detail": d.detail,
                    "points": d.points,
                    # a driver with no evidence is reported, not hidden — the
                    # receiving system should be able to tell the difference
                    "evidence": (asdict(b.driver_evidence[d.key])
                                 if d.key in b.driver_evidence else None),
                }
                for d in b.risk.drivers
            ],
        },
        "satisfaction": {
            "score": b.satisfaction.score,
            "label": b.satisfaction.label,
            "quotes": [asdict(q) for q in b.satisfaction.quotes],
        },
        "signals": asdict(b.signals),
        "unknowns": b.unknowns,
        "citations": [asdict(c) for c in b.citations],
        "markdown": b.markdown,
    }
