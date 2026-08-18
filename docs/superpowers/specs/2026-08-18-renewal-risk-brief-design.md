# Renewal Risk Brief — Design

**Date:** 2026-08-18
**Status:** Approved pending user review
**Companion project:** [MedSec](https://github.com/owlstormai/MedSec) — this repo reuses its offline-first, cite-or-abstain, eval-gated philosophy.

## 1. What we're building

A retrieval-augmented generation (RAG) system that produces a **one-page renewal
risk brief per account** for a fictional SMB (small and medium-sized business)
medical-software vendor. Every claim in a brief cites its source document and
date. The technical star is **per-account metadata filtering with hard tenant
isolation**: with 300 clients whose data lives in one system, Account A's
documents must be provably unable to appear in Account B's brief.

The system runs fully offline by default (no API keys, deterministic outputs,
CI-safe). Setting `ANTHROPIC_API_KEY` upgrades the prose and the semantic
satisfaction scoring to Claude, behind the same citation-and-grounding gates.

## 2. The fictional world

- **Vendor:** "VitalPoint Software" — practice-management software for small
  medical practices.
- **Clients:** 300 accounts (`--accounts 300`, trivially adjustable), from a
  3-seat office to a ~90-seat multi-clinic group.
- **Specialty mix:** dental, family medicine, pediatrics, dermatology, physical
  therapy, behavioral health, optometry, chiropractic, urgent care, and similar.
- **Location mix:** spread across US cities/states.

Specialty and location are stored account attributes, usable for slicing in the
UI and for making accounts confusable (similar names, identical complaint
patterns) — which is what makes the isolation and citation guarantees
meaningful.

## 3. Synthetic dataset (hybrid generation)

### 3.1 Archetypes (hand-authored)

~12 account archetypes capture real renewal patterns:

healthy-and-quiet · usage-declining · support-burned · champion-left ·
billing-dispute · onboarding-never-finished · price-sensitive ·
feature-gap-shopping-competitor · outage-affected · expansion-candidate ·
stable-low-touch · silent-churn

Each archetype is a hand-written bundle of narrative material: ticket story
arcs, QBR (quarterly business review) note paragraphs, and contract clause
variants — written well enough that a cited excerpt reads like a real document.
Each archetype also defines **ground truth**: an expected risk level, expected
risk drivers, and an expected satisfaction level.

### 3.2 Generator (seeded, deterministic)

`scripts/make_dataset.py --seed 42 --accounts 300` assigns each account an
archetype plus noise, then emits:

- **SQLite rows:** account profile (name, specialty, location, seats, ARR —
  annual recurring revenue, contract start/end, auto-renew terms), ~15 months of
  monthly usage metrics, support ticket records (status, severity, timestamps).
- **Narrative documents:** ticket bodies, 2–4 QBR notes per account, a contract
  excerpt — each stamped with `account_id`, doc type, and date.
- **Golden labels:** per-account planted risk level, risk drivers, and
  satisfaction level, written to `data/golden/labels.yaml` for the eval harness.
- **Canaries:** one unique nonsense phrase per account embedded in its
  documents, used by leak tests to prove cross-account contamination never
  happens.
- **Withheld evidence:** for a subset of accounts the generator deliberately
  omits evidence for certain signals, so the "What we don't know" section can be
  evaluated for honesty.

Same seed → byte-identical dataset (unit-tested).

## 4. Architecture: two stores

```
make_dataset.py ──┬─→ SQLite (system of record)
                  │     accounts · contracts · tickets · usage_metrics
                  │
                  └─→ narrative docs ─→ chunk + tag (account_id, doc_type, date)
                                          │
                                          ▼
                              hybrid index: BM25 + dense (TF-IDF offline)
                              reciprocal-rank fusion, as in MedSec
```

- **SQLite** answers structured questions exactly (renewal date, ticket counts,
  usage trends) — no fuzzy retrieval for hard facts.
- **The document index** serves citable narrative text (ticket bodies, QBR
  notes, contract clauses) for the RAG side.

### 4.1 Tenant isolation (the star)

- The **only** public retrieval API is scoped:
  `scope = index.for_account("acct_0042"); scope.retrieve(query)`.
  No unscoped search method exists.
- The `account_id` filter is applied **inside the index before ranking**, never
  by post-filtering ranked results.
- Canary-based adversarial evals (see §7) make isolation a tested, CI-gated
  property rather than a convention.

## 5. Risk scoring — transparent rubric

Deterministic signals computed from SQLite:

| Signal | Source |
|---|---|
| Usage trend (last two quarters) | usage_metrics |
| Ticket volume / severity trend | tickets |
| Unresolved-ticket age | tickets |
| Days to renewal | contracts |
| Seat utilization | usage_metrics ÷ contract seats |
| QBR sentiment flags | QBR notes (structured flags) |
| **Satisfaction score** | semantic layer (§6) |

Each signal contributes weighted points; the total maps to **Low / Medium /
High** risk. Every signal shown in a brief carries its number and source
("logins down 41% Q-over-Q — usage_export, 2026-07"). No black box.

## 6. Satisfaction layer (the "vibe" signal)

A semantic pass reads each account's narrative documents and produces:

- a **satisfaction score (0–100)** with a label (Frustrated / Neutral / Happy),
- 2–3 representative quotes, each cited verbatim to source doc and date.

It exists to catch what numbers miss — modest ticket counts but escalating tone
("third time reporting this", "evaluating alternatives").

- **Offline mode:** deterministic lexicon scorer — curated dictionaries of
  frustration markers (escalation phrases, churn language, repeated-issue
  phrasing) and satisfaction markers, weighted by recency and doc type.
- **Claude mode:** the LLM reads the account's *scoped* documents and scores
  satisfaction under a strict contract: score + verbatim quoted citations, no
  unsupported claims.

The satisfaction score feeds the risk rubric as a weighted input, so
"numbers fine, vibe bad" accounts correctly climb to Medium/High. The brief gets
a dedicated **Customer Sentiment** section.

## 7. Eval harness (gates CI)

1. **Tenant isolation:** adversarial canary queries across all 300 accounts —
   zero tolerance; one leak fails the build.
2. **Risk-label accuracy:** predicted Low/Med/High vs. planted ground truth.
3. **Satisfaction accuracy:** predicted sentiment vs. planted ground truth, for
   both lexicon and Claude modes.
4. **Citation faithfulness:** every claim's cited chunk must actually contain
   the supporting text.
5. **Retrieval quality:** recall@5 and MRR (mean reciprocal rank) on planted
   evidence queries.
6. **Abstention honesty:** "What we don't know" must list exactly the signals
   whose evidence was deliberately withheld.

## 8. Brief format (one page per account)

1. Header: account, specialty, location, ARR, renewal date, days remaining.
2. **Risk level** (Low/Medium/High) with score breakdown.
3. Top 3–5 risk drivers, each citing source doc + date.
4. **Customer Sentiment:** satisfaction score + cited quotes.
5. Recent-history snapshot (tickets, usage, last QBR).
6. Recommended actions.
7. **What we don't know:** signals with no evidence (abstention discipline).

Offline: assembled extractively from templates + cited excerpts. With Claude:
prose rewritten under the rule *every claim keeps its citation, no new facts*.

## 9. Interfaces

- **CLI:** `rrb make-data`, `rrb ingest`, `rrb brief acct_0042`,
  `rrb brief --all`, `rrb serve`.
- **Web UI:** portfolio dashboard of all 300 accounts, sortable/filterable by
  risk, renewal date, specialty, location; click through to any brief.

## 10. Testing

- pytest unit tests: generator determinism (same seed → identical output),
  scoring rubric, scoped retriever (unscoped access impossible by
  construction), satisfaction lexicon, brief builder.
- Evals run in CI with zero API keys, like MedSec.

## 11. Stack

Python 3.12, `uv`, SQLite (stdlib `sqlite3`), scikit-learn TF-IDF for the dense
leg, FastAPI + minimal HTML for `rrb serve` (mirroring MedSec's web layer),
`anthropic` SDK optional.

## 12. Out of scope (YAGNI)

- Real CRM/ticketing integrations (Salesforce, Zendesk) — the generator's
  output formats stand in for exports.
- Authentication/multi-user in the web UI.
- Physical per-account indexes — documented as the enterprise-tier next step,
  not built.
- Non-US locales.
