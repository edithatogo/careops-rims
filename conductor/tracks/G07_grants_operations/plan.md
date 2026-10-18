# Implementation plan

**Access scope:** current-user manual operation against isolated DEV data; no
cross-user monitoring, delivery or unattended schedule is part of this tranche.

- [x] Record scope and acceptance requirements.
- [x] Inspect current inputs, dependencies and relevant platform objects. Reused G04 source health and G01 stable keys; no operational tenant object was changed.
- [x] Implement: Add a local fail-closed run evaluator for empty/duplicate/key-missing/failed-source batches and last-accepted preservation.
- [~] Verify: Local controlled-failure checks pass; one controlled native synthetic create and one same-key update are now evidenced with the flow restored Off. Current-user manual monitoring, concurrency and exact-key operational reconciliation remain open; cross-user delivery and unattended scheduling are future extensions.
- [x] Review fix: reject whitespace-divergent source and opportunity identity values before operational acceptance (`1ac3d52`).
- [x] Record local and live evidence separately before closure.

## Native operational readback refresh — 2026-09-22

- [x] Re-read the canonical QLD Health `CHHHS Research Grants - Reviewed
  Import Upsert` details page. It is the sole observed Grants flow, owner-only,
  SharePoint-connected, Off, with Flow Checker Errors 0 and the expected single
  inactive-flow warning. Two visible recent runs are succeeded/test-succeeded.
  Receipt: `private/ops/2026-09-22-powerautomate-g07-flow-readback.json`.
- [~] Keep duplicate/concurrency, failed-batch preservation, exact-key
  reconciliation and unattended monitoring/delivery open until independently
  read back.

### Native malformed-batch test boundary — 2026-09-22

- [x] Attempt the current-user manual test with `ReviewedRowsJson=not-json`.
  Power Automate opened the canonical flow's Run flow dialog but refused
  submission because the flow is Off; therefore no run was created and no
  SharePoint mutation occurred. The flow was not enabled and remains Off.
  Receipt: `private/ops/2026-09-22-powerautomate-g07-malformed-test-boundary.json`.
- [x] The pre-submit Off-state boundary was superseded by the bounded native
  execution recorded below; the earlier receipt remains historical evidence
  that no run was attempted while the flow was Off.

### Native malformed-batch execution — 2026-09-22

- [x] Execute the bounded current-user cycle against the canonical flow:
  temporarily enable, submit `ReviewedRowsJson=not-json`, read back the failed
  run and restore the flow Off. Run
  `08584115886238763797828484917CU13` failed at `Parse_Reviewed_Rows` with the
  expected invalid-JSON error before `Apply_to_each_Reviewed_Row`.
- [x] Read back the exact QLD Health personal `Grants Registry` REST endpoint;
  the response was an empty Atom feed, so no item was created or changed.
  Receipt: `private/ops/2026-09-22-powerautomate-g07-malformed-test.json`.
- [~] Duplicate/concurrency, exact-key operational reconciliation and
  unattended monitoring/delivery remain open; the flow is Off after the test.

### Native exact-key create/update cycle — 2026-09-22

- [x] Temporarily enable the canonical flow and submit one synthetic reviewed
  row with `OpportunityKey=SYNTH-G07-20260922`; the create run succeeded
  (`08584115882832862098741138474CU12`).
- [x] Submit the same key with an updated title, description, amount and hash;
  the update run succeeded (`08584115882008512967727243474CU27`) and native
  readback showed one item (ID 6, etag `"2"`) with the updated title.
- [x] Delete the exact synthetic item and read the full list back as an empty
  Atom feed; restore the flow Off. Receipt:
  `private/ops/2026-09-22-powerautomate-g07-exact-key-cycle.json`.
- [~] Duplicate/concurrency, unattended monitoring/delivery and production
  acceptance remain open; a single-key create/update cycle is not a substitute
  for those gates.

### Native official reviewed-row replay — 2026-09-22

- [x] Replay one reviewed Queensland opportunity using canonical key
  `metro-south-innovate-grants-2027`; run
  `08584115872127113780695944024CU04` succeeded and readback returned exactly
  one SharePoint item (ID 8).
- [x] Delete the exact row with HTTP 200, confirm an empty Atom feed and restore
  the canonical flow Off. Cross-track receipt:
  `private/ops/2026-09-22-powerautomate-g02-g04-metro-south-reviewed-row.json`.
- [~] Duplicate/concurrency, monitoring/delivery, recurrence and production
  acceptance remain open; this was a bounded manual reviewed-import cycle.

## Phase: Review fixes
- [x] Task: Apply review corrections for the controlled native replay and preserve the remaining acceptance boundary (0536b98).
- [x] Task: Reject runs without source health or with records from unreported sources (aad9d4a).
- [x] Task: Reject incomplete or duplicate source-health rows and records without source identity (2165c70).
- [x] Task: Reconcile non-negative per-source health counts to admitted record counts and reject mismatches (91345bf).
- [x] Task: Reject non-string source and opportunity identities without coercion, including unhashable malformed keys.
- [x] Task: Reject non-object run records and health rows without incidental exceptions (c174a3a).
- [x] Task: Add exact emitted-to-registry key-set reconciliation with fail-closed preservation (994dc05).
- [x] Task: Add selected-field registry readback reconciliation with fail-closed prior-batch preservation (`1b0c91b`).
- [x] Task: Reject string-shaped reconciliation field allowlists and canonicalize whitespace before comparison (`0eef31a`).

## Phase: Conductor review fix — reconciliation identity boundary — 2026-09-22

- [x] Task: Reject surrounding whitespace in emitted and registry `OpportunityKey` values during exact-key readback reconciliation instead of silently canonicalising them (`c60d492`).
- [x] Verification: focused relationship/operations tests (22), full local suite (452 tests, 8 skipped), project checks (460), web-first contracts, Conductor validation and diff validation pass locally.
- [~] Native duplicate/concurrency, operational monitoring, reconciliation readback, recurrence, delivery and production acceptance remain open.

## Phase: Conductor review fix — relationship identity boundary — 2026-09-22

- [x] Task: Reject surrounding whitespace in relationship identities, evidence
  URLs, confidence, award IDs and review states instead of silently trimming
  them (`2fad01c`).
- [x] Verification: focused relationship/operations tests (23), full local
  suite (465 tests, 8 skipped), project checks (460), web-first contracts,
  Conductor validation and diff validation pass locally.
- [~] Native duplicate/concurrency, operational monitoring, reconciliation
  readback, recurrence, delivery and production acceptance remain open.
