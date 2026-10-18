# Detailed execution: E01_flow_automation

This runbook refines the existing plan; it does not reset completed historical work or establish new live evidence. Execute each unchecked applicable task below and mirror its outcome into the owning plan. Read [stabilisation protocol](../../PUBLICATION_STABILISATION.md) first.

## Inputs

scripts/build_sharepoint_upsert_package.py; config/flows/publication-registry-upsert.definition.json; scripts/validate_publication_platform_contract.py; docs/POWER_AUTOMATE_SHAREPOINT_FLOW.md; private baseline flow export.

## 1. Discover and export

- [ ] Inspect the existing canonical ingestion flow's connectors, triggers, action graph, list mapping and current run history. Distinguish the archive flow. Save a recoverable definition privately and confirm no concurrent edit.

## 2. Repair local first

- [x] Use S01's tested builder and verified column mapping. Validate explicit loop scope, dependency graph, lookup uniqueness, escaped keys, pagination and preservation of manual review fields. Evidence: `python3 -m unittest discover -s tests -p 'test_publication_platform_contract.py' -v` (16 passed, 8 private-package cases skipped) and `python3 scripts/validate_publication_platform_contract.py` passed against the tracked definition. These are local contract checks, not native flow acceptance.

## 3. Controlled update

- [ ] Apply to the existing isolated/manual test route after validating target and rollback. Read back the saved definition. No new parallel canonical ingestion flow; if isolation requires a test object, record its scope and retirement step.

## 4. Exercise actions

- [ ] In an isolated test data target run create, identical replay, changed metadata, two overlapping submissions, duplicate lookup and a failed source batch. Expect one key, preserved review/first-observed state, and failed batch excluded from acceptance. Never insert synthetic data into the production publication set.

## 5. Schedule gate

- [ ] Verify manual end-to-end flow completion with T11 and T14. Record proposed Brisbane schedule and rights. Check session approval for activation; absent explicit approval, leave activation unchecked and describe tested manual operation accurately.

## Acceptance

- [ ] Receipt must contain current definition hash, target mapping, run correlation, action outcomes and list readback. A successful package import does not satisfy execution.

## Local defect found and corrected

The 2026-09-20 manual-flow replay showed a blank `SourceKey` filter. The packaged definition explained why: the loop consumed the single-row readiness result (`SourceReadiness`, counts and audit status) as if it were a publication row. The local package now has a separate `Run_publication_rows_query` action that projects the canonical `Publication` table and derives a nonblank `SourceKey`; the loop depends on that action. The package was imported successfully into the existing DEV route; Flow Checker returned zero errors and zero warnings, and the route remains Disabled. Do not enable the recurrence until activation approval is present; the run/replay/update evidence gate remains open.

## Checkpoint

Run `python3 scripts/agent_harness.py check --task all` for local changes. Record task, outcome, command/exit code, target/version correlation privately, evidence path, rollback and remaining blocker. Never place tenant IDs in this file.
