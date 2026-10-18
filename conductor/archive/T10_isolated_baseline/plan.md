# Plan: Protect the existing report and prove an isolated write

## Implementation
- [x] 01. Capture the original report/model definitions or available version-history checkpoints, settings and dependency inventory. Store hashes and IDs privately; do not copy old employment rows into Git or a third-party service.
- [x] 02. Prepare the smallest approved development report/model using existing workspace capabilities. Verify that the development model ID differs from the original and that the report is bound to it. Never infer that Save a copy duplicates the model.
- [x] 03. If isolation cannot be created, stop model writes. Offer a precise owner/admin task rather than modifying a shared production model or taking ownership. (Isolation successfully established in development copy {{ISOLATED_MODEL_ID}}).
- [x] 04. Record the last-observed model/report version or definition hash and check it immediately before each change. Stop on concurrent edits.
- [x] 05. Perform one reversible canary write on the isolated target, save/apply, reopen/read back, then undo it and verify rollback. For example, use a temporary development-only measure; remove it before acceptance.
- [x] 06. Record exact tool invocation or UI steps, target IDs, before/after values, timestamps, rollback evidence and read-back result. Only then mark write capabilities verified.

## Power Platform native implementation (2026-09-13)

See [native architecture and licence fallbacks](../../../docs/POWER_PLATFORM_NATIVE_PLAN.md).

- [x] Remove obsolete persisted SQL dependencies only in the protected isolated model; prove cloud-native source execution and rollback. Persisted removal, ReportingWindow and live DORA cloud save/load/readback are verified. The protected baseline is retained; restoring this broader removal has not been exercised. Full source/model acceptance remains open. See docs/PROTECTED_DEVELOPMENT_BASELINE.md.

## Review and completion
- [x] Execute applicable automated checks and the separate native/tenant checks.
- [x] Record defects, fixes, precise evidence references and remaining blockers in review.md.
- [x] Update metadata and track register; commit local changes without claiming unperformed external actions.

## Current state
Verified protected development baseline active on development model {{ISOLATED_MODEL_ID}}. Isolation, canary writes and rollbacks completed.

## Verified protected development baseline, 2026-09-12

Original PBIX downloaded outside the repository, hashed and ZIP-checked; imported under a distinct development name. New model/report IDs and exclusive related-content binding verified. Model measure and report-page rename canaries each persisted after reload and were rolled back with another reload. Private evidence: `private/ops/original-pbix-backup.json` and `private/ops/isolated-baseline-observation.json`. Power BI automatically converted only the development model to large-model format and enabled version history. No original model/report changes occurred.
