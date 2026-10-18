# SharePoint List Architecture: Publication Registry

Status: **Active implementation design** (2026-09-17)  
Purpose: Decouple research publication data storage and human review from Power BI dashboard development, allowing immediate operational use by researchers and library staff.

---

## 1. Overview & Architecture

The architecture separates data ingestion, persistence/review, and presentation into three loosely coupled tiers:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Ingestion Engine (Power Automate & Native Power Query)    │
│    - Daily ESearch against PubMed API                       │
│    - DORA QLD Health RSS Feed Harvester                     │
│    - Large XML payloads stored in 01 Source archive library │
└──────────────────────────────┬──────────────────────────────┘
                               │ Upserts (SourceKey indexed)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Central Data Store: SharePoint List                      │
│    - List Name: "Publication Registry"                      │
│    - Immediate web UI access for CHHHS library & researchers│
│    - Human review of ambiguous affiliations (ReviewStatus)   │
│    - 1-click export to Excel / CSV                          │
└──────────────┬──────────────────────────────┬───────────────┘
               │ Tabular Reader               │ Manual Excel/CSV
               ▼                              ▼
┌──────────────────────────────┐ ┌────────────────────────────┐
│ 3a. Power BI Dashboard      │ │ 3b. Immediate Staff Use     │
│     (Track T12/T13)          │ │     (Search, Review, Export│
│     - Clean 6-table model    │ │      Monthly Reports)      │
│     - Fast refreshes (<30s)  │ └────────────────────────────┘
└──────────────────────────────┘
```

---

## 2. SharePoint List Schema Specification

**List Name:** `Publication Registry`  
**Description:** Official CHHHS Research Publication Register and Attribution Review Ledger.

| Field Internal Name | Display Name | Type | Indexed | Description / Allowed Values |
| :--- | :--- | :--- | :---: | :--- |
| `Title` | Title | Single line of text | **Yes** | Publication Title. Standard SharePoint mandatory title field. |
| `SourceKey` | Source Key | Single line of text | **Yes; unique** | Stable unique source identifier (e.g. `pubmed:24711477` or `dora:10037.1/12345`). Used for idempotent upserts; duplicate values must be rejected at the list boundary. |
| `CanonicalKey` | Canonical Key | Single line of text | **Yes** | Stable deduplicated publication key (e.g. `PUB:0034379c5548...`). |
| `Authors` | Authors | Multiple lines of text | No | Semicolon-delimited formatted author list. Plain text. |
| `Journal` | Journal | Single line of text | No | Journal title or publishing venue. |
| `PublicationYear` | Publication Year | Number (0 decimals) | **Yes** | 4-digit calendar year (e.g. 2026). Used for fast list view filtering. |
| `PublicationMonth` | Publication Month | Single line of text | **Yes** | Format `YYYY-MM` (e.g. `2026-04`) or blank if month unverified. |
| `PublicationDateRaw` | Raw Date Parts | Single line of text | No | Unprocessed source date parts (e.g. `Day=07; Month=Apr; Year=2014`). |
| `PublicationDatePrecision` | Date Precision | Choice | No | Choices: `day`, `month`, `year`, `range`, `unknown`, `rss_unverified`. |
| `SourceSet` | Source Set | Choice | No | Choices: `PubMed`, `DORA`, `PubMed; DORA`. |
| `PMID` | PMID | Single line of text | **Yes** | PubMed unique identifier. |
| `DOI` | DOI | Single line of text | **Yes** | Digital Object Identifier (clean normalized string). |
| `PubMedURL` | PubMed Link | Hyperlink or Picture | No | Direct URL to PubMed entry (`https://pubmed.ncbi.nlm.nih.gov/...`). |
| `DORAURL` | DORA Link | Hyperlink or Picture | No | Direct URL to DORA repository (`https://dora.health.qld.gov.au/...`). |
| `MatchedFacilities` | Matched Facilities | Multiple lines of text | No | CHHHS facilities identified in affiliations (e.g. `Cairns Hospital; Liz Plummer Cancer Care Centre`). |
| `CHHHSAffiliatedAuthors` | CHHHS Authors | Multiple lines of text | No | Names of authors associated with CHHHS affiliations. |
| `AttributionEvidence` | Attribution Evidence | Multiple lines of text | No | Exact source affiliation snippet supporting CHHHS attribution. |
| `ReviewStatus` | Review Status | Choice | **Yes** | Choices: `Needs Review`, `Included`, `Excluded`. Default: `Needs Review`. |
| `ReviewNotes` | Review Notes | Multiple lines of text | No | Reviewer notes explaining manual inclusion or exclusion reasons. |
| `FirstObservedUTC` | First Observed | Date and Time | **Yes** | ISO-8601 UTC timestamp when paper was first harvested. Never overwritten on re-refresh. |
| `LastObservedUTC` | Last Observed | Date and Time | No | ISO-8601 UTC timestamp of the most recent harvest verifying this paper. |

---

### 2.1 Extended Enrichment Schema (Planned Sources)

As additional academic sources (Scopus, Web of Science, Dimensions, Crossref, OpenAlex, ARDC Research Link Australia) are integrated, the following fields extend the registry without breaking the core 21-column baseline:

| Field Internal Name | Display Name | Type | Source(s) | Description / Notes |
| :--- | :--- | :--- | :--- | :--- |
| `FunderNames` | Funder Names | Multiple lines of text | Crossref, Dimensions, OpenAlex | Semicolon-delimited recognized funding organizations (e.g. `NHMRC; Medical Research Future Fund`). |
| `GrantIDs` | Grant / Award IDs | Multiple lines of text | Crossref, Dimensions, OpenAlex, ARDC | Specific grant or award numbers linked to CHHHS projects. |
| `MeSHHeadings` | MeSH Headings | Multiple lines of text | PubMed, Dimensions | Medical Subject Headings descriptors for thematic clustering. |
| `AuthorKeywords` | Author Keywords | Multiple lines of text | Scopus, WoS, Crossref | Author-supplied keywords. |
| `OpenAccessStatus` | Open Access Status | Choice | OpenAlex, Crossref, Dimensions | Choices: `Gold`, `Hybrid`, `Green`, `Bronze`, `Closed`, `Unknown`. |
| `OAUrl` | Open Access URL | Hyperlink or Picture | OpenAlex, Unpaywall via Crossref | Direct repository or publisher open-access PDF link. |
| `AffiliationsRaw` | Raw Affiliations | Multiple lines of text | Scopus, WoS, OpenAlex | Full affiliation strings for all co-authors preserved for deep entity analysis. |
| `OrganisationKeys` | Organisation Keys | Multiple lines of text | Explicit affiliation enrichment | Semicolon-delimited versioned organisation hierarchy keys. |
| `OrganisationNames` | Organisation Names | Multiple lines of text | Explicit affiliation enrichment | Resolved organisation names; many-to-many values are retained. |
| `OrganisationMatchMethod` | Organisation Match Method | Choice | Explicit affiliation enrichment | `explicit-affiliation-alias`, `unmatched`, or `review-required`. |
| `OrganisationMatchConfidence` | Organisation Match Confidence | Choice | Explicit affiliation enrichment | `high`, `medium`, `low`, or `unknown`; never inferred from author name alone. |
| `OrganisationEvidence` | Organisation Evidence | Multiple lines of text | Explicit affiliation enrichment | Matched alias and source evidence summary. |
| `OrganisationReferenceVersion` | Organisation Reference Version | Single line of text | Local reference registry | Version of the organisational hierarchy used for enrichment. |
| `OrganisationEffectiveFrom` | Organisation Effective From | Date and Time | Local reference registry | Start of the organisational interpretation. |
| `OrganisationEffectiveTo` | Organisation Effective To | Date and Time | Local reference registry | End date when a historical structure is superseded; blank means current/unknown. |
| `AffiliationHierarchy` | Institutional Hierarchy | Multiple lines of text | OpenAlex (ROR), Scopus | Normalized parent/child entity mapping (e.g. `Queensland Health > Cairns and Hinterland Hospital and Health Service > Cairns Hospital`). |
| `CitationCount_Scopus` | Scopus Citations | Number (0 decimals) | Scopus | Source-isolated citation count as of latest harvest. |
| `CitationCount_Crossref` | Crossref Citations | Number (0 decimals) | Crossref | Source-isolated citation count as of latest harvest. |
| `CitationCount_OpenAlex` | OpenAlex Citations | Number (0 decimals) | OpenAlex | Source-isolated citation count as of latest harvest. |
| `CitationMetricsObservedUTC`| Citation Metrics UTC | Date and Time | All | UTC timestamp when citation counters were last observed. |

---

### 2.1.1 Derived author registry

The publication list remains publication-centred. Author analysis must use a separate derived registry or view described in [Author-centred registry and attribution design](AUTHOR_REGISTRY_DESIGN.md). At minimum it must preserve `AuthorKey`, display name and variants, stable external identifiers, identity status/confidence, affiliation history, publication/source keys, author order, affiliation evidence, evidence URL, observation time, and review state.

### 2.1.2 DORA Activity Registry

The linked Queensland Open Data DoRA dataset is a separate project/activity register and must not be forced into the publication list. The source-preserving target is a separate SharePoint list named `DORA Activity Registry`, described by `config/dora-activity-registry.schema.json` and read by `config/DoraActivityRegistry.m`. It contains seven provenance fields and all 19 current source columns, plus the datastore `_id` key, including ethics/review references, project/contact fields, sponsor, dates, disease category, site structure, DORA authority and consent. The source `_id` is the row identity; `Project ID` may repeat and is not a deduplication key. Native list creation, import and readback remain acceptance gates.

### 2.1.3 Organisational hierarchy enrichment

The local reference registry in `config/organisation-hierarchy.json` provides a versioned HHS → service group → facility group hierarchy. `scripts/organisation_enrichment.py` matches only explicit affiliation aliases and preserves the evidence, confidence, reference version, and effective dates. It does not infer an organisation from a person name, title, locality, journal, or collection location. The live list should add these fields only after a schema readback confirms the internal names and a controlled backfill proves key-set and review-state preservation.

Organisation, author, facility, and publication relationships are many-to-many. The list fields are a compact projection for filtering; detailed author-to-organisation and publication-to-organisation bridges belong in derived registries or model tables so that multiple affiliations and historical changes are not flattened away.

Name-only or ResearchGate-only matches are candidates, not included publications. Author-derived candidate sets must reconcile to the canonical publication key set before reporting or release.

### 2.1.4 DORA metadata extensions and limitations

Where exposed by the historical DORA source, retain repository collection/community, item type, handle, version, deposit/update timestamp, raw date, DOI/PMID, and exact description/attribution text. Do not interpret a repository date as a formal publication date without source evidence. DORA coverage, document type, version relationships, and author-to-affiliation linkage remain explicit review fields rather than silent assumptions.

### 2.2 Field Precedence & Conflict Resolution Strategy

When multiple data sources report differing values for the same canonical publication, the following deterministic resolution rules apply:

1. **Inclusion / Attribution Authority:**  
   `PubMed` and `DORA` remain the primary baseline authorities. An item is classified as `Needs Review` upon first discovery by any source, but its CHHHS attribution must be supported by explicit facility or hospital text evidence in `AttributionEvidence`.
2. **Canonical Deduplication Precedence:**  
   - Normalized `DOI` (lowercase, stripped of `https://doi.org/` prefix) is the primary deduplication anchor across all sources.
   - For biomedical papers lacking DOI, `PMID` is authoritative.
   - For internal Queensland Health publications lacking DOI/PMID, `DORAKey` is authoritative.
3. **Bibliographic Metadata Priority:**  
   - **Title:** `PubMed` > `Crossref` > `Scopus` > `WoS` > `OpenAlex` > `DORA RSS`.
   - **Journal Name:** Standard ISO abbreviations from PubMed/NLM; full journal titles from Crossref.
   - **Publication Dates:** Exact year and month are preserved from the earliest formal publication notice. The raw date string and precision level (`day`, `month`, `year`) are never lost.
4. **Citation Counter Isolation:**  
   Citation counts from Scopus, Crossref, and OpenAlex are **never summed** or blended. Each provider’s counter is maintained in its own dedicated column with observation timestamps, acknowledging differing citation indexes and counting scopes.

---

## 3. List Performance & The 5,000-Item Threshold

Because the publication collection already contains ~1,970 baseline entries and continues to expand, the list is designed to safely bypass the SharePoint 5,000 List View Threshold:

1. **Mandatory Column Indexes:**  
   `SourceKey`, `CanonicalKey`, `PublicationYear`, `PublicationMonth`, `ReviewStatus`, `PMID`, `DOI`, `Title`, and `FirstObservedUTC` are configured as indexed columns. `SourceKey` is also configured as the unique list identity.
2. **Standard & Specialized List Views:**
   - **`All Included Publications` (Default Operational View):**  
     Filter: `ReviewStatus` is equal to `Included`. Sorted by `PublicationYear` (descending) and `PublicationMonth` (descending).
   - **`Needs Review` (Triage & Curation View):**  
     Filter: `ReviewStatus` is equal to `Needs Review`. Sorted by `FirstObservedUTC` (descending). Primary view for library staff triaging new automatic ingests.
   - **`By Publication Year` (Yearly Archive View):**  
     Grouped by `PublicationYear` (descending). Displays year totals and yearly publication counts.
   - **`By Primary Source` (Reconciliation View):**  
     Grouped by `SourceSet` (`PubMed`, `DORA`, `PubMed; DORA`). Used to verify cross-source harvest parity.
   - **`Matched Facilities` (Facility Reporting View):**  
     Filter: `MatchedFacilities` is not blank. Enables filtering and exporting by individual facilities (e.g., Cairns Hospital, Liz Plummer Cancer Care Centre, Atherton Hospital).
3. **Heavy Payloads in Document Library:**
   - Full abstracts and large XML node arrays are kept as chunk files in the `01 Source archive` document library, referenced by `SourceKey`. The list columns remain compact and lightning-fast.

---

## 4. Operational Workflows for Users (Immediate Benefits)

Without waiting for Power BI report publishing:
- **Triage & Curation:** Reviewers open the `Needs Review` view, inspect the `AttributionEvidence`, and change `ReviewStatus` to `Included` or `Excluded`.
- **Facility Breakdowns:** Search or filter by `MatchedFacilities` to produce facility-level publication lists.

---

## 5. Seed Data Population & Enterprise Tenant Compliance

### 5.1 Enriched Seed Dataset
The pre-processed seed data is stored in:
- CSV: `private/ops/sharepoint-seed/publication-registry-seed.csv` (1,265 records, 34 enriched columns)
- JSON: `private/ops/sharepoint-seed/publication-registry-seed.json`

### 5.2 Recommended Import Routes

#### Route A: Browser Web UI Import (Recommended & Tenant-Compliant)
Because Queensland Health enforces strict Entra ID third-party application consent policies (AADSTS700016), third-party CLI tools (such as PnP Management Shell App `{{SHAREPOINT_CLIENT_ID}}`) require central tenant admin approval. The user's active browser session operates under approved enterprise SSO:
1. In Microsoft Lists (`{{SHAREPOINT_LISTS_URL}}` or `https://www.office.com/launch/lists`):
2. Click **+ New list** -> **From CSV**.
3. Select `private/ops/sharepoint-seed/publication-registry-seed.csv`.
4. Ensure column types match the schema above and name the list **`Publication Registry`**.
5. Confirm creation.

#### Route B: In-Place Power Automate Ingestion
Use the deployable package `private/ops/flow-packages/sharepoint-upsert.zip` to update flow `{{FLOW_ID}}`. The cloud flow uses the user's pre-approved SharePoint connection to upsert records into the list without triggering local PowerShell auth gates.

## Connector boundary

This publication upsert flow is distinct from the OneDrive-based validation/archive flow. OneDrive actions are appropriate for private source-archive files and commit readback; they are not the persistence path for either this publication list or the future `Grants Registry` list. The grants system must use a separate, single SharePoint Online list-upsert flow targeting `Grants Registry`.

#### Route C: PowerShell PnP Automated Import (If App Consented)
If the PnP Management Shell App is granted admin consent in tenant `{{TENANT_ID}}`:
```powershell
pwsh ./scripts/Deploy-SharePointList.ps1
pwsh ./scripts/Import-SharePointSeed.ps1
```
