# Reconciliation gap analysis — 2026-09-12

Scope: existing report, linked semantic model, separate Research model, development-folder preview and Git HEAD `88a1d74`. This is an observed comparison and implementation proposal, not native acceptance. Exact identities and observations are recorded in ignored `private/ops/2026-09-12-discovery.json`; operation status is in `private/ops/capabilities.json`.

Update: the ZIP and standalone README have now been downloaded and reviewed. [Package review](DEVELOPMENT_PACKAGE_REVIEW.md) records verified hashes, tests, the exact README difference and collector defects. This supersedes the initial preview-only and download-pending observations below.

## Asset reconciliation

| Asset | Evidence | Disposition |
|---|---|---|
| Existing report | Open semantic model resolves its actual workforce model. All four pages were inspected for visual descriptions. | Preserve original. Publication labels do not make its workforce measures valid research metrics. |
| Linked model | Nine tables; Employee hidden, 41 columns shown in model card; eight many-to-one relationships. Import storage observed on Employee. | Replace bindings in isolated development; do not rename these fields into publication concepts. |
| Separate Research model | Different ID; Query table marked empty; pre-existing TMDL script contains a PubMed search. | It is not the report's current model. Do not apply or discard its existing script or assume it is a safe development target. |
| Standalone development README | Full rendered text inspected; describes storage/registry/release architecture and incomplete deployment. | Design input requiring reconciliation with Git, not evidence that its acceptance tests or deployment ran. |
| Development ZIP | Preview lists six files: source-config.json, README.md, validation.json, registry-schema.sql, test_collector.py, collect_pubmed.py. | Contents and hashes pending receipt of downloaded file. Do not execute downloaded code before review. |
| README versions | Standalone displayed size 4.69 KB; ZIP member displayed size 5.25 KB. | Treat as potentially different revisions; do not assume byte equivalence. |
| Git | Local M/DAX/report definitions, Python reference/export code and contracts. | Locally validated baseline with known source defects; no evidence it was applied to the live report. |

## Outcome gaps

| Area | Git baseline | Development README / live observation | Required next work |
|---|---|---|---|
| Publication identity | Python and M auto-merge a unique normalized title/year match; keys derive from PMID or DORA URL. | README requires stable IDs after enrichment, exact identifiers, contradiction quarantine and title-only review. | Review ZIP registry schema and collector; choose one persistent identity contract and implement conflict/enrichment regression cases in T11. |
| Ingestion | PubMed ESearch plus ESummary; fails above 10,000 results. | README specifies EFetch, date-window splitting, shared rate limits, restart receipts and affiliation capture. | Compare actual collector implementation with its claims before adoption; preserve returned-ID reconciliation. |
| DORA | Finite RSS feed, no durable registry write-back; feed dates used as publication dates. | README proposes public metadata exports; says no complete export/API is verified. | Inspect a real export before writing an adapter. Preserve absent-source and date uncertainty; do not count missing DORA as zero. |
| Review and inclusion | Affiliation-search match is a candidate; persistent inclusion/exclusion workflow is absent from inspected reference code. | README separates ingestion from needs_review/included/excluded decisions. | Persist decisions independently; expose candidate counts separately from included publication counts. |
| Releases | Direct source refresh into M model; local export guards exist. | README requires a single selected immutable reporting release and last-good retention. | Agree a release-to-model adapter and failure behavior after schema review. Never combine every historical release. |
| Time | Local date precision and Brisbane boundaries exist, but DORA date defect remains. | README separates publication, first seen, modified and collected times; backfill differs from monthly discovery. | Keep these concepts distinct in schema, measures and export snapshots. |
| Pages | Contract: CHHHS Publications, Monthly Publications, Source Reconciliation. | Live: Monthly Research, Research Portfolio, Clinical Trials & Evidence, hidden Publication Tooltip. | Build the three contract pages in isolated development; explicitly remove legacy tooltip dependencies from the candidate. |
| Visuals | Research-native source definitions exist locally. | Monthly page uses New Hires; portfolio uses employee changes; clinical page uses Bad hires; hidden tooltip uses Separations. | Rebind every visual, filter, tooltip and bookmark to research semantics; title changes are insufficient. |
| Recovery | Contract requires recoverable baseline and separate development model. | Original model says version history unavailable because it has not been edited online. | Obtain a recoverable original checkpoint outside any workforce-row import into Git; verify recovery before writes. Do not edit original merely to create history. |
| Refresh | Local validation does not certify live execution. | No scheduled/OneDrive history rows shown; no suitable gateway or cloud connections; schedule off/disabled, UTC. | Treat current data as unverified cached baseline. Configure candidate sources only after isolation; verify native refresh separately. Schedule activation remains gated. |
| Permissions | Previously unknown. | Linked model direct access lists owner account as workspace admin; one related report; no related-item access or report links listed. | These support read/authoring investigation, not proof of a complete tenant-wide consumer inventory or isolation. |

## Authoring route

Use the installed Microsoft Power BI browser workflow and ordinary Service UI. Report editing and Save are exposed. Model opens in Viewing mode, offers Editing in its mode menu, and explicitly disables Get data, Transform data and New measure in Viewing mode. No original-model Editing transition or write probe was performed. Refresh and download/version-history actions are exposed, but refresh success, recovery and export completeness remain unverified.

Missing dedicated MCP write schemas do not establish a web limitation. T16/T17 remain inactive. The separate Research model and its unsaved script must be preserved while the development target is resolved.

## Proposed implementation sequence

1. Receive the ZIP locally, record SHA-256 and member hashes, review code as data, compare its README with the standalone revision, and reconcile its schema/config/tests with Git. Do not infer implementation from filenames or validation.json.
2. Complete T08: exact tenant identity, remaining fields/expressions/filters/bookmarks, model settings and per-operation route. Avoid extracting embedded employee records when inspecting M.
3. Complete T10 recovery and isolation. Prefer a separate restricted development report/model in the existing workspace, sourced from reviewed research definitions. Prove distinct IDs and binding. Keep the original and separate Research model unchanged. A report-only copy is insufficient.
4. Run a reversible canary against the isolated candidate; save, reopen, verify and roll back. Verify report and semantic-model persistence independently, followed by Power Query capability.
5. Implement T11–T14 against the reconciled contract: ingestion/identity/review, research model, three pages, full canonical bibliography and monthly snapshots. Run native M/DAX and complete key-set reconciliations in addition to local tests.
6. T15 live acceptance remains distinct from production rebind, publishing and scheduled delivery. Present the verified candidate and exact intended effect before any separately gated action.

## Current boundaries

The initial download-path issue is resolved: normal SharePoint download controls produced local ZIP and README files, now preserved in ignored repository storage. No access to the blocked Chrome download-manager page was needed. Package hashes and contents have been reviewed; adoption/hardening and the release adapter remain open.

No original or development model/report writes, source refresh, sharing changes, schedule activation or VM changes were performed. Browsing restored the report's initial Clinical Trials & Evidence selection and preserved the separate Research script.
