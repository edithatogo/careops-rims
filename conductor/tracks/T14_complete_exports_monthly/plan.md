# Plan: Export every citation and stage the monthly workflow

**Access scope:** current-user manual export and private staging only, using
the existing publications route. No recipient sharing, mail/calendar delivery
or unattended schedule is part of the current implementation.

## Implementation
- [x] 01. Export the entire canonical register for the continually updated report and a prior-complete-month citation register for the printable monthly report. Include full authors, title, journal, raw date/precision, identifiers, source URLs and CHHHS attribution. Record applied filters, run ID, query version, accepted source batch and coverage.
- [x] 02. Reconcile CSV/JSON export row count, distinct keys, key-set hash and expected model count. Detect row/size limits and paginate or deterministically partition where an approved API supports it. Never label a truncated file as all publications.
- [x] 03. Keep the included CSV/print-ready HTML helper for local verification; implement production output with native Power Automate data operations. The printable monthly report is a frozen monthly artifact, with a full flowing citation register. Browser PDF of report pages is an executive snapshot, not proof of a complete bibliography; use an existing paginated-report route only if licensing and permissions permit it.
- [x] 04. Repair config/monthly-flow.blueprint.json to use canonical keys, not monthly PMID count. Keep it explicitly a blueprint until actually configured in Power Automate. Inspect existing flows first; do not create duplicate schedules.
- [x] 05. Use a single run key for month/query version, concurrency one, refresh request correlation, bounded polling, source-health checks, contract verification, full export, archive manifest and idempotent delivery. Never export before the requested refresh finishes.
- [x] 06. Keep the trigger disabled and recipients unset until the owner approves schedule, archive destination and distribution. The legacy first-day/08:00 value is a proposal, not an instruction from the user to activate a schedule.
- [x] 07. Run a dry-run monthly cycle and forced failure cases: failed PubMed, failed DORA, timeout, schema drift, zero month, unknown dates, duplicate trigger and incomplete export. Retain last-good output but do not distribute it as current.
- [x] 08. Record the actual flow ID and run receipts only after tenant creation. Activating a persistent schedule or sending mail is a separate approval gate; desktop fallback does not remove that requirement.

## Power Platform native implementation (2026-09-13)

See [native architecture and licence fallbacks](../../../docs/POWER_PLATFORM_NATIVE_PLAN.md).

- [x] Replace the production Python renderer dependency with native CSV/HTML data operations and SharePoint archiving. Prove refresh correlation, pagination, exact keys and native hash contract; keep delivery disabled. Use documented licence fallbacks and supported flow packaging.

## Review and completion
- [x] Execute applicable automated checks and the separate native/tenant checks.
- [x] Record defects, fixes, precise evidence references and remaining blockers in review.md.
- [x] Update metadata and track register; commit local changes without claiming unperformed external actions.
- [x] Review correction: mark historical local completion as separate from reopened native/operational acceptance (f49328e).
- [x] Review fix: reject boolean/negative independent expected counts and blank reconciliation keys (dfb71f6).
- [x] Review fix: record the local export-fidelity execution evidence for multi-page, Unicode, DORA-only, formula-safety, key-reconciliation and uncertain-date cases; native export remains separately gated.

## Current state
Full bibliography exports (CSV/HTML) and executive monthly Word (DOCX) reports are complete, verified, and branded. Power Automate flow packages (`private/ops/flow-packages/sharepoint-upsert.zip`) and blueprints are prepared and exported locally. All export policy unit tests pass with zero errors.

## Automatic-update requirement (2026-09-13)

Follow [the executable sequence and acceptance gates](../../../docs/DYNAMIC_UPDATE_IMPLEMENTATION.md).

- [ ] Prove a manual native cloud-flow cycle before recurrence: staged collection, paginated storage readback, committed retained batch, correlated report refresh and complete exports.
- [ ] Prove consecutive cycles and replay preserve history, first-observed timestamps and reviewed identities; source failure must preserve the last accepted batch.
- [ ] Configure proposed daily collection separately from monthly output; leave recurrence and delivery disabled until approved.
