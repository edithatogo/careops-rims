# Detailed execution: T15_web_acceptance_release

This runbook refines the existing plan; it does not reset completed historical work or establish new live evidence. Execute each unchecked applicable task below and mirror its outcome into the owning plan. Read [stabilisation protocol](../../PUBLICATION_STABILISATION.md) first.

## Inputs

S01/S02/S03 plans and receipts; T11/T14/E01/E07 results; docs/RELEASE_READINESS.md; docs/VERSIONING_ARCHITECTURE.md; actual native report/model inventory.

## 1. Assess dependencies

- [ ] Read every required task outcome. Reject stale/missing receipts, mismatched target identities, untested rollback and local-only substitutes. Current source sync can finish before live acceptance, but cannot be labelled a production release.

## 2. Verify report and model

- [ ] Capture current page inventory and bindings; reconcile the approved publication page scope. Open every page and test empty/multiple filters, DORA-only and unassigned facility visibility, long citations, keyboard readability and persisted reload. Query validation alone does not prove rendering.

## 3. Verify complete recovery set

- [ ] Capture report/model definitions, list schemas/configuration, flow definitions, source/accepted-batch manifests and runtime dependency inventory privately. Record any export limitations. Prove restoration in isolation; never bundle credentials into an archive.

## 4. Verify source release

- [ ] Use S02 manifest and S03 sanitized remote commit. Test a fresh checkout and verify hashes. Record software version, schema version, batch version and private deployment-receipt pointer separately.

## 5. Release decision

- [ ] Record separate statuses for source package, native model, report rendering, data retention, exports and schedule/delivery. Perform publish/rebind only if explicitly approved. Do not manufacture a global completion label when a required gate is open.

## 6. Grants handover

- [ ] Only after the publication baseline is accepted, record its immutable commit/tag and target baseline, update CURRENT_STATE to the first G01 task and allow grants implementation. Leave T16/T17 dormant unless their explicit fallback conditions were met.

## Acceptance

- [ ] All unresolved gates have either passing evidence or an explicit owner-approved scope deferral. Deferred capability must not be described as implemented. Owner-visible handover states exactly what is automated.

## Checkpoint

Run `python3 scripts/agent_harness.py check --task all` for local changes. Record task, outcome, command/exit code, target/version correlation privately, evidence path, rollback and remaining blocker. Never place tenant IDs in this file.
