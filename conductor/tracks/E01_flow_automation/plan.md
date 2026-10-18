# Implementation Plan: E01 Power Automate Ingestion Canonicalization and Recurrence Scheduling

## Parallel scope refinement — 13 October 2026

E01 retains the shared writer and native flow integration under the current object
owner. Follow the [parallel assignments](../../../docs/PLATFORM_COMPLETION_PLAN.md#parallel-delivery-assignments--13-october-2026).
Supporting chats prepare source-specific definitions against frozen inputs; they
must not rebuild the current import package, change connections/trigger state,
resubmit an uncertain run or refresh the shared model. E01-H02a integrates one
reviewed adapter at a time with the existing immutable staging/commit-last path,
exact native preimage, rollback and saved/run readback. Account recovery and
CURRENT_STATE remain with their recorded owner. No checkbox is closed by this
planning refinement; schedules and delivery retain their separate gates.

## Shared-data execution refinement — 13 October 2026

E01-H02a owns bootstrap/adaptation of the existing archive writer, durable raw staging and accepted commit-last integration. Preserve stable workflow identity, connections, batch/replay and prior state. The current publication/archive owner must hand off an overlapping object before another writer acts.

Use the [delivery contract](../../../docs/PLATFORM_COMPLETION_PLAN.md#shared-data-delivery-contract--13-october-2026) for the bounded implementation sequence, permission matrix, CLI routes and cause-specific recovery. This refines existing tasks; historical checked phases do not close complete raw retention.


**Access scope:** current-user isolated/manual publication-flow operation only,
matching the existing publications development route. Recurrence, sharing and
organisation-wide binding are future extensions.

## Phase 1: Trigger & Nomenclature Canonicalization
- [x] Task 1.1: Refactor `config/flows/publication-registry-upsert.definition.json` to replace the manual button trigger with a 20:00 UTC (06:00 AEST) daily recurrence trigger.
- [x] Task 1.2: Update flow display name from `"CHHHS Publications - DEV manual ingestion validation"` to `"CHHHS Research Publications - Daily Ingestion & Enrichment"`.
- [x] Task 1.3: Update `config/flows/manifest.template.json` to enforce canonical naming across all root and child resource definitions.

## Phase 2: Package Build Automation
- [x] Task 2.1: Update `scripts/build_sharepoint_upsert_package.py` to bake recurrence trigger and canonical name directly into deployable zip files.
- [x] Task 2.2: Execute `python3 scripts/build_sharepoint_upsert_package.py` to generate `private/ops/flow-packages/sharepoint-upsert.zip`.
- [x] Task 2.3: Verify zip contents via inspection script to ensure definition and manifest integrity.

## Phase 3: Verification & Downstream Handshake
- [x] Task 3.1: Confirm timing alignment with Power BI dataset `{{ISOLATED_MODEL_ID}}` daily 07:00 AEST scheduled refresh.
- [x] Task 3.2: Confirm local validation contracts pass with zero errors (`validate_project.py` and `webfirst_contracts.py`).
## Reopened acceptance audit — 2026-09-20

Earlier checked tasks describe historical implementation. They do not close current operational acceptance.

- [ ] Verify remaining native execution, replay/readback and reconciliation against current private receipts.
- [ ] Record release and schedule status separately from local test/package completion.

## Phase 4: Local flow defect remediation
- [x] Separate the Power BI readiness summary query from the publication-row query consumed by the SharePoint upsert loop; add a nonblank `SourceKey` contract and regression test.
- [~] Re-deploy the corrected definition only to the approved isolated/manual route and capture create, replay/update, duplicate and failed-batch readback. The 2026-09-21 live retest proves corrected readiness/query/loop execution and SharePoint lookup; create/replay/update, duplicate, failed-batch, reconciliation and unattended-cycle evidence remain open.

## Phase: Live query retest evidence — 2026-09-21

- [x] Re-test the retained canonical DEV scheduled flow after the `DatasetExecuteQueriesError`; bounded `TOPN(100)`/`SELECTCOLUMNS` publication projection succeeded through the serial loop and SharePoint `Get items`.
- [x] Record the current run IDs and connector/list boundary in the ignored private receipt; retain the organisation-wide target, replay/update, duplicate, failed-batch, reconciliation and unattended-schedule gates as open.

## Phase: Conductor review — 2026-09-21

- [x] Review the corrected flow definition, builder, live retest evidence and local regression results; retain E01 as in progress because native operational acceptance is incomplete.

## Phase: Target-package hardening — 2026-09-21

- [x] Harden `load_target` to reject non-HTTPS site targets and empty or unresolved field mappings before package generation (`b6cc2e9`).
- [x] Add regression coverage for malformed site URLs and empty mappings; the latest local verification reports 374 tests with 8 skips.
- [x] Review fix: record the local builder/flow-contract execution evidence; native run/replay/schedule acceptance remains separately gated.
- [x] Add an exact-one-match update guard so duplicate publication keys cannot write (`22b5df1`).
- [x] Add a standalone publication-flow validator and CI gate alongside the grants-flow validator; retain native replay and schedule gates as open (`bcbee3f`).
- [x] Add regression coverage requiring both canonical flow validators to remain in the source-only CI workflow (`35ef830`).

## Phase: Conductor review recheck — 2026-09-22

- [x] Re-run the source-only validator, full local suite and Conductor checks
  from the clean canonical checkout.
- [~] Retry the QLD Health classic-designer null-date branch using an explicit
  current-item expression. The unsaved condition shell was rejected by the
  expression editor and the dynamic-content panel stalled; the browser tab was
  reloaded without saving. Native null/non-null create/update/readback remains
  open.
- [ ] Archive E01 only after native replay, failure-safe reconciliation and
  schedule/release evidence are terminal and independently read back.

## Phase: Conductor review fix — 2026-09-22

- [x] Enforce the specified daily 20:00 UTC recurrence and canonical manifest
  display name in the publication-flow validator, with regression coverage
  (`c614d43`). Native deployment and schedule acceptance remain open.

## Phase: Conductor review fix — target binding identity boundary — 2026-09-22

- [x] Reject surrounding whitespace in private SharePoint site/list/model identifiers and internal field mappings before publication package generation (`8638767`).
- [x] Verification: focused publication contract tests (23, 8 private-package cases skipped), full local suite, project checks (460), web-first contracts, Conductor validation and diff validation pass locally.
- [~] Native import, replay/update, duplicate/failure-safe reconciliation and schedule/release evidence remain open.
