# Detailed execution: T14_complete_exports_monthly

This runbook refines the existing plan; it does not reset completed historical work or establish new live evidence. Execute each unchecked applicable task below and mirror its outcome into the owning plan. Read [stabilisation protocol](../../PUBLICATION_STABILISATION.md) first.

## Inputs

contracts/publication-export.contract.json; scripts/export_publication_register.py; scripts/export_monthly_docx.py; config/monthly-flow.blueprint.json; docs/MONTHLY_AUTOMATION.md; accepted T11 batch.

## 1. Freeze selection

- [ ] Select an accepted source batch and explicit Brisbane reporting month. Record expected canonical keys, date exclusions, review exclusions and filters independently of the rendered first screen.

## 2. Test export fidelity

- [x] Add and run local cases for more than one export page, long/Unicode authors and titles, DORA-only/no PMID, formula-safe CSV, duplicate/missing keys, uncertain month and December/January boundary. Evidence: `python3 -m unittest discover -s tests -p 'test_webfirst.py' -v` (64 passed) and `python3 -m unittest discover -s tests -p 'test_publication_batch_contract.py' -v` (5 passed). These are local contract checks, not native export acceptance.

## 3. Native dry run

- [ ] Run the actual export actions against the isolated model after a correlated successful refresh. Write candidate output to private staging; read back complete file contents, hashes, key sets and required fields. Do not email or publish.

## 4. Failure and replay

- [ ] Repeat the same batch/month. Verify stable logical content and no duplicate accepted monthly report; test truncated output and source failure without replacing the last accepted artefact.

## 5. Delivery gate

- [ ] Record intended recipients, channel and schedule separately. Activation/sending requires explicit approval. If not approved, mark export acceptance complete only where proved and leave unattended delivery open.

## Acceptance

- [ ] Full bibliography and monthly artefacts must reconcile to the model by key and field, not file existence, size or row count alone. Store native action/refresh correlation and actual output hashes privately.

## Checkpoint

Run `python3 scripts/agent_harness.py check --task all` for local changes. Record task, outcome, command/exit code, target/version correlation privately, evidence path, rollback and remaining blocker. Never place tenant IDs in this file.
