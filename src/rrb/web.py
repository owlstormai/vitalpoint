"""FastAPI routes. Data assembly only — all markup lives in templates.py."""
import statistics
from collections import defaultdict

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from rrb import templates
from rrb.brief import ACTIONS, build_brief
from rrb.chunker import chunk_documents
from rrb.db import connect
from rrb.generator import AS_OF, VENDOR
from rrb.index import HybridIndex
from rrb.scoring import score_risk
from rrb.sentiment import score_satisfaction
from rrb.signals import compute_signals

RISK_ORDER = {"high": 0, "medium": 1, "low": 2}
HEALTHY_ACTION = "Confirm the renewal and send a thank-you note."


def create_app(db_path: str) -> FastAPI:
    app = FastAPI()

    # Built once at boot: chunking and indexing the whole corpus is the only
    # expensive step, and the dataset is static while the server runs.
    boot = connect(db_path)
    index = HybridIndex(chunk_documents(boot))
    usage_by_account: dict[str, list[int]] = defaultdict(list)
    for r in boot.execute(
            "SELECT account_id, logins FROM usage_metrics ORDER BY month"):
        usage_by_account[r["account_id"]].append(r["logins"])
    boot.close()

    # sqlite connections are not safe across request threads, so each request
    # opens its own; scored rows are cached since the dataset is static.
    _score_cache: dict[str, tuple] = {}

    def _score(conn, acct_id: str):
        if acct_id not in _score_cache:
            sig = compute_signals(conn, acct_id)
            docs = conn.execute(
                "SELECT * FROM documents WHERE account_id=? AND doc_type IN "
                "('ticket','qbr')", (acct_id,)).fetchall()
            sat = score_satisfaction(docs)
            r = score_risk(sig, sat)
            # keep the unrounded trend too: a -0.1% decline rounds to 0, and
            # deciding "is this declining" on the rounded value contradicts
            # the sparkline, which reads the raw series
            _score_cache[acct_id] = (r.level, r.points, sig.days_to_renewal,
                                     sat.score, sig.usage_change_pct)
        return _score_cache[acct_id]

    def _not_found() -> HTMLResponse:
        return HTMLResponse(
            templates.page(
                "Account not found",
                '<div class="card empty"><strong>Account not found</strong>'
                'No account with that identifier is in the book. '
                '<a href="/">Back to the renewal desk</a>.</div>',
                AS_OF.isoformat(), VENDOR, "brief-wrap"),
            status_code=404)

    @app.exception_handler(404)
    async def _handle_404(request, exc):
        # a URL like /brief/../x never matches the route (the path converter
        # rejects the slash), so without this it would fall through to
        # Starlette's bare JSON error instead of the app's own page
        return _not_found()

    @app.get("/", response_class=HTMLResponse)
    def dashboard(specialty: str = "", state: str = "", risk: str = "",
                  sort: str = "risk"):
        conn = connect(db_path)
        try:
            all_rows = []
            for a in conn.execute(
                    "SELECT * FROM accounts ORDER BY account_id").fetchall():
                level, points, days, sat, change = _score(conn, a["account_id"])
                all_rows.append({
                    "id": a["account_id"], "name": a["name"],
                    "specialty": a["specialty"], "city": a["city"],
                    "state": a["state"], "arr": a["arr"],
                    "renewal": a["contract_end"], "days": days,
                    "level": level, "points": points, "sat": sat,
                    "usage_change": round(change), "declining": change < 0,
                    "usage": usage_by_account.get(a["account_id"], []),
                })
        finally:
            conn.close()

        # portfolio stats describe the whole book, not the filtered view
        stats = {
            "total": len(all_rows),
            "high": sum(1 for r in all_rows if r["level"] == "high"),
            "arr_total": sum(r["arr"] for r in all_rows),
            "arr_at_risk": sum(r["arr"] for r in all_rows
                               if r["level"] == "high"),
            "soon": sum(1 for r in all_rows if r["days"] <= 30),
            "soon_high": sum(1 for r in all_rows
                             if r["days"] <= 30 and r["level"] == "high"),
            "median_sat": round(statistics.median(
                [r["sat"] for r in all_rows])) if all_rows else 0,
        }

        rows = [r for r in all_rows
                if (not specialty or r["specialty"] == specialty)
                and (not state or r["state"] == state)
                and (not risk or r["level"] == risk)]
        if sort == "renewal":
            rows.sort(key=lambda r: r["days"])
        elif sort == "arr":
            rows.sort(key=lambda r: -r["arr"])
        else:
            rows.sort(key=lambda r: (RISK_ORDER[r["level"]], r["days"]))

        specialties = sorted({r["specialty"] for r in all_rows})
        states = sorted({r["state"] for r in all_rows})
        return templates.dashboard_page(
            rows, stats, specialties, states,
            {"specialty": specialty, "state": state, "risk": risk,
             "sort": sort},
            VENDOR, AS_OF.isoformat())

    @app.get("/brief/{account_id}", response_class=HTMLResponse)
    def brief(account_id: str):
        conn = connect(db_path)
        try:
            acct = conn.execute("SELECT * FROM accounts WHERE account_id=?",
                                (account_id,)).fetchone()
            if acct is None:
                return _not_found()
            b = build_brief(conn, index, account_id)
        finally:
            conn.close()
        actions = [ACTIONS[d.key] for d in b.risk.drivers
                   if d.key in ACTIONS] or [HEALTHY_ACTION]
        return templates.brief_page(
            acct, b, usage_by_account.get(account_id, []), actions,
            VENDOR, AS_OF.isoformat())

    return app
