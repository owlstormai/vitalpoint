"""Build the synthetic dataset: sqlite db + golden labels."""
import argparse
from pathlib import Path

from rrb.db import init_db
from rrb.generator import generate, write_labels

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--accounts", type=int, default=300)
    ap.add_argument("--db", default=ROOT / "data" / "rrb.sqlite")
    ap.add_argument("--labels", default=ROOT / "data" / "golden" / "labels.yaml")
    args = ap.parse_args()
    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)
    conn = init_db(db_path)
    labels = generate(conn, seed=args.seed, n_accounts=args.accounts)
    write_labels(labels, args.labels)
    print(f"wrote {args.accounts} accounts → {db_path} and {args.labels}")


if __name__ == "__main__":
    main()
