# Detailed execution: E07_publication_platform_acceptance

This runbook refines the existing plan; it does not reset completed historical work or establish new live evidence. Execute each unchecked applicable task below and mirror its outcome into the owning plan. Read [stabilisation protocol](../../PUBLICATION_STABILISATION.md) first.

## Inputs

docs/PUBLICATION_PLATFORM_ACCEPTANCE.md; docs/SHAREPOINT_LIST_REGISTRY.md; config/organisation-hierarchy.json; source list/schema exports in private storage; S01 attribution corrections.

## 1. Verify canonical inventory

- [ ] List existing publication list, ingestion flow, archive, report and semantic model and record exact identities privately. Inspect duplicates and consumers; do not delete anything based on similar names.

## 2. Capture schema and restore path

- [ ] Read internal names, types, unique/index settings, item versioning and current review fields. Export definitions/config privately, then prove an isolated restore path before persistent changes.

## 3. Test list invariants

- [ ] Use isolated fixture storage for create/replay/update/concurrent duplicate tests. Preserve FirstObserved, review decision/notes and manual overrides. Verify readback by key and values, including long Unicode titles and missing PMID.

## 4. Controlled enrichment

- [ ] Only after S01 corrections, compare proposed organisation assignments to source affiliation evidence. Unknown geography/validity remains unknown. Produce a dry-run diff and verify key/review preservation before a controlled live backfill; read back exact changed values.

## 5. Monitoring and reconciliation

- [ ] Expose last successful collection, accepted batch, source status, stale/error state and quarantine counts. Compare list/model/full-export canonical sets and selected fields; compare monthly subsets separately. A failed run must not refresh the last-success timestamp.

## Acceptance

- [ ] Complete each acceptance gate with current evidence; unsupported fields or permission failures are specific blockers. Do not certify cloud acceptance from the local structural validator.

## Checkpoint

Run `python3 scripts/agent_harness.py check --task all` for local changes. Record task, outcome, command/exit code, target/version correlation privately, evidence path, rollback and remaining blocker. Never place tenant IDs in this file.
