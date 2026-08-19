"""Eval harness. Gates: isolation is zero-tolerance; the rest have thresholds.

Run: .venv/bin/python -m evals.run_evals [--db PATH --labels PATH]
Exit code 1 on any gate failure (CI hooks on this).
"""
import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from rrb.brief import DRIVER_QUERIES, build_brief
from rrb.chunker import chunk_documents
from rrb.db import connect
from rrb.index import HybridIndex

ROOT = Path(__file__).resolve().parent.parent

GATES = {
    "risk_accuracy": 0.75,
    "satisfaction_accuracy": 0.75,
    "citation_faithfulness": 1.0,
    "recall_at_5": 0.75,
    # Accounts hold only 3-8 chunks each, so a k=5 retrieval often returns the
    # whole scope and recall@5 comes cheap. MRR grades by RANK, so it stays
    # honest about whether the planted evidence actually surfaces first.
    "mrr": 0.7,
    "abstention_accuracy": 0.9,
}


def run_evals(db_path: str, labels_path: str) -> dict:
    conn = connect(db_path)
    labels = yaml.safe_load(Path(labels_path).read_text())
    index = HybridIndex(chunk_documents(conn))
    ids = list(labels)

    # 1. tenant isolation: query every scope with every OTHER account's canary.
    # The positive control matters as much as the leak count: a retrieve() that
    # silently returned nothing would score zero leaks and pass vacuously, so
    # every canary must first prove it IS findable inside its own scope.
    leaks = 0
    control_failures = 0
    for victim in ids:
        canary = labels[victim]["canary"]
        own = index.for_account(victim).retrieve(canary, k=5)
        if not any(canary in h.chunk.text for h in own):
            control_failures += 1
        for attacker in ids:
            if attacker == victim:
                continue
            for hit in index.for_account(attacker).retrieve(canary, k=5):
                if canary in hit.chunk.text or hit.chunk.account_id == victim:
                    leaks += 1

    # 2, 3, 4, 6: risk accuracy, satisfaction accuracy, citation
    # faithfulness, and abstention honesty — all measured by driving the
    # real build_brief() pipeline (not by recomputing score_risk() in
    # isolation) so the harness exercises exactly what `rrb brief` produces,
    # narrative drivers included.
    risk_ok = sat_ok = sat_n = 0
    cit_total = cit_ok = abst_ok = 0
    risk_detail: list[tuple[str, str, str]] = []  # (archetype, expected, got)
    sat_detail: list[tuple[str, str, str]] = []
    for acct_id, lab in labels.items():
        b = build_brief(conn, index, acct_id)

        risk_detail.append((lab["archetype"], lab["risk"], b.risk.level))
        if b.risk.level == lab["risk"]:
            risk_ok += 1

        if b.satisfaction.label != "unknown":
            sat_n += 1
            sat_detail.append(
                (lab["archetype"], lab["satisfaction"], b.satisfaction.label))
            if b.satisfaction.label == lab["satisfaction"]:
                sat_ok += 1

        for cit in b.citations:
            cit_total += 1
            body = conn.execute("SELECT body FROM documents WHERE doc_id=?",
                                (cit.doc_id,)).fetchone()["body"]
            if cit.excerpt in body:
                cit_ok += 1

        expected_unknown = "qbr_notes" in lab["withheld"]
        if ("qbr_notes" in b.unknowns) == expected_unknown:
            abst_ok += 1

    # 5. retrieval quality on planted evidence: recall@5 and MRR
    rec_total = rec_ok = 0
    reciprocal_ranks = 0.0
    for acct_id, lab in labels.items():
        scope = index.for_account(acct_id)
        for driver, doc_id in lab["evidence"].items():
            rec_total += 1
            hits = scope.retrieve(DRIVER_QUERIES[driver], k=5)
            rank = next((i for i, h in enumerate(hits, 1)
                         if h.chunk.doc_id == doc_id), None)
            if rank is not None:
                rec_ok += 1
                reciprocal_ranks += 1.0 / rank

    n = len(ids)
    report = {
        "accounts": n,
        "isolation_leaks": leaks,
        "isolation_control_failures": control_failures,
        "risk_accuracy": round(risk_ok / n, 3),
        "satisfaction_accuracy": round(sat_ok / max(sat_n, 1), 3),
        "citation_faithfulness": round(cit_ok / max(cit_total, 1), 3),
        "recall_at_5": round(rec_ok / max(rec_total, 1), 3),
        "mrr": round(reciprocal_ranks / max(rec_total, 1), 3),
        "abstention_accuracy": round(abst_ok / n, 3),
    }
    report["passed"] = leaks == 0 and control_failures == 0 and all(
        report[k] >= v for k, v in GATES.items())
    # underscore-prefixed: per-archetype detail for confusion printing on
    # failure, not part of the public report contract.
    report["_risk_detail"] = risk_detail
    report["_sat_detail"] = sat_detail
    return report


def _print_confusion(name: str, detail: list[tuple[str, str, str]]) -> None:
    """Per-archetype confusion summary: expected vs got, mismatches only."""
    by_archetype: dict[str, Counter] = defaultdict(Counter)
    for archetype, expected, got in detail:
        by_archetype[archetype][(expected, got)] += 1
    print(f"\n{name} confusion by archetype (expected->got: count):")
    any_mismatch = False
    for archetype in sorted(by_archetype):
        mismatches = {pair: c for pair, c in by_archetype[archetype].items()
                      if pair[0] != pair[1]}
        if not mismatches:
            continue
        any_mismatch = True
        parts = ", ".join(f"{e}->{g}: {c}"
                           for (e, g), c in sorted(mismatches.items()))
        print(f"  {archetype:<22} {parts}")
    if not any_mismatch:
        print("  (no mismatches — gate failure must be elsewhere)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / "data" / "rrb.sqlite"))
    ap.add_argument("--labels",
                    default=str(ROOT / "data" / "golden" / "labels.yaml"))
    args = ap.parse_args()
    report = run_evals(args.db, args.labels)
    risk_detail = report.pop("_risk_detail")
    sat_detail = report.pop("_sat_detail")
    width = max(len(k) for k in report)
    for k, v in report.items():
        print(f"{k:<{width}}  {v}")
    if not report["passed"]:
        if report["risk_accuracy"] < GATES["risk_accuracy"]:
            _print_confusion("risk", risk_detail)
        if report["satisfaction_accuracy"] < GATES["satisfaction_accuracy"]:
            _print_confusion("satisfaction", sat_detail)
        print("\nEVAL GATES FAILED", file=sys.stderr)
        sys.exit(1)
    print("\nall gates passed")


if __name__ == "__main__":
    main()
