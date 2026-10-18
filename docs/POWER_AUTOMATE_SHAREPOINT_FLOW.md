# Power Automate Ingestion: SharePoint List Pattern

Status: **Implementation Architecture** (2026-09-17)  
Prerequisite: Standard Office 365 licensing (no premium or Fabric dependency).

---

## 1. Flow Overview & Standard Connector Routing

By using the **SharePoint List** as the primary operational registry, the Power Automate ingestion flow avoids:
- The missing dataset refresh status correlation gate in Power BI.
- The 30+ MB single-cell string overflow limit in Power BI tables.
- The need for premium HTTP connectors (uses standard RSS, standard SharePoint, and staged Power Query actions).

```
[ Trigger: Daily 08:00 AEST or Manual ]
                │
                ▼
[ Fetch Observations from PubMed / DORA ]
                │
                ├───> [ Heavy XML/JSON Archive ] ──> Create file in "01 Source archive"
                │
                ▼
        [ For Each Observation ]
                │
                ▼
[ SharePoint: Get items (Filter Query: SourceKey eq '@{items('...')?['SourceKey']}') ]
                │
         Is Empty?
        ┌───────┴───────┐
       Yes              No
        │                │
        ▼                ▼
[ Create item ]   [ Update item ]
- Title           - LastObservedUTC
- SourceKey
- FirstObservedUTC
- ReviewStatus = "Needs Review"
```

---

## 2. Detailed Action Configurations

### Step A: Observation Retrieval
- **DORA RSS:** Handled via standard Power Automate **RSS connector** (`List all RSS feed items`) or staged Power Query cloud harvest.
- **PubMed:** Handled via staged cloud Power Query or batch file retrieval.

### Step B: Archive Raw Payloads
- Heavy raw metadata payloads (abstracts, raw XML, full author affiliation trees) are saved as `.json` files directly to the `01 Source archive` document library using the standard **SharePoint - Create file** action.
- File naming format: `archive/<Source>/<Year>/<SourceKey_Sanitized>.json`.

### Step C: Idempotent Registry Upsert (SharePoint Connector)
For each observed paper:

1. **SharePoint - Get items:**
   - **Site Address:** Target Research Site
   - **List Name:** `Publication Registry`
   - **Filter Query:** `SourceKey eq '@{item()?['SourceKey']}'`
   - **Top Count:** 1

2. **Condition: `length(body('Get_items')?['value']) is equal to 0`**

   - **If TRUE (New Publication Discovered):**
     - Action: **SharePoint - Create item**
     - Fields:
       - `Title`: `@{item()?['Title']}`
       - `SourceKey`: `@{item()?['SourceKey']}`
       - `CanonicalKey`: `@{item()?['CanonicalKey']}`
       - `Authors`: `@{item()?['Authors']}`
       - `Journal`: `@{item()?['Journal']}`
       - `PublicationYear`: `@{item()?['PublicationYear']}`
       - `PublicationMonth`: `@{item()?['PublicationMonth']}`
       - `SourceSet`: `@{item()?['SourceSet']}`
       - `PMID`: `@{item()?['PMID']}`
       - `DOI`: `@{item()?['DOI']}`
       - `PubMedURL`: `@{item()?['PubMedURL']}`
       - `DORAURL`: `@{item()?['DORAURL']}`
       - `MatchedFacilities`: `@{item()?['MatchedFacilities']}`
       - `AttributionEvidence`: `@{item()?['AttributionEvidence']}`
       - `ReviewStatus`: `"Needs Review"`
       - `FirstObservedUTC`: `@{utcNow()}`
       - `LastObservedUTC`: `@{utcNow()}`

   - **If FALSE (Existing Publication Re-observed):**
     - Action: **SharePoint - Update item**
     - `Id`: `@{first(body('Get_items')?['value'])?['Id']}`
     - Fields:
       - `LastObservedUTC`: `@{utcNow()}`
       - *(Preserves existing `FirstObservedUTC`, `ReviewStatus`, `ReviewNotes`, and manual facility overrides intact).*

---

## 3. Human Review & Power BI Refresh Lifecycle

1. **Human Triage:** Library staff open the `Needs Review` view in SharePoint / Microsoft Lists. They check ambiguous papers and toggle `ReviewStatus` to `Included` (or `Excluded`).
2. **Power BI Model Loading:** Power BI connects directly to the SharePoint List using `powerquery/SharePointPublicationRegistry.m`. It automatically excludes records marked `Excluded`.
3. **Speed & Reliability:** The dataset refresh takes seconds rather than 12+ minutes because it is reading clean tabular rows rather than parsing raw XML across hundreds of HTTP calls.
