# T17_desktop_fallback_acceptance: Author and save a native PBIX in the Windows VM

## Outcome
Install the regular Power BI Desktop app, complete only the authoring operations that the web route could not perform, and validate a genuine native PBIX. Reuse the same data, report and export contracts.

## Dependencies
T16_utm_windows_fallback, T09_execution_contracts

## Acceptance criteria
- The regular Desktop app runs and the saved self-contained PBIX reopens successfully.
- Actual PubMed/DORA refresh and report rendering pass in the guest.
- The same source, publication, date, legacy-exclusion and export contracts pass.
- No unapproved publish/rebind/schedule action occurs.

## Evidence boundary
Conditional only. Existing native-acceptance work is consolidated here; a working web report does not need this track.

## Safety and scope
Read `conductor/workflow.md` and `contracts/web-first-execution.contract.json`. Preserve the existing report/model until an approved, isolated write path and rollback are proven. Do not require Fabric Git integration, capacity purchase, public publishing or a new repository. Do not enter or expose credentials in Git or this pack.
