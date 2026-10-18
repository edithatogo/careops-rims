# Publication history in SharePoint

Status (2026-09-14): the first PubMed/DORA archive batch is now **committed**, with exact manifest readback verified by the native manual flow. The approved organisation OneDrive archive is SharePoint-backed. This establishes one accepted retained baseline, not complete ongoing retention or final report consumption.

The isolated model refresh completed after the archive was bound to the existing approved cloud connection. Loaded native DAX verified all ten reconstruction/rollover/interruption tests. Full stored metadata reconstruction passed for 1,261 PubMed records (32,289,819 JSON characters) and 709 DORA records (2,603,915 characters), including exact archived publication-key sets and payload identities. Private refresh/run identifiers are in `private/ops/retention-native-tests.json`.

The committed-history reader and a key/observation-date projection were accepted through TMDL. A prior preview reported 1,261 unique PubMed keys and 709 unique DORA keys, with metadata character totals matching the validated archive. The current Power BI model readback contradicts a loaded projection: both `RetainedPubMedPublications` and `RetainedDoraPublications` currently show **Table contains no data** in model view. Processed-model loading therefore remains pending, and the canonical reporting consumers have not been switched to retained history.

## Current implementation route

Use the existing organisation OneDrive storage, which is SharePoint-backed, rather than create a new site or require a Fabric workspace. The approved folder already contains `01 Source archive`, `02 Registry`, `03 Reporting` and `04 Development`. The existing manual development flow uses Power BI and OneDrive for Business; it has no recurrence or delivery action.

`scripts/build_native_retention_package.py` builds an importable package from the verified native export. It writes immutable files named with a new batch UUID, table and page number to `01 Source archive`; each write must read back exactly before its cursor advances. Key sets and row counts must match independent model queries. The package deliberately does not emit a committed manifest or promote a registry yet. The committed-history reader and metadata decoder are now deployed in the isolated model and tested in native previews. The separate manual bootstrap commit flow has now accepted the validated baseline after refresh-generation correlation, loaded metadata checks and exact key reconciliation. Report consumption and unattended commit promotion remain required.

The isolated deployment package also includes `config/native-canonical-retained-partitions.tmdl`. After contributor-authorized refresh readback, it rebinds the existing canonical `PubMedPublications` and `DoraPublications` names to the committed-history projections without changing the shared/original model. It remains a deployment command, not evidence of a completed live write.

The list/library design below is an optional alternative if a shared SharePoint site is later selected. No dedicated list or library has been created, and their specific configuration checks are not proof of the current file-based route.

## Alternative list/library storage design

Create a `Publication Sources` list with version history enabled. `SourceKey` is required single-line text, unique and indexed: `dora:<handle>` or `pubmed:<PMID>`. Keep source identities separate from reviewed canonical identities. Fields:

| Field | SharePoint type and rule |
| --- | --- |
| Title | Single-line text; display label only, never the complete bibliography |
| SourceKey / Source / SourceIdentifier | Single-line text; stable identity |
| SourceURL | Hyperlink |
| FirstObservedUTC | Date/time; set once on creation, never reset during refresh |
| LastObservedUTC | Date/time; advance only after a successful observation |
| LatestCommittedBatch | Single-line text; points to a validated retained batch |
| RawPublicationDate / DatePrecision | Single-line text; retain uncertainty |
| PublicationDate | Nullable date; populate only when exact date is supported |
| CanonicalKey | Nullable single-line text; reviewed mapping, never guessed |
| ReviewStatus | Choice: Pending, Included, Excluded; new records default Pending |

Create a `Publication History` document library with version history enabled. Store complete UTF-8 source metadata, full authors, abstracts and exact affiliation/attribution evidence as files, rather than truncating them into list columns. Use stable source/batch paths and retain prior versions. A batch manifest records source identifiers, counts, extraction time, query/parser versions, coverage, validation outcomes and metadata file paths. Keep review decisions separately from source updates so ingestion cannot overwrite them.

## Native ingestion behaviour

1. Backfill the complete validated historical corpus, not just the current RSS window. Preserve any evidenced earlier observation timestamps; otherwise use the actual import time and label the observation as a baseline. Never infer first observation from publication or feed dates.
2. In Power Automate, process one batch at a time. Resolve `SourceKey` using an indexed equality filter; create missing items or update existing items. Enforce uniqueness at the list as well as in the flow. A conflicting create must re-read the existing item rather than make a duplicate.
3. Write complete metadata files and validate expected versus stored key sets before committing the batch manifest. Readers consume only committed batches. Preserve the previous committed state if collection, pagination, file storage or validation fails.
4. Never delete an item, erase its metadata or mark it excluded because it is absent from a later feed. A finite RSS feed is a discovery window; absence is not a deletion signal. An unavailable feed is not a successful empty batch.
5. Build the reporting source from retained committed history plus reviewed identity mappings. Keep collection and final reporting refresh separate to avoid a self-overwriting model/register cycle.
6. Use the existing standard SharePoint connector where service access and tenant policy permit. Dataset extraction remains conditional on a successful native action test; otherwise use an assisted import of validated public metadata. Leave recurring activation and delivery disabled pending their existing approval gate.

## Required live acceptance

- Verify inherited access and retention/versioning for the approved existing folder. If the alternative list design is used, additionally verify list uniqueness/index and list/library versioning. Connector access and one-file readback are already evidenced; full-batch acceptance remains open.
- Import and read back historical source keys and complete metadata; reconcile exact sets and full contents, not only counts.
- Replay the same batch: no duplicate items and unchanged FirstObservedUTC.
- Process a smaller subsequent feed: earlier records and their complete metadata remain available to the report.
- Interrupt a batch: the previous committed history remains readable, with no partial batch exposed.
- Confirm source updates preserve review decisions, date precision and attribution evidence.

Use a separate temporary validation list/library for rollover and failure cases; synthetic records must never enter live publication data. Local tests do not establish these tenant acceptance gates.
## Retained reporting projections

`config/native-retained-dora-projection.tmdl` and `config/native-retained-projections.tmdl` are the additive isolated-model payloads for retained DORA and retained PubMed reporting projections. Power BI TMDL accepts one command per script, so apply them separately after the parser fixtures and live archive parity checks pass. The current live report inputs remain unchanged until then.

If the live DORA web feed fails during a reporting-model refresh, apply `config/native-dora-archive-partitions.tmdl` to the isolated model. It preserves the existing DORA table shapes and replaces only their M partitions with the most recent committed archive. The collection flow must still record its failure and leave the prior committed archive intact; it must never declare an unavailable feed to be an empty collection.
