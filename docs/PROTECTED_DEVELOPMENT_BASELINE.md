# Protected development baseline — 2026-09-12

Supported Power BI browser access is restored. The existing original report was downloaded through File → Download this file → report and data. Its PBIX is 8,500,533 bytes, passed ZIP CRC validation and contains DataModel and Report/Layout. It remains outside this repository; workforce rows were not inspected. Its exact path/hash are in ignored `private/ops/original-pbix-backup.json`.

A distinctly named PBIX copy was imported into the existing My workspace. Power BI created both a new report and a distinct semantic model. The model shows the nine restored tables; its related-content list contains only the development report. Permissions showed one Queensland Health Workspace Admin, no sharing links and no inherited item access. The restored report renders. This is a restored baseline for development, not an accepted research report.

Two native persistence/rollback tests passed:

- Model: create `CodexIsolationCanary = 1` on Age, commit, reload, locate and read back the exact expression; delete the measure, reload, and verify an empty exact-name search.
- Report: rename the development landing page to `Isolation report canary`, save, reload and verify; restore `Monthly Research`, save, reload and verify.

Power BI automatically converted the development model to large semantic-model storage format when editing began, making version history available. This was observed on the isolated copy. The original report/model were not edited or rebound; sharing, schedules and VM settings were not changed.

Private target identities and step evidence are recorded in `private/ops/isolated-baseline-observation.json`. T10 is in progress: explicit revision/concurrency checks and remaining review evidence need completion before broader authoring. T08 capability records must also be updated to distinguish proven report/model persistence from still-unverified native Power Query execution, source refresh and full export/readback.

Next: establish the development revision checkpoint, apply the research source/model work in the isolated target, reconcile the three report pages, then verify native M/DAX, refresh, rendering and model/export key sets. Publication/rebinding and scheduled delivery retain their separate approval gates.

## Version checkpoint and Power Query probe

Saved the reverted development baseline through File → Save to version history. The success toast appeared and Version history read back the description “Protected baseline before research sources; model and report canaries reverted and verified 2026-09-12.” The current version displayed Today, 5:43 pm, with two earlier 5:41 pm versions. Private evidence is in `private/ops/isolated-version-checkpoint.json`.

Transform data opened the native Power Query editor with nine inherited queries. The selected query failed evaluation because its data gateway was inaccessible. A temporary blank-query preview, using typed empty-table and text-normalisation checks, also failed with the same gateway error after selecting the available `(none)` gateway option. This is not native M validation. Cancel closed the unsaved Power Query session and the model returned to nine tables. No research source or gateway-setting change was saved. Next inspect the isolated model's connection settings and supported cloud execution route before retrying source authoring; do not change shared gateway permissions.

The subsequent isolated-model Settings → Gateway and cloud connections inspection showed the on-premises/VNet switch enabled but disabled for editing, no suitable gateways, and no cloud connections. No connection or permission settings were changed. Local verification remained 148 unit tests passed, 212 project checks passed, and `PASS_LOCAL_ONLY`. A subsequent Power Query launch stalled with a blank dialog; a model reload recovered the nine-table model without saving any query edits.

The pending editor subsequently loaded. Metadata inspection showed a legacy SQL Server connection to the local machine. Removing all nine inherited queries in the unsaved session, then adding a source-free typed-table preview with gateway `(none)`, still produced the gateway-access error. Cancel discarded the entire session; all nine baseline tables were observed again. No test table or legacy-query deletion was saved. This narrows the problem beyond the selected legacy query, but does not prove a tenant-wide restriction or justify changing shared gateway access. F02 has meanwhile been repaired in local M and generated definitions; 149 tests, 212 project checks and `PASS_LOCAL_ONLY` pass. Native acceptance remains open.

## Current-project connection inspection

Power Query Manage connections showed the inherited local SQL source linked to a personal cloud connection. The Current project unlink control acknowledged removal and showed “No connection linked”; no global connection was deleted. A new source-free preview still failed with the gateway-access error after selecting `(none)` (5.18 seconds). The diagnostic query session was cancelled without saving; persistence of the unlink after cancellation remains unverified. The private execution handoff is `private/ops/POWERQUERY_EXECUTION_HANDOFF.md`. Capability records now distinguish verified isolated report/DAX persistence from available-but-unverified Power Query writes. No native acceptance gate is closed by these observations.

## Chrome repair attempt, 2026-09-13

The isolated model still showed nine baseline tables and the protected version from the previous day at 5:43 pm. Manage Connections and Gateways identified the inherited SQL Server connection as Personal mode; its explicit connection test returned Offline. Model settings still offered no suitable gateway or cloud connection, and the enabled gateway switch was disabled for editing.

A Current project unlink was submitted using Save with no query-definition edits. Power BI processed the request and returned to the model; reopening Power Query showed the same SQL connection linked again. Therefore saving the unlink did not establish a persistent repair. A source-free logical TRUE table preview with gateway `(none)` failed again in 0.60 seconds. The diagnostic session was cancelled, returning to model view. Browser attachment was lost during the final independent baseline check, so that additional verification was not completed. No original-model, global connection, permissions, capacity, schedule or VM changes were performed.

The blocker remains unresolved. The observations establish an offline inherited personal-mode connection and an inaccessible gateway selection, but do not establish why the web editor fails to switch this mashup to cloud execution. Private diagnostic identifiers and action receipts: `private/ops/2026-09-13-gateway-repair-attempt.json`. Further repair must resolve the isolated model's persisted gateway/source dependency through supported authoring or owner/support remediation; native acceptance remains open.

## Persisted source removal and native cloud execution — 2026-09-13

The previous gateway blocker is superseded for source-free execution. After verifying the protected version-history checkpoint, all nine legacy tables were deleted through the isolated model's normal Delete from model action. One out-of-sync rejection was recovered by reading the refreshed model and retrying the still-present table. A reload showed no tables, and Power Query showed Queries [0]. No original or global connection was modified.

With gateway `(none)`, `#table(type table [NativeProbe = logical], {{true}})` returned TRUE, one row and one column, in 8.30 seconds. The diagnostic expression was replaced before saving by the real ReportingWindow M query. It evaluated the previous complete Brisbane month as 1 August to 1 September 2026 exclusive, then saved, loaded and survived reload as the sole three-column table. This proves native M evaluation and persisted import-table authoring; it does not prove live external source access or end-to-end research refresh. The development report's old bindings now require replacement as planned; it is not a usable research report yet. The protected baseline remains the rollback path. Private action evidence: `private/ops/2026-09-13-native-cloud-repair.json`.

The first real cloud source also evaluated successfully: DoraSourceObservations returned four live RSS items with title, link, description and raw pubDate in 2.66 seconds. A new anonymous Public-privacy Web connection was created for the public DORA source without a gateway. Save/load returned to the model with ReportingWindow and DoraSourceObservations. This is raw staging of a finite feed; author parsing, historical retention, PubMed collection and canonical bibliography acceptance remain open.

Post-reload native DAX verification succeeded: 4 DORA rows, 4 distinct source URLs, 0 blank source URLs, and ReportingWindow 2026-08-01 to 2026-09-01 exclusive. The reusable check is `config/native-staging-check.dax`; it is a staging smoke check, not full bibliography acceptance.

## Parser implementation continuation

Native fnParsePubDate passed ten date-precision cases. The temporary fixture query was replaced in full with DoraHarvest, which returned four live rows and eleven metadata columns using DoraSourceObservations. Save was requested, but identity verification recurred after Continue. These parser edits are preview-verified, not persistence-verified; the open editor is retained for user sign-in. The earlier two saved staging/reporting tables remain the last independently verified persisted state. See `private/ops/2026-09-13-native-parser-validation.json`.

## Continued native ingestion — 2026-09-13

Browser access recovered. Reload confirmed DoraHarvest had persisted from the earlier pending save (11 columns). The attribution-evidence revision now saved and survived reload (12 columns), along with 28 FacilityDefinitions rows and an optional blank NCBI parameter. Native ESearch over the anonymous public cloud connection succeeded: the exact Cairns Hospital affiliation probe reported 599 hits (retmax=1; a connection probe, not full coverage).

Power Query rejected the recursive NCBI helper with a cyclic-reference error, including internal recursion. A bounded List.Generate retry sequence compiled as a native function and executed the anonymous probe successfully. Retryable HTTP failures remain errors after at most five attempts, with delay/backoff and a fixed HTTPS origin. Static checks were updated for this outcome-linked implementation change; this is not blanket native acceptance.

The web TMDL preview showed an additive PubMedHarvest expression, and Apply reported success. The full XML parser and a real-PMID metadata probe also applied successfully. Native execution returned six full author names, a 3,078-character abstract, explicit author affiliation evidence including CHHHS, and a raw issue date of 2026 with year precision. The complete metadata serialized to 51,999 characters, so chunked persistence is required instead of one text cell. Full harvest, chunk reconciliation, historical DORA and canonical readback remain pending.

### Full ingestion deployment and final validation interruption

The first complete native XML pass returned 1,254 PMIDs. Nine native M audit rows passed, including reconstruction of 2,177 metadata chunks, exact requested/returned key counts, author evidence counts and date precision. Saving completed, and DAX readback confirmed 1,254 stored PMIDs and 2,177 chunks. However, 34 records failed the stored-character-length check. This stage is therefore not lossless acceptance. The correction encodes UTF-8 metadata as hexadecimal before chunking, avoiding text normalization and oversized cells.

Comparison with the earlier collector configuration exposed an omitted historical Cairns Public Health Unit search. The revised PubMed query retains these scope-review records without an approved facility bridge. It exposes the complete coverage-ID set independently of facility matches. The full-author parser also preserves initials where a full given name is absent.

TMDL Apply reported success for the revised PubMed expressions and the PubMed publications, author-evidence, encoded-metadata and audit tables; it also applied the historical DORA expression and publications, encoded-metadata and audit tables. The reproducible scoped script is config/native-ingestion.tmdl, generated by scripts/build_native_ingestion.py. It requires the existing FacilityDefinitions and optional pNCBIEmail; it does not publish or trigger a refresh itself. The local canonical query now uses full metadata sources and retains PubMed abstracts, but the canonical model/report has not been deployed or accepted.

A manual native refresh was started. Its last visible state was Processing queries and validating semantic model. At approximately 09:28 UTC, the browser-control security check became unavailable and denied access because the admin-enforced policy could not be verified. The tab was successfully marked for handoff. Final refresh success, historical DORA counts, restored PubMed coverage, author-evidence completeness and post-import encoded-metadata checks remain UNVERIFIED. Do not label ingestion complete or promote these tables until config/native-ingestion-storage-check.dax and both native audit tables pass after a verified refresh.

### Verified source refresh and storage checks — 2026-09-14

Browser access recovered. Initial native readback showed the new publication tables empty and the earlier 1,254-record audit still stored. A new isolated-model on-demand refresh was therefore requested. Its exact request was tracked through completion: 15:33:38–15:45:09 Brisbane time, with the data stage completing in 11m 25s. Private correlation evidence is in `private/ops/2026-09-14-native-refresh.json`.

After that refresh, native queries returned 1,261 PubMed publications, 709 DORA publications and 11,501 PubMed author-evidence rows. All nine PubMed and five DORA source audit rows passed. Post-import checks found 3,892 PubMed metadata chunks and 711 DORA chunks, with zero length/index failures, missing or unexpected metadata keys, or non-UTF8-HEX encoding rows. These are observed source counts, not canonical bibliography counts.

The existing Power Automate environment now contains a saved manual-only development validation flow. Its standard Power BI query action successfully read this isolated model in My Workspace. The subsequent readiness query also succeeded against the populated sources; its deliberately failing branch has not been exercised. `config/native-ingestion-readiness.dax` documents that prerequisite gate. It does not replace storage checks, refresh correlation or full export validation. Private flow evidence is in `private/ops/2026-09-14-powerautomate-query-proof.json`.

Durable source-history consumption, reviewed canonical model deployment, report rendering, complete exports, unattended-cycle tests and ongoing licence rights remain open. No scheduled trigger or delivery was enabled. Local validation remains 161 tests, 235 project checks and PASS_LOCAL_ONLY.
