# Plan: Author and save a native PBIX in the Windows VM

## Implementation
- [ ] 01. Run scripts/Inspect-PowerBI-Guest.ps1 read-only preflight. Verify the Windows build, memory, display, WebView2 and approved current regular Power BI Desktop installer; do not install the Report Server edition.
- [ ] 02. Obtain and install Desktop from Microsoft with owner approval. Do not change licensing or tenant access controls. Record the actual installed Desktop version and guest compatibility result.
- [ ] 03. Open the source PBIP in a short local path, or open a verified latest report/model export. Do not reopen the retired employment-derived PBIX as the release model. Native parse errors must be fixed rather than hidden.
- [ ] 04. Implement T11/T12/T13 operations locally when genuinely blocked in the web UI. Apply the same fixture/native-parity and zero/ambiguity/date tests; preserve successful web edits through an explicit source reconciliation.
- [ ] 05. Configure public-source credentials privately, refresh PubMed and DORA, verify exactly three pages and reconcile all exports. Remove fixture queries/caches before release.
- [ ] 06. Use Desktop Save As to write a new PBIX. Close and reopen that PBIX; verify the active data model, all visuals, refresh and the full register. A renamed ZIP, report-only thin PBIX, or PBIT does not satisfy this gate.
- [ ] 07. Run scripts/check_saved_pbix.py where applicable and record that binary/package checks supplement, not replace, native reopen/refresh evidence.
- [ ] 08. Publish/rebind to the existing Power BI workspace only after explicit approval and exact target/baseline checks. Return to T14 and T15 for exports, web verification and any monthly workflow. A VM does not solve tenant permission or export-policy restrictions.

## Review and completion
- [ ] Execute applicable automated checks and the separate native/tenant checks.
- [ ] Record defects, fixes, precise evidence references and remaining blockers in review.md.
- [ ] Update metadata and track register; commit local changes without claiming unperformed external actions.

## Current state
Conditional only. Existing native-acceptance work is consolidated here; a working web report does not need this track.
