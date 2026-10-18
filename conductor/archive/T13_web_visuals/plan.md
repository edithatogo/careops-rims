# Plan: Implement the live register and printable monthly report

## Product boundary

Deliver two reader-facing report products from the same isolated semantic model:

- **CHHHS Publications** is the continually updated report. It includes the publication register and its supporting Source Reconciliation page so that current coverage, provenance and unresolved records remain visible.
- **Monthly Publications** is a printable report for the previous complete Brisbane calendar month. Its data is frozen to the accepted monthly run and must show the reporting month, accepted batch, refresh time and query version. It is not a live rolling page after that run is accepted.

The existing PBIR stays at exactly three pages: CHHHS Publications, Monthly Publications and Source Reconciliation. This avoids duplicating semantic models while keeping the two reader-facing products distinct.

## Implementation
- [x] 01. Use exactly CHHHS Publications, Monthly Publications and Source Reconciliation. Internal page names may differ in the existing service item only through an explicit one-to-one ID mapping; no unexpected hidden page is allowed.
- [x] 02. Implement **CHHHS Publications** as the live report: canonical count, source coverage, a clearly labelled as-of timestamp, useful year/facility/source filters and a full scrollable publication register. Retain unknown dates and missing PMIDs.
- [x] 03. Implement **Monthly Publications** as the printable prior-month report: fixed Brisbane reporting-month basis, accepted batch/run identity, source-health note, complete flowing citation list and print-safe layout. It must not silently move to a newer month when a reader reopens it. A zero-month report must say zero rather than show stale data.
- [x] 04. Implement Source Reconciliation: PubMed-only/DORA-only/both, ambiguity/attribution evidence, source failures/query warnings, date precision and coverage gaps. Put operational warnings here, not in invented research impact metrics.
- [x] 05. Keep complete titles/authors accessible through the register or detail interaction and use working PubMed, DOI and DORA links. Do not add unrequested clinical recommendations, citation scores, workforce visuals or AI summaries.
- [x] 06. Apply changes one page or visual at a time; read back field bindings and filters after each save. Use an explicit visual map from the existing source baseline; review only necessary schema-driven layout changes.
- [x] 07. Test on the browser viewport for readable typography, contrast, keyboard navigation, labels, nulls, long citations and no clipping. Capture one evidence image per page and verify the rendered data matches native query output.
- [x] 08. Reopen both products in a new session. Confirm live-report refresh state persists independently of the saved printable monthly run; confirm page order, interactions, filters and the frozen month/run identity persist. Replace any incidental canary visual; do not publish the development report yet.

## Review and completion
- [x] Execute applicable automated checks and the separate native/tenant checks.
- [x] Record defects, fixes, precise evidence references and remaining blockers in review.md.
- [x] Update metadata and track register; commit local changes without claiming unperformed external actions.

## Current state
Three-page report structure verified and complete. 36 research-only visuals mapped across CHHHS Publications, Monthly Publications, and Source Reconciliation. All residual legacy Employee pods removed. PBIR-Legacy definition generated at `private/ops/report-definition-updated.json`.
