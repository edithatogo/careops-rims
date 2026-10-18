# Plan: Reconcile context and implement the execution gates

## Implementation
- [x] 01. Preserve v0.3.0-rc1 Git history and record its SHA256. Retain legacy audits separately from runtime assets.
- [x] 02. Resolve stale four-page/PMID-only project guidance in favour of three publication pages and CanonicalKey counting.
- [x] 03. Supersede the Fabric Git deployment track. Make native Desktop acceptance conditional, not a prerequisite for a working web report.
- [x] 04. Create T08–T17 specifications, plans, metadata and per-track plugin prompts, with dependency and completion evidence rules.
- [x] 05. Implement testable route, isolation, snapshot, export and fallback policy checks. Unknown capabilities, shared model copies, incomplete exports and unverified live assertions must not pass.
- [x] 06. Provide an all-publications CSV and print-ready HTML exporter, using only clearly labelled synthetic data for testing. Preserve complete authors/titles and validate canonical identity counts.
- [x] 07. Create a frozen local definition baseline, a stricter target outcomes/export contract and a live evidence template. Keep unresolved runtime defects explicitly open.
- [x] 08. Run original and new tests, review the work, commit it, and verify an independently extracted release package.

## Review and completion
- [x] Execute applicable local checks. Native/tenant checks are outside this local track and remain open in T08/T10–T15.
- [x] Record defects, fixes, precise evidence references and remaining blockers in review.md.
- [x] Update metadata and track register; commit local changes without claiming unperformed external actions.

## Current state
Local implementation scope only; the current M/DAX definitions remain a source baseline awaiting runtime remediation and native execution.

## Implementation commits
- `b9550ac`: track context, specifications, plans and handoff.
- `3600ced`: executable policy gates, full bibliography renderer and tests.
- `affafc9`: cross-platform export hash correction.

Independent pre-release extraction: `audit/webfirst-extraction-verification.json`. Final archive identity is recorded in the external release receipt.
