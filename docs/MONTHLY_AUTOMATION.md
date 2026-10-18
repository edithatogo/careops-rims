# Monthly orchestration: native implementation, not deployed

The implementation blueprint is `config/monthly-flow.blueprint.json` (v2.1). It is not an importable Power Platform solution. The default route uses standard connectors and built-in data operations under the observed Office 365 rights; see [licence decisions and fallbacks](POWER_PLATFORM_NATIVE_PLAN.md).

## Runtime sequence

1. Keep the proposed monthly trigger disabled. Acquire a durable run record keyed by month/query version and accepted source batch, with concurrency one and duplicate-run protection. This record is the identity of the frozen printable monthly report.
2. Retain source observations and review decisions in approved SharePoint storage. Freeze a validated source batch before the final model refresh; never reset first-observed dates or treat finite RSS coverage as complete history.
3. Request refresh and prove completion of that exact run. Verify batch marker, reporting window and source health. A successful request, fixed delay or older successful refresh is insufficient. If standard actions cannot establish correlation, require manual verification and leave unattended acceptance open.
4. Extract the complete canonical register and the selected-month register. Reconcile independent model counts, distinct CanonicalKey sets and the required hash; PMID counts omit DORA-only records. Deterministic pagination must respect query row/value/byte limits.
5. Use Select, Create CSV table and Create HTML table to produce full flowing citations; archive the files plus source coverage, filters, date precision, query version and run/batch identifiers in the approved SharePoint library. Python helpers are local verification tools only.
6. Require separate approval for archive destination, recipients and schedule activation. Record delivery receipts and reconcile ambiguous send outcomes before retrying. Never distribute stale output as current.

## Configuration and open gates

Configure approved connections, workspace/model/report identity, SharePoint site/library, optional NCBI contact and reviewer privately. Confirm DLP, service access, standard dataset-query execution, exact refresh correlation, complete RSS metadata and a supported native hash implementation before deployment. Full author/title fields must not be truncated. Exact attribution evidence is required by the export contract; the current native model does not yet expose that field, so its export acceptance remains open.

The full and monthly register queries now contain all 18 export fields. Use the new `*-register-page.dax` templates for bounded extraction, `*-keys-page.dax` for independent key extraction and `export-counts.dax` for counts before/after extraction. These are authored DAX, not native-executed evidence.

Proposed timing remains day 1, 08:00 Brisbane (UTC+10), reporting the previous complete Brisbane calendar month. No trigger is enabled and no recipients are configured. Publication-date month and first-observed month are separate concepts; uncertain dates remain in the full bibliography without invented month attribution.

Power BI report PDF export is optional and capacity-dependent; PPU alone does not support ExportToFile. CSV/HTML are the default complete-bibliography formats. Solution-aware packaging is preferred only in an existing eligible Dataverse environment; ordinary cloud flows with documented configuration are the fallback. No Fabric migration is assumed.

## References

[Power BI connector](https://learn.microsoft.com/en-us/connectors/powerbi/), [dataset query requirements](https://learn.microsoft.com/en-us/rest/api/power-bi/datasets/execute-queries), [native data operations](https://learn.microsoft.com/en-us/power-automate/data-operations), [report export requirements](https://learn.microsoft.com/en-us/power-bi/developer/embedded/export-to), [NCBI guidance](https://www.ncbi.nlm.nih.gov/books/NBK25499/).

## 2026-09-13 implementation and remaining proof

The local CSV/HTML renderer now reopens both written files and compares every contract field against supplied input before committing output. HTML includes all 18 fields, with escaped text and complete metadata visible. This closes a local omission; it does not authenticate Power BI extraction. Tests include long Unicode, formula-like cells and same-key metadata loss. Python remains an offline verification/reference tool, not a hosted production dependency.

Native flow configuration:

1. Keep the trigger disabled. Freeze the source/review batch and acquire the unique run record. Persist request identity, target, request time and correlation evidence privately.
2. The standard connector documents Refresh a dataset but no refresh-history action. A successful refresh action is not completion. With an independently approved/licensed supported history route, require the exact request ID, Completed status and end time, then compare the loaded batch. Otherwise require manual correlated history verification. No reliable correlation means stop; do not poll by fixed delay and assume success.
3. Run export-counts.dax. Run each page template separately with include-null values enabled. Start AfterKey empty; set it to the last accepted key, escaping double quotes by doubling them. Start PageSize at 100. Reject error payloads at every response level even under HTTP 200. Reduce page size on size errors; if one record cannot fit, stop for a lossless chunk route. Never accept truncated content.
4. Continue until an accepted empty page. Independently paginate keys, reject duplicates/non-progress and compare exact sets and counts. Read counts and the model batch again; any change invalidates the export. A matching timestamp alone does not establish a frozen source batch or exact refresh identity.
5. Use native Select with explicit mappings for every export field, then Create CSV table/Create HTML table with explicit column ordering. Preserve complete text; apply spreadsheet formula protection before CSV and HTML escaping before any manually assembled HTML. Include scope, period, batch and coverage in the HTML wrapper and manifest. Treat nulls consistently as empty output cells, not omitted columns.
6. Write CSV/HTML into a pending batch folder in approved SharePoint storage, read them back, and compare fields as well as canonical keys. Publish a committed manifest only after all checks and the existing SHA-256 key-set contract pass. Do not invent an unsupported native hash expression. The native hash and full-file readback implementation still require proof; unattended acceptance remains blocked until then.

Current blocker: Power BI browser access was denied again by its admin-policy verification check. No flow was created, no live refresh was verified and no live export completeness claim is made. Native creation/run evidence and approval of scheduled delivery remain open.
