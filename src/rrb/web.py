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
    boot_conn = connect(db_path)
    index = HybridIndex(chunk_documents(boot_conn))
    boot_conn.close()
    _risk_cache: dict[str, tuple] = {}

    # sqlite connections are not safe for concurrent use across request
    # threads — each request opens its own.
    def _risk(conn, acct_id: str):
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
        conn = connect(db_path)
        try:
            q = "SELECT * FROM accounts WHERE 1=1"
            params: list = []
            if specialty:
                q += " AND specialty=?"; params.append(specialty)
            if state:
                q += " AND state=?"; params.append(state)
            rows = []
            for a in conn.execute(q + " ORDER BY account_id",
                                  params).fetchall():
                level, points, days = _risk(conn, a["account_id"])
                if risk and level != risk:
                    continue
                rows.append((days, level, points, a))
        finally:
            conn.close()
        rows.sort(key=lambda t: ({"high": 0, "medium": 1, "low": 2}[t[1]], t[0]))
        esc = html.escape
        trs = "".join(
            f"<tr><td><a href='/brief/{esc(a['account_id'])}'>"
            f"{esc(a['account_id'])}</a>"
            f"</td><td>{esc(a['name'])}</td>"
            f"<td>{esc(a['specialty'])}</td>"
            f"<td>{esc(a['city'])}, {esc(a['state'])}</td>"
            f"<td class='{level}'>{level} ({points})</td>"
            f"<td>{esc(a['contract_end'])} ({days}d)</td></tr>"
            for days, level, points, a in rows)
        body = (f"<h1>Renewal Risk — {len(rows)} accounts</h1>"
                "<p>Filter: ?specialty=dental · ?state=TX · ?risk=high</p>"
                "<table><tr><th>Account</th><th>Name</th><th>Specialty</th>"
                "<th>Location</th><th>Risk</th><th>Renewal</th></tr>"
                f"{trs}</table>")
        return PAGE.format(body=body)

    @app.get("/brief/{account_id}", response_class=HTMLResponse)
    def brief(account_id: str):
        conn = connect(db_path)
        try:
            b = build_brief(conn, index, account_id)
        except KeyError:
            return HTMLResponse(PAGE.format(body="<h1>Not found</h1>"),
                                status_code=404)
        finally:
            conn.close()
        return PAGE.format(
            body=f"<p><a href='/'>← all accounts</a></p>"
                 f"<pre>{html.escape(b.markdown)}</pre>")

    return app
