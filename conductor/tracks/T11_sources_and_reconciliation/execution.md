# Detailed execution: T11_sources_and_reconciliation

This runbook refines the existing plan; it does not reset completed historical work or establish new live evidence. Execute each unchecked applicable task below and mirror its outcome into the owning plan. Read [stabilisation protocol](../../PUBLICATION_STABILISATION.md) first.

## Inputs

powerquery/CanonicalPublications.m; config/native-ingestion-storage-check.dax; config/native-canonical-check.dax; tests/native/; docs/DYNAMIC_UPDATE_IMPLEMENTATION.md; current track plan and private receipt references.

## 1. Restore current context

- [ ] Read metadata/spec/plan and prior receipts. Discover the existing isolated model and its consumers through supported controls. Compare target identity and revision with the rollback checkpoint. Refresh stale authentication through normal login only.

## 2. Establish independent baselines

- [ ] Capture source keys, canonical keys, metadata chunk integrity, date uncertainty and current committed batch IDs before editing. Counts alone cannot prove equality; retain key-set hashes and exact differences privately.

## 3. Verify native retention

- [ ] Run prepared native retention/parser cases in isolation. Test a smaller DORA feed, missing page, interrupted commit, duplicate page, older observation and replay. Expected: preserve historical records and reviews; reject incomplete batches; no synthetic rows in reporting tables.

## 4. Complete integration

- [ ] Connect reporting readers to the last accepted committed history in the isolated model. Apply one change at a time with readback. Trigger one manual refresh, correlate its actual run ID to terminal completion, then repeat storage/key checks.

## 5. Second live cycle

- [ ] Perform a subsequent permitted live collection and replay. Demonstrate stable identities/first-observed dates, updated last-observed dates, retained absent records and an explained canonical-key delta. A timestamp change alone fails.

## Acceptance

- [ ] Every remaining T11 checkbox needs a linked current receipt. If any source fails, preserve the last accepted batch and leave the failed gate unchecked. Record rollback route; remove only positively identified isolated fixtures after testing.

## Checkpoint

Run `python3 scripts/agent_harness.py check --task all` for local changes. Record task, outcome, command/exit code, target/version correlation privately, evidence path, rollback and remaining blocker. Never place tenant IDs in this file.
