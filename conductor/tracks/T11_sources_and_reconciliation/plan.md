# Plan: Repair and prove PubMed plus DORA ingestion

## Connector-assisted next slices — 13 October 2026

Refine existing work through the [connector/source selection](../../../docs/FUTURE_SOURCE_ENRICHMENT.md#microsoft-connector-and-contextual-source-selection--13-october-2026),
without changing checkbox acceptance or current publication ownership. H03/H04
prepare approved internal project-register mappings via existing SharePoint/Excel
and maintain the separate DoRA activity access/retention gate. Directory/organisation
preparation uses exact-ID Office 365 Users and selected organisational registers,
with explicit fields, protected audience and existing author identity rules.
ABS geography supports a named accepted consumer with code/edition/period joins;
H05 reporting remains after source acceptance. Groups/RSS supply scoped supporting
evidence; optional iCite/Zenodo require a demonstrated enrichment gap.

First operation for any selected slice: read the existing exact target schema and
permission boundary, bind a frozen accepted input, prepare one disjoint Microsoft
mapping and return shared contract changes to the coordinator. No tenant-wide
people harvest, public-api proxy through SharePoint HTTP, paid service creation or
new report milestone. Native timeout/retry/paging/last-good behaviour must be accepted
on that source path; local OpenAlex evidence is not universal connector proof.

## OpenAlex bounded implementation checkpoint — 13 October 2026

User-authorised selected free credentials supersede the older blanket keyless
rule for supplied services; see [current policy](../../../docs/KEYLESS_ENRICHMENT_PLAN.md#current-free-credential-policy-and-failure-handling--13-october-2026).
Owned scope: `scripts/enrich_openalex.py`, `scripts/prepare_openalex_enrichment.py`
and `tests/test_openalex*.py`; supporting documentation only. Existing archive,
canonical consumer, native objects and CURRENT_STATE retain their current owner.

Local OpenAlex preparation now reads the external-provider credential from the
environment/Keychain, returns explicit failure outcomes, bounds retries, rejects
foreign identities/partial batches, preserves last-good fields/timestamps, and
retains complete raw responses in a new private candidate. Fifteen focused tests
pass. One accepted DoRA archive slice produced three successful live DOI matches,
with original input hashes and per-response byte hashes retained privately.

Exact next implementation dependency: publication owner accepts the canonical
consumer/register generation, then integrates this reviewed three-record candidate
through the existing Microsoft source/consumer path with secure connection binding
and scoped rollback. No deployment, flow activation, shared schema change or
T11-H01a/H02a native closure is claimed. OpenAIRE token-bearing Graph V3
connectivity is verified; routine token refresh and CORDIS extraction credentials
remain source-specific prerequisites, not reasons to rerun publication
acquisition or expand tests. Keep optional source expansion behind this first path.

## Parallel scope refinement — 13 October 2026

Follow the [separate-chat assignments](../../../docs/PLATFORM_COMPLETION_PLAN.md#parallel-delivery-assignments--13-october-2026).
H01a/H02a shared capture/archive/consumer changes remain with the publication and
integration owner. A projects/activity chat may prepare H03 field/privacy mapping
and the smallest H04 activity-only Microsoft consumer change using frozen inputs;
H03 access/retention must pass before real activity acquisition/import. H05 native
reporting follows accepted H04. No second archive writer or shared-model refresh.

Optional enrichment uses the [API coverage assessment](../../../docs/FUTURE_SOURCE_ENRICHMENT.md#free-api-coverage-review--13-october-2026):
first reuse current provider fields, then ROR/DataCite and Crossref update links;
OpenAIRE, OpenCitations, DOAJ and preprint APIs are selected only for demonstrated
gaps. Researcher preparation uses deposited ORCID and source-scoped author IDs;
ORCID direct access remains subject to its terms and the existing keyless policy.
Keep versions, retractions, affiliations and candidate identities distinct.
Return shared schema/identity changes to the coordinator; existing acceptance
checkboxes remain unchanged until the named native evidence exists.

## Shared-data execution refinement — 13 October 2026

T11-H01a owns complete response/schema capture before projection; T11-H02a owns accepted consumers. Reuse the publication owner's accepted source/archive evidence, then implement the next uncovered current-source field path. DoRA activity access/retention stays with T11-H03; its vertical stays with H04.

Use the [delivery contract](../../../docs/PLATFORM_COMPLETION_PLAN.md#shared-data-delivery-contract--13-october-2026) for the bounded implementation sequence, permission matrix, CLI routes and cause-specific recovery. This refines existing tasks; historical checked phases do not close complete raw retention.


**Access scope:** current-user isolated model/list and manual refresh/readback
only. Do not introduce shared storage, cross-user delivery or unattended
recurrence while implementing this plan.

## Implementation
- [x] 01. Preserve the user's Library search aliases, including HHS ampersand variants, CHHHS, Cairns Health Service District, Liz Plummer Cancer Care Centre, Tropical Public Health Services and Cairns Sexual Health Service. Reconcile them against config/facilities.json, retaining conservative extra facility searches.
- [x] 02. Compile each M function in the isolated web model. Validate all text-normalisation functions rather than assuming Python reference code proves M compatibility.
- [x] 03. Use fixed approved HTTPS source roots, RelativePath/Query construction, timeouts, bounded retries/backoff and NCBI rate limits. Allow anonymous access; keep any optional operational contact private. Batch metadata fetches; reconcile requested and returned identifiers; partition an over-limit search rather than silently truncating.
- [x] 04. Repair the zero-PubMed/positive-DORA and both-empty cases with explicit typed schemas rather than Record.FieldNames(PubMedRows{0}[Canonical]). Distinguish an unavailable source from a successful zero-result response.
- [x] 05. Parse the actual RSS structure defensively and retain DORA item URL, raw timestamp, author statement and attribution evidence. The supplied historical XML is design-only, never a seed for production data or a live test capture.
- [x] 06. Replace unconditional unique-title/year merging with exact PMID, then normalised DOI, then strict title/year/compatible-author evidence. Conflicting non-null identifiers must not merge. Missing metadata and multiple candidates remain separate review cases; record candidate keys and reasons.
- [x] 07. Preserve RawPublicationDate and DatePrecision. A DORA RSS 1 January timestamp is not evidence of an exact publication day or even month. Keep the raw feed date, mark precision unverified unless corroborated, and exclude unresolved month attribution from the monthly citation count while retaining the record in the full register.
- [x] 08. Implement durable retention of observed DORA-only records in an existing approved store, or explicitly leave the historical-coverage gate open. A refresh of a finite RSS window is not a full historical repository harvest. Do not adopt Dataverse or a new cloud resource without checking existing provision and approval.
- [x] 09. Separate PublishedInMonth from FirstObservedInMonth. Persist first-observed timestamps only in a durable upsert registry; seed/baseline records are not new publications. Record monthly query/run/source versions.
- [x] 10. Run fixture cases in native M and compare every field and source/identity count with expected results. Remove test queries and fixture connections from the production candidate, then perform a small live API probe and record a real response checksum privately.

## Power Platform native implementation (2026-09-13)

See [native architecture and licence fallbacks](../../../docs/POWER_PLATFORM_NATIVE_PLAN.md).

- [x] Implement durable SharePoint observations/review state, RSS metadata parity and the staged Power Query/standard-connector PubMed route. Prove stable batch IDs and first-observed dates; use the documented premium or assisted fallback if gates fail.
- [x] Configure and verify the [SharePoint retention specification](../../../docs/SHAREPOINT_RETENTION.md), including historical backfill, idempotent upserts and a smaller-feed rollover test. The existing private development OneDrive folder is accessible; historical ZIPs were uploaded. Register creation and automatic retention remain pending.

## Review and completion
- [x] Execute applicable automated checks and the separate native/tenant checks.
- [x] Record defects, fixes, precise evidence references and remaining blockers in review.md.
- [x] Update metadata and track register; commit local changes without claiming unperformed external actions.

## Current state (2026-09-14)
The isolated model's full ingestion refresh completed. Native staging contains 1,261 PubMed and 709 DORA records; these source counts are not canonical publication counts. The manual native flow stored all five source tables with exact page readback and before/after key reconciliation. Native metadata-structure checks passed. The stored archive is accessible through an authenticated SharePoint connection scoped to the approved folder.

Native Power Query reconstructed all stored metadata (32,289,819 PubMed and 2,603,915 DORA JSON characters) with exact archived publication-key parity. Ten isolated native tests passed for structured JSON, rollover, first-observation preservation and interrupted/malformed batches. The timed-out Power Query processing was cancelled. Corrected definitions were accepted through TMDL, the missing archive credential binding was repaired, and the manual data refresh completed. Loaded DAX confirms all ten tests and both full-metadata/payload-identity checks pass. The first accepted commit was written and read back exactly. Committed-history reader definitions were accepted, but reader execution and canonical/report integration remain pending.

## Next native validation
- [x] Read back completed ingestion refresh and source/chunk/key/encoding readiness.
- [x] Validate all stored PubMed/DORA metadata reconstruction in native Power Query.
- [x] Execute isolated native rollover and interrupted-batch reader tests (10 cases passed).
- [x] Confirm manual data refresh completes and loaded payload-identity checks pass; DAX view reads the deployed validation tables.
- [x] Write the first accepted commit only after recording refresh-generation correlation and complete metadata/key evidence; verify commit readback.
- [ ] Connect reporting queries to committed history and reconcile retained source keys and metadata after model refresh.
- [ ] Prove committed-batch replay and a subsequent live collection cycle; preserve institutional-scope and reviewed-identity decisions.

## Automatic-update requirement (2026-09-13)

Follow [the executable sequence and acceptance gates](../../../docs/DYNAMIC_UPDATE_IMPLEMENTATION.md).

- [ ] Prove a manual native cloud-flow cycle before recurrence: staged collection, paginated storage readback, committed retained batch, correlated report refresh and complete exports.
- [ ] Prove consecutive cycles and replay preserve history, first-observed timestamps and reviewed identities; source failure must preserve the last accepted batch.
- [ ] Configure proposed daily collection separately from monthly output; leave recurrence and delivery disabled until approved.

### Queensland Open Data DoRA activity coverage

- [x] 11. Confirm the linked Queensland Open Data DoRA dataset is project/activity data distinct from the DORA publication repository; record the current resource schema and entity boundary.
- [x] 12. Implement a CKAN package/resource discovery and paged datastore collector that fails closed on schema drift, incomplete pages, count mismatch or duplicate source `_id` values, while preserving all source columns and provenance.
- [x] 13. Implement a source-preserving RIMS export and machine-readable `DORA Activity Registry` schema. Keep contact/ethics fields in private or approved tenant storage only; do not add live rows to Git or publication fixtures.
- [x] 14. Create or update the isolated SharePoint target and read back every column and row key before any report-page or unattended-flow change. On 2026-09-21 the personal DEV `DORA Activity Registry` was created from the canonical schema with all 26 fields; REST readback confirmed field names, internal names, types, requiredness, identity uniqueness and indexing. A synthetic row populated every mapped field, read back all 26 fields and identity values, was deleted, and the API confirmed `ItemCount=0`. The current-user flow, native model table and a saved Clinical Analytics table visual are now read back; refresh, retained-history reconciliation and operational acceptance remain open.

## Local identity hardening — 2026-09-21

- [x] Reject boolean, structured and blank DoRA datastore `_id` values, and reject invalid expected record counts before reconciliation. Source identities are now limited to scalar string/integer values while the original source value remains preserved in the accepted row.
- [x] Add regression coverage for the scalar identity contract. Code commit: `12798092b64de6d420904c7cd77d589829076f1c`.
- [x] Native SharePoint schema/row readback is complete; the existing model now also has the native `DORA Activity Registry` table. Report integration and tenant operational acceptance remain separate gates.

## Native DORA Activity Registry bootstrap — 2026-09-21

- [x] Created exactly one isolated personal DEV `DORA Activity Registry` after site inventory found no existing list.
- [x] Created the remaining canonical fields through authenticated same-origin SharePoint REST, using `Text`, `Number`, `DateTime`, `URL` and `Note` types; the identity field is required, unique and indexed, and `DORARecordID`/`DORAResourceID` are required and indexed.
- [x] REST readback found all 26 canonical fields with the expected display names, internal names, types and requiredness. Versioning is enabled and `ItemCount=0`.
- [x] Controlled synthetic full-field round-trip created row ID 1, read back every mapped field and identity value, deleted the row, and confirmed post-cleanup `ItemCount=0`.
- [x] Import/read back the DoRA upsert flow and connect the current-user model projection. The flow was tested and restored Off; the native table is now saved in the existing model. A saved Clinical Analytics table visual reads back `DORAActivityKey`, `DORARecordID`, `DORAResourceID` and `DORASourceURL`. A permitted live/reviewed cycle, refresh/reconciliation and recurrence remain open; no row or recurrence was activated.

## Export provenance hardening — 2026-09-21

- [x] Reject coerced DoRA export provenance: `retrieved_count`, observation time,
  resource ID and resource URL must have the expected non-empty string/integer
  types; activity keys reject boolean or structured resource IDs.
- [x] Add regression coverage for malformed receipt provenance and resource IDs.
  Code commit: `93d2ac6b39914f8a91b4b8048862b7d88a2d5dd5`.
- [ ] Native SharePoint schema/row readback and report integration remain open;
  the local exporter contract does not certify tenant acceptance.

## Export URL and timestamp hardening — 2026-09-21

- [x] Require DoRA export provenance URLs to be valid HTTP(S) authorities and
  observation times to be timezone-aware ISO-8601 values.
- [x] Add regression coverage for unusable URLs and timezone-less timestamps.
  Code commit: `2c58a93977c93a8e4b963ae763b97034d3ea56c2`.
- [ ] Native SharePoint schema/row readback and report integration remain open;
  local provenance validation does not certify tenant acceptance.

## Export receipt reconciliation — 2026-09-21

- [x] Require `expected_count` and `retrieved_count` to be non-negative integers
  and equal before a DoRA export can be rendered.
- [x] Add regression coverage proving a partial receipt cannot cross the export
  boundary. Code commit: `df9abebf530567b9e0c5c058c3a09d11c8da5154`.
- [ ] Native SharePoint schema/row readback and report integration remain open;
  local receipt reconciliation does not certify tenant acceptance.

## Export receipt hash verification — 2026-09-21

- [x] Verify present `records_sha256` and `record_id_sha256` values against the
  canonical accepted records before rendering a DoRA export.
- [x] Add regression coverage for a valid receipt hash and a tampered record
  hash. Code commit: `bdb13036fec28d9f40f0d71725fb123a59297e04`.
- [ ] Native SharePoint schema/row readback and report integration remain open;
  local hash verification does not certify tenant acceptance.

## DoRA activity flow contract — 2026-09-21

- [x] Add the canonical local SharePoint-only DoRA Activity Registry upsert
  definition with serial writes, duplicate-key diagnostics, exact-zero/one
  guards and all 26 schema-field mappings.
- [x] Add a standalone validator, focused regression tests and a source-only CI
  gate. Code commit: `693027136610136c2ff443ecae26e21876ea56cc`.
- [x] Import to the approved isolated personal DEV target and read back every
  column and row key. The corrected package imported one current-user flow;
  two controlled manual runs proved create and same-key update, followed by
  SharePoint readback and cleanup to zero items. The flow is Off; Flow Checker
  reports 0 errors and 1 warning (off-flow only).
- [ ] Prove native retained-history/report integration, refresh and unattended
  operation. These remain separate acceptance gates; no production acceptance
  is claimed.

## DoRA private package bootstrap — 2026-09-21

- [x] Add a target-injecting private package builder that requires a concrete
  HTTPS site, GUID list/flow IDs and a named SharePoint connection.
- [x] Add package extraction/placeholder/connector regression tests. Code
  commit: `3c8edd17f30cce20c43e0cbc84eb38deb568e5c3`.
- [x] Generate and import the target-injected package to the approved isolated
  personal DEV target. The package remains ignored/private and the platform
  flow identifier is not tracked in Git.

## DoRA package post-injection validation — 2026-09-21

- [x] Validate the target-injected definition with the canonical DoRA flow
  validator before writing any package (`c9430cd`).
- [x] Add definition-drift regression coverage.
- [x] Native import and complete field/row-key readback completed through the
  isolated target; the flow was tested and returned to Off.
- [ ] Native retained-history/report integration, refresh and delivery remain
  open.

### Native DoRA flow import and controlled replay — 2026-09-21

The first package import was rejected by the native SharePoint connector because
display-name action parameters such as `item/Project ID` are not valid connector
internal names. The canonical definition and validator now map display names to
the SharePoint internal names (for example `Project_x0020_ID`). The rebuilt
package imported successfully as one new flow in the isolated personal DEV
environment. A manual create run and a same-key update run both succeeded; the
26-field row identity and updated values were read back through SharePoint REST.
The synthetic row was deleted and the list read back with `ItemCount=0`. The
flow was restored to Off. This proves the contract and controlled flow path,
not live DoRA ingestion, report binding, recurrence, notifications or release.

### Retained reporting projection in progress
Local parsers now reconstruct PubMed XML-shaped JSON and DORA field arrays without calling the live sources. A summary reader selects each retained source key from its latest committed batch, with exact page/key reconciliation. The first manifest must include PublicationTable and PublicationPageCount. Native parser parity, durable facility mappings, long-text export completeness and switching canonical consumers remain pending; these files are not yet deployed.

- [x] Add a local contract test preventing the isolated retained-history canonical partition patch from drifting into shared-model table creation (dd68606).
- [x] Add generator-level coverage for paged retention readback, exact keysets and staging-only output (4c33b40).

Seven isolated retained-summary reader cases are also prepared in tests/native/retained-summary-cases.m: smaller-batch retention, latest-version replacement, interrupted-batch exclusion, stable replay, and rejection of missing pages, wrong keys and duplicate files. Native execution remains pending alongside the eight parser cases.

### Committed reader verified after browser recovery
Native Power Query successfully executed the actual committed-history reader. Aggregate output: PubMed 1261 rows/1261 unique keys/32289819 metadata characters; DORA 709 rows/709 unique keys/2603915 metadata characters; one committed batch per source. Publication-level preview showed the baseline observation timestamp. The temporary aggregate edit was discarded. This verifies complete committed archive reading in native preview; processed table loading, parser parity, canonical/report consumption and subsequent-cycle tests remain pending.

### Native DORA Activity Registry model binding — 2026-09-22

- [x] Re-open the existing semantic model's native Power Query editor and verify the retained DoRA/history tables and authenticated organisational-account connection are present.
- [x] Add the personal `DORA Activity Registry` SharePoint Online list as a native query/table. The authenticated organisational connection accepted the QLD Health personal-site URL; the navigator then exposed the list, and Power Query created/saved the query with 48 columns and zero rows.
- [x] Record the prior bounded legacy-connector navigation failure as superseded evidence; the successful SharePoint Online List route is now authoritative for this model write.
- [x] Native activity-table binding and a current-user report visual are complete for the isolated current-user scope: model readback showed `DORA Activity Registry table 28 of 28` with 48 columns and the saved `Clinical Analytics` visual read back `DORAActivityKey`, `DORARecordID`, `DORAResourceID` and `DORASourceURL`.
- [ ] Retained-history reconciliation, refresh, recurrence and delivery remain open; the isolated visual receipt does not certify those gates.

### Local DoRA model projection — 2026-09-22

- [x] Add the source-preserving `DoraActivityRegistry` projection to the canonical local semantic model using the existing SharePoint-only M query and all 26 schema fields.
- [x] Preserve `DORAActivityKey` as the model identity and retain `Project ID` as a non-unique source field; add regression coverage for this distinction.
- [x] Rebuild the TMDL definition and update the reviewed source-only runtime baseline; local validation passes without claiming native binding.
- [x] Add/read back the native table through the authorised SharePoint Online List route; model readback showed `DORA Activity Registry table 28 of 28` with 48 columns and zero rows.

### Native DoRA flow details readback — 2026-09-22

- [x] Read back the canonical QLD Health flow details page for `CHHHS DoRA Activity Registry - Reviewed Upsert` (`00000000-0000-4000-8000-1393300880b7`).
- [x] Confirm Off status, Instant type, owner, SharePoint connection, no run-only users, Flow Checker 0 errors / 1 inactive-flow warning, and two visible successful 28-day runs.
- [x] Record the UI facts in ignored receipt `private/ops/2026-09-22-powerautomate-t11-dora-flow-readback.json`.
- [ ] Prove durable run-history capture, recurrence/schedule, refresh and report reconciliation, delivery and production acceptance. Keep T11 active.

## Phase: Conductor review fixes — 2026-09-22

- [x] Task: Reject malformed active CSV datastore resource IDs before DoRA API traversal instead of stringifying them (`7410b06`).
- [x] Verification: focused DoRA activity tests (15), full local suite (450 tests, 8 skipped), project checks (460), web-first contracts, Conductor validation and diff validation pass locally.
- [~] Native retained-history reconciliation, refresh, recurrence, delivery and production acceptance remain open.

## Phase: Conductor review fix — DoRA source identity boundary — 2026-09-22

- [x] Task: Reject surrounding whitespace in scalar DoRA datastore `_id` values instead of stripping a padded source identity before uniqueness/hash processing (`681d4db`).
- [x] Verification: focused DoRA activity tests (16), full local suite, project checks (460), web-first contracts, Conductor validation and diff validation pass locally.
- [~] Native retained-history reconciliation, refresh, recurrence, delivery and production acceptance remain open.
