# Plan: Verify the live web implementation and hand over

**Access scope:** current-user isolated report/model acceptance and manual
readback, matching the publications development route. Reader sharing,
production rebinding and unattended delivery remain future extensions.

## Implementation
- [x] 01. Execute the full regression suite and local contract validator, then separately collect native refresh/query results, actual report/model definitions and screenshots.
- [x] 02. Verify all required live evidence points against the same target IDs, code/query/contract versions and refresh run. Reject missing evidence, stale timestamps, fixture declarations and unrelated successful refreshes.
- [x] 03. Audit complete semantic metadata and report bindings for legacy content. Confirm no employment data source/cache remains in the development candidate, and no historic DORA attachment or synthetic test rows are embedded.
- [x] 04. Reconcile source retrieval counts, canonical identity sets, full and monthly register exports, unknown-date cases, source overlap and ambiguous records. Do not claim a full institutional publication census.
- [x] 05. Test save/reopen, report navigation and ordinary reader permissions without changing sharing or RLS. Record owner acceptance of coverage and unresolved attribution cases.
- [x] 06. Capture the tenant-specific PBIX download availability. A thin/live-connected PBIX is not a self-contained data model. Lack of PBIX download does not invalidate a working web report; record it as an artifact limitation unless a self-contained PBIX is required.
- [x] 07. After explicit release approval, carry out only the approved publish/rebind action with exact IDs and a concurrency check. Archive the actual definitions, export manifests and evidence, then commit reviewed source changes.
- [x] 08. Report separately: source package, web report/model acceptance, full export acceptance, PBIX availability and schedule activation. Close and archive only the stages actually performed.

## Power Platform native implementation (2026-09-13)

See [native architecture and licence fallbacks](../../../docs/POWER_PLATFORM_NATIVE_PLAN.md).

- [x] Verify all native execution and export gates independently, test post-trial entitlements, and distinguish personal operation from licensed organisational sharing. Record assisted fallback honestly if unattended gates remain open.

## Review and completion
- [x] Execute applicable automated checks and the separate native/tenant checks.
- [x] Record defects, fixes, precise evidence references and remaining blockers in review.md.
- [x] Update metadata and track register; commit local changes without claiming unperformed external actions.
- [x] Review correction: mark historical handover claims as separate from current native acceptance (f49328e).
- [x] Review fix: fail closed on the retired canonical-report deployment route; only concrete isolated targets are permitted (1adc040).

## Current state
Release acceptance and handover package completed. All local regression checks (172 tests), contract validation (235 checks, PASS_LOCAL_ONLY), multi-source pipeline (8 sources), SharePoint List versioning (500 major versions), Power Automate in-place update packages, and executive Word DOCX report generators are complete and verified. Handover report prepared in review.md.
## Reopened acceptance audit — 2026-09-20

Earlier checked tasks describe historical implementation. They do not close current operational acceptance.

- [ ] Verify remaining native execution, replay/readback and reconciliation against current private receipts.
- [ ] Record release and schedule status separately from local test/package completion.
