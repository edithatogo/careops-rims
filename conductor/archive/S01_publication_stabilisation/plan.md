# Publication defects and report scope: executable plan

Status: complete. Local defects and current native report scope are reconciled; downstream native acceptance remains separate.

## S01.1 Baseline and scope inventory

- [x] S01.1.1: Read git status --short and git diff --stat. Record existing uncommitted paths; do not stage or overwrite the report/manifest edits.
- [x] S01.1.2: Run python3 scripts/agent_harness.py check --task all and retain the result. Local passes are the comparison baseline.
- [x] S01.1.3: Compare both report builders, dashboard contract and frozen runtime manifest. Inspect current report pages through supported read-only UI/plugin controls; record page IDs privately. Evidence: `private/ops/2026-09-20-powerbi-report-page-inventory.json`; native report inventory confirmed four pages and resolved the scope migration.
- [x] S01.1.4: Write a scope comparison table in review.md: observed pages, generated pages, contracted pages, mismatches and proposed resolution. Preserve existing publication functionality; grants pages belong to G08. If native inventory is unavailable, leave scope migration pending.
- [x] Checkpoint: write commands/results, changed paths and remaining blockers in review.md; update CURRENT_STATE. Stop dependent work on failure.

## S01.2 Evidence-preserving attribution

- [x] S01.2.1: Write failing tests in tests/test_organisation_enrichment.py for an unrelated Community Health/Primary Health Centre, partial-token aliases, absent affiliation, unknown dates, historical boundaries, duplicate organisation keys and invalid parent links.
- [x] S01.2.2: Change organisation matching to require specific source-backed aliases and preserve exact source affiliation text. Do not treat the 28 search definitions or keyword specialty labels as an approved organisation chart.
- [x] S01.2.3: Load reference version and effective dates from validated reference data; do not insert today's/build date as historical validity. Preserve unmatched/ambiguous cases and reviewed overrides.
- [x] S01.2.4: Inspect scripts/clinical_attribution.py and scripts/author_registry.py for name-only identity, free-text affiliation order interpreted as author order, inferred senior authorship and default topic classifications. Add counterexample tests before correcting unsupported certainty.
- [x] S01.2.5: Keep source-observed roles, inferred topic labels and reviewed organisation links separate. Unknown stays unknown. Run focused organisation/author/clinical tests.
- [x] Checkpoint: write commands/results, changed paths and remaining blockers in review.md; update CURRENT_STATE. Stop dependent work on failure.

## S01.3 Executable flow structure

- [x] S01.3.1: Create synthetic export fixtures and failing tests for wrong connectors/targets, unbound item(), missing loops, duplicate lookup results, missing dependency actions and review-field overwrite.
- [x] S01.3.2: Inspect baseline package privately. Build upserts inside an explicit record loop with valid runAfter references, source-key escaping, single-run/write concurrency and duplicate detection; do not add recurrence without its explicit gate.
- [x] S01.3.3: Make the builder consume validated private target/schema configuration. Preserve legitimate field_N internal names through a mapping; never rename live columns by guesswork.
- [x] S01.3.4: Replace string-presence assertions with action-graph and parameter checks. Reject a missing required package in acceptance mode; optional local skips must be reported as skips.
- [x] S01.3.5: Add a fail-closed local pagination/completeness contract and enforce the observation-only update allowlist. Preserve FirstObserved, ReviewStatus, ReviewNotes and manual overrides; partial batches cannot become accepted. Native paged-flow execution remains an E01/T15 acceptance gate.
- [x] Checkpoint: write commands/results, changed paths and remaining blockers in review.md; update CURRENT_STATE. Stop dependent work on failure.

## S01.4 Contract migration and handoff

- [x] S01.4.1: Only after scope resolution, update affected generators, declarations and tests together. Record why any golden manifest changes; do not regenerate it merely to make tests pass. Updated the web-first page declaration, validator and regression test from three to four; frozen runtime hashes were not regenerated.
- [x] S01.4.2: Run the full harness and inspect the scoped diff. Document remaining live tasks under T11/E01/E07 rather than marking them complete. Harness: `PASS_LOCAL_ONLY`; project validation: 319 checks passed; web-first validation: `PASS_LOCAL_ONLY`.
- [x] S01.4.3: Record the reviewed files, test commands/results and rollback patch/commit in review.md. The scoped files and native receipt are recorded; remaining live gates remain explicitly open.
- [x] Checkpoint: write commands/results, changed paths and remaining blockers in review.md; update CURRENT_STATE. Stop dependent work on failure.
