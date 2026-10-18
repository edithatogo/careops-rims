# Architecture and Operations: Publication Registry Versioning Systems

This document clarifies the versioning capabilities across the CHHHS Research Publication Registry platform, covering SharePoint Online, Power Automate, Power BI semantic models, and local Git repositories. Local definitions and package receipts are not evidence that a tenant feature is enabled or that rollback has been tested.

---

## 1. Summary of Versioning Capabilities

| Layer | Native Versioning Mechanism | Repository / Git Integration | Disaster Recovery / Rollback |
| :--- | :--- | :--- | :--- |
| **SharePoint List** | Must be read back from the target list; version settings are not assumed from a script. | Seed datasets (`publication-registry-seed.csv`, `.json`) and deployment scripts in Git. | Restore only after item-level version history and an isolated recovery test are evidenced. |
| **Power Automate Flow** | Platform Version History and solution-aware drafts are conditional on the actual environment/flow capability. | Declarative workflow definitions (`config/flows/*.definition.json`) and private package exports. | Revert only after native version-history or isolated re-import/readback is verified; local ZIPs are not native rollback evidence. |
| **Power BI Semantic Model** | Depends on the existing workspace/report capabilities and must be read back; TMDL is not a service snapshot. | Declarative TMDL and DAX measure scripts. | Use an isolated model/report with an approved recovery path; no shared-model rollback is claimed locally. |
| **Publication Data & Lineage** | Persistent observation timestamps (`first_observed_utc`, `last_observed_utc`, `CitationMetricsObservedUTC`). | SQLite database (`Registry` table + `SourceRecord` table) with immutable raw ingestion batches. | Idempotent replay from raw feeds; deterministic deduplication ensures zero data loss or ghost deletions. |

---

## 2. SharePoint List Versioning

### Configuration
SharePoint Online supports automated versioning on custom lists. In this project, versioning is enforced via `scripts/Deploy-SharePointList.ps1`:
```powershell
Set-PnPList -Identity "Publication Registry" -EnableVersioning $true -MajorVersions 500
```

### Operational Behavior
1. **Automated Tracking:** Every modification—whether applied via the Power Automate upsert flow, human curation (changing `ReviewStatus` from `Needs Review` to `Included`), or batch PowerShell—creates a numbered version (1.0, 2.0, 3.0, etc.).
2. **Audit Trail:** Each version records:
   - Modified date/time (UTC).
   - Modified by (Service Principal or User Account).
   - Exact delta: previous value vs. new value for every modified column.
3. **Restoration:** Any previous version can be inspected and restored with one click from the SharePoint List context menu (`Item -> Version History -> Restore`).

---

## 3. Power Automate Flow Versioning & Platform Deduplication

### Platform Version History (conditional)
Power Automate may expose version history for a cloud flow, but this repository
does not assume that capability, solution-awareness, or rollback semantics until
the exact flow/environment is inspected and a native readback is recorded:
- Navigate to flow details: `Flow Details -> Version History`.
- Shows timestamp, author, save comments, and allows instant rollback to any previously saved revision.

### Git-Controlled Declarative Definitions
To ensure engineering rigor and compliance:
1. **Flow Definitions in Code:** The workflow is authored and maintained declaratively in `config/flows/publication-registry-upsert.definition.json`.
2. **Package Generator:** `scripts/build_sharepoint_upsert_package.py` packages the definition and metadata into `private/ops/flow-packages/sharepoint-upsert.zip`.
3. **Platform Deduplication:** When the approved native route is available, an
   import must explicitly update the existing flow (`{{FLOW_ID}}`) rather than
   create a second flow. This is a deployment rule, not evidence that the
   update has occurred.

## 6. One-owner release routine

1. Work from a focused change and keep tenant/runtime material in ignored
   private storage.
2. Run `python3 scripts/agent_harness.py check --task all` and record the
   `PASS_LOCAL_ONLY` result.
3. Build a clean source candidate, verify the pinned Conductor submodule and
   generate a reproducible source receipt with `scripts/package_release.py`.
4. Only after a separately approved native candidate/readback, apply the
   platform change and record its target identity, rollback path and receipt.
5. Create a release tag/manifest and optionally a GitHub Release. Conductor is
   the backlog and evidence index; no duplicate Projects/Jira/Planner system is
   required.

---

## 4. Multi-Source Ingestion & Enrichment Pipeline

### Architecture
The deduplication pipeline supports 8 distinct bibliographic and scientometric sources:
1. **PubMed:** National Library of Medicine API (mesh terms, affiliations, PMIDs).
2. **DORA:** Queensland Health Institutional Repository (staff publications, local facility tags).
3. **OpenAlex:** Live REST API (global citation counts, Open Access status, OA landing URLs, ROR affiliations).
4. **Crossref:** Live REST API (publisher citation counts, funder acknowledgments, grant award numbers).
5. **Dimensions:** Structured CSV/JSON ingestion (`ingest_dimensions.py` extracting citations, FCR, RCR).
6. **Scopus:** Structured CSV ingestion (`ingest_scopus_wos.py` extracting Scopus EID, Scopus citations, author affiliations).
7. **Web of Science:** Structured CSV/TSV ingestion (`ingest_scopus_wos.py` extracting WoS UT, Core Collection citations, grant numbers).
8. **ARDC Research Link Australia (RLA):** Structured activity ingestion (`ingest_scopus_wos.py` linking MRFF/NHMRC grants and Australian research activity IDs).

### Provenance Preservation
- Every raw ingestion maintains immutable timestamps and source identifiers.
- Independent citation counters (`CitationCount_OpenAlex`, `CitationCount_Crossref`, `CitationCount_Scopus`, `CitationCount_WoS`) prevent false equivalence.
- Merged records maintain a composite `SourceSet` (e.g. `PubMed; DORA; OpenAlex; Crossref`).

---

## 5. Automated Monthly Reporting & DOCX Export

### SharePoint View
The "Past Month Publications" view filters the list to:
- `ReviewStatus` = `Included`
- Sorted by `PublicationYear DESC`, `PublicationMonth DESC`.

### DOCX Generation Utility
`scripts/export_monthly_docx.py` generates an executive Word report for clinical governance:
```bash
python3 scripts/export_monthly_docx.py --month 2026-08 --output reports/CHHHS-Publications-Monthly-2026-08.docx
```
- Fully styled to Queensland Health Clinical Research branding (Deep Teal `#005C8A`, Navy Slate `#2B3E50`, Evergreen `#107C41`).
- Contains Executive Summary KPI cards, facility breakdowns, publication types, and hyperlinked citations with PubMed/DOI links.
