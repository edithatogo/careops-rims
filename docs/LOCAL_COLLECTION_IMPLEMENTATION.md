# Local collection and registry implementation — 2026-09-12

The downloaded DEV collector has been adapted into `scripts/collect_pubmed.py`; its original archive remains unchanged in ignored private storage. This is preparatory local work for T11/T14, not completion of their native acceptance or T10 dependencies.

Implemented: configured facility queries and batch limits; bounded POST requests; a shared SQLite rate limiter; response hashes and restart checkpoints; duplicate/search/fetch/split-window reconciliation; persistent source and PMID/DOI identities; versioned observations; immutable first-observed values and review history; contradiction quarantine; and immutable candidate bibliography/month exports. Title similarity does not merge records. Candidate staging cannot promote a release or overwrite the last accepted release.

The DoRA importer follows the observed public RSS schema. It retains raw feed dates and attribution text without treating them as verified publication dates, and does not retain abstracts in candidate records. A finite feed is not a complete institutional bibliography. The registry preserves unknown dates and requires explicit attribution decisions. Synthetic and live registries cannot mix.

## Verified local evidence

- PubMed query window 1800-01-01 through 2026-09-12: 1,261 expected IDs and 1,261 fetched records, archived with hashes. This reconciles the configured query, not institutional completeness.
- DoRA RSS: four records; full historical coverage unverified.
- Staged registry: 1,265 candidate records, all needing review, zero identifier contradictions detected. DoRA items without identifiers remain separate even if potentially overlapping PubMed titles.
- Complete candidate CSV/HTML plus 309 month-specific CSV/HTML exports were generated. Their key sets reconcile to the local registry only; no native model readback exists.
- Receipts, source responses, SQLite database and candidate exports are under ignored `private/ops/`. No collected records were added to Git.

## Reproduce

Use Python 3 from the repository root. All concurrent collectors must use the same rate database. A dead writer lock may only be removed after confirming its process has stopped.

```sh
python3 scripts/collect_pubmed.py --output private/ops/pubmed-baseline --rate-db private/ops/pubmed-rate.sqlite --start 1800-01-01 --end 2026-09-12
python3 scripts/stage_collected_publications.py --pubmed private/ops/pubmed-baseline/RUN_ID --dora private/ops/dora-probe --database private/ops/publications.sqlite --output private/ops/candidate-releases --release-id NEW_RELEASE_ID
```

The staging command verifies the successful collector receipt and response/candidate hashes, and requires `rss.xml` plus its download `receipt.json` containing `sha256`, `retrieved_at` and `item_count`. Hashes establish local integrity, not independent source authenticity. Completed runs and release directories are not overwritten. Resume an incomplete collector using `--resume RUN_DIRECTORY` with the exact original configuration and window.

## Remaining gates

Power BI browser access currently fails because its admin-enforced security policy cannot be verified. A bounded retry returned the same denial. No alternate route was used to bypass it. Once supported access returns: finish discovery, recover the original baseline, establish approved independent model isolation, prove canary write/rollback, and then apply/read back source/model/report changes.

Full DoRA history, attribution review, native M/DAX, the four-page report scope,
live refresh, native canonical/month key-set reconciliation, accepted release
promotion and scheduled delivery remain open. Direct-M runtime assets have not
been replaced by this candidate collector. T16/T17 remain conditional; no VM,
sharing, publication or schedule was changed.

## Derived author registry

The local implementation in `scripts/author_registry.py` builds an auditable author and author-publication evidence projection from structured PubMed author evidence and DORA records. It preserves author order, affiliation text, source keys, evidence URLs and review status, and reports `Confirmed`, `Probable` and `Unresolved` identity states. Name-only and ResearchGate-only matches remain review candidates. Regression coverage is in `tests/test_author_registry.py`; this projection does not promote records or write to the live tenant.

The author projection must be reconciled to canonical publication keys before any report or release export. Its statistics deliberately report completeness as `not_established` until source coverage and identity review are independently accepted.

Latest source evidence: [historical collection and reviewed reconciliation](HISTORICAL_SOURCE_RECONCILIATION.md) supersedes the four-item RSS-only candidate. Native acceptance remains open.
