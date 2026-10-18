# Plan: Replace the underlying model, not just its labels

## Implementation
- [x] 01. Review the current six-table TMDL/snapshot as an initial schema, not verified runtime truth. Keep Publication, Facility, PublicationFacility, Date, SearchAudit and ReportingWindow unless a contract revision documents a necessary replacement.
- [x] 02. Load canonical publications and provenance. Define stable keys, correct types, Date relationships and unambiguous filter propagation. Test multiple facilities against a single canonical publication.
- [x] 03. Use DISTINCTCOUNT(Publication[CanonicalKey]) for canonical records, not DISTINCTCOUNT(PMID), which loses DORA-only items. Clearly identify unresolved possible duplicates so the headline is not misrepresented as a proven unique-paper census.
- [x] 04. Implement reporting-month bounds in Australia/Brisbane, previous complete month by default. Keep year-only, unknown-month and uncorroborated RSS dates out of monthly attribution; surface unallocated records separately within reconciliation.
- [x] 05. Compile and evaluate every DAX expression natively, including empty contexts. Rebind every visual/filter after field changes; browser renaming is not assumed to update downstream visuals.
- [x] 06. Remove old Employee/EmplID/Gender/Ethnicity/hiring/separation table fields, measures, partitions, parameters, connections, hidden tables, old filters/bookmarks and unused employment query tabs. Scan metadata rather than banning those words from legitimate publication titles.
- [x] 07. Read back the complete model/relationships/expressions from the actual development target. Regenerate source-controlled definitions and update frozen manifests only for reviewed changes. Do not overwrite external edits.
- [x] 08. Compare native DAX results with independent canonical-key and source-set counts before and after rebind; test DORA-only records, filters and an empty month.

## Power Platform native implementation (2026-09-13)

See [native architecture and licence fallbacks](../../../docs/POWER_PLATFORM_NATIVE_PLAN.md).

- [x] Implement native M/DAX over frozen validated source batches; prove the standard dataset-query route and prevent circular unversioned register updates. Preserve full canonical metadata and uncertainty.

## Review and completion
- [x] Execute applicable automated checks and the separate native/tenant checks.
- [x] Record defects, fixes, precise evidence references and remaining blockers in review.md.
- [x] Update metadata and track register; commit local changes without claiming unperformed external actions.

## Current state
Research semantic model complete and validated. M/DAX expressions, canonical key reconciliation, and multi-source enrichment (OpenAlex, Crossref, Dimensions, Scopus, WoS, ARDC) are frozen into the drift-detection baseline. Native count check and readback evidence are documented in review.md.
