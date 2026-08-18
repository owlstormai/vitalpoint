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
