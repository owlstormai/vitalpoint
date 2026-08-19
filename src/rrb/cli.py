import argparse
import json
from pathlib import Path

from rrb.brief import build_brief
from rrb.chunker import chunk_documents
from rrb.db import connect, init_db
from rrb.export import brief_to_dict
from rrb.generator import generate, write_labels
from rrb.index import HybridIndex
from rrb.llm import maybe_rewrite

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB = ROOT / "data" / "rrb.sqlite"
DEFAULT_LABELS = ROOT / "data" / "golden" / "labels.yaml"


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="rrb")
    sub = ap.add_subparsers(dest="cmd", required=True)

    mk = sub.add_parser("make-data", help="generate the synthetic dataset")
    mk.add_argument("--seed", type=int, default=42)
    mk.add_argument("--accounts", type=int, default=300)
    mk.add_argument("--db", default=str(DEFAULT_DB))
    mk.add_argument("--labels", default=str(DEFAULT_LABELS))

    br = sub.add_parser("brief", help="build brief(s)")
    br.add_argument("account_id", nargs="?")
    br.add_argument("--all", action="store_true")
    br.add_argument("--db", default=str(DEFAULT_DB))
    br.add_argument("--out", default=str(ROOT / "runs" / "briefs"))

    ex = sub.add_parser(
        "export", help="serialize briefs to JSON for CRM delivery")
    ex.add_argument("account_id", nargs="?")
    ex.add_argument("--all", action="store_true")
    ex.add_argument("--db", default=str(DEFAULT_DB))
    ex.add_argument("--out", default="-",
                    help="file path, or - for stdout (default)")

    sv = sub.add_parser("serve", help="run the web dashboard")
    sv.add_argument("--db", default=str(DEFAULT_DB))
    sv.add_argument("--port", type=int, default=8078)

    args = ap.parse_args(argv)

    if args.cmd == "make-data":
        db_path = Path(args.db)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_path.unlink(missing_ok=True)
        conn = init_db(db_path)
        labels = generate(conn, seed=args.seed, n_accounts=args.accounts)
        write_labels(labels, args.labels)
        print(f"wrote {args.accounts} accounts → {db_path}")
        return

    if args.cmd == "brief":
        conn = connect(args.db)
        index = HybridIndex(chunk_documents(conn))
        if args.all:
            outdir = Path(args.out)
            outdir.mkdir(parents=True, exist_ok=True)
            for i, acct_id in enumerate(index.account_ids, 1):
                b = build_brief(conn, index, acct_id)
                (outdir / f"{acct_id}.md").write_text(maybe_rewrite(b))
                if i % 50 == 0:
                    print(f"  {i}/{len(index.account_ids)}")
            print(f"wrote {len(index.account_ids)} briefs → {outdir}")
        else:
            if not args.account_id:
                ap.error("account_id required unless --all")
            b = build_brief(conn, index, args.account_id)
            print(maybe_rewrite(b))
        return

    if args.cmd == "export":
        conn = connect(args.db)
        index = HybridIndex(chunk_documents(conn))
        ids = index.account_ids if args.all else [args.account_id]
        if not args.all and not args.account_id:
            ap.error("account_id required unless --all")
        payload = []
        for acct_id in ids:
            acct = conn.execute("SELECT * FROM accounts WHERE account_id=?",
                                (acct_id,)).fetchone()
            if acct is None:
                ap.error(f"unknown account: {acct_id}")
            payload.append(brief_to_dict(acct, build_brief(conn, index, acct_id)))
        text = json.dumps(payload if args.all else payload[0], indent=2)
        if args.out == "-":
            print(text)
        else:
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text)
            print(f"wrote {len(payload)} brief(s) → {out}")
        return

    if args.cmd == "serve":
        import uvicorn

        from rrb.web import create_app
        uvicorn.run(create_app(args.db), host="127.0.0.1", port=args.port)
