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
