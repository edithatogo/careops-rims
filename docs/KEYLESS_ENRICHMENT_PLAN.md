# Free API Enrichment Plan: CHHHS Research Publications

## Current free-credential policy and failure handling — 13 October 2026

The user has authorised the recommendations and supplied OpenAlex, OpenCitations
and CORDIS widget credentials. This supersedes the older blanket zero-key/account
constraint for these selected free services. No paid subscription, top-up or
unqualified API is authorised. OpenAIRE developer sign-in and one token-bearing Graph V3 request are
confirmed (HTTP200, valid JSON, one result); a supplied short-lived token is in
Keychain. Routine refresh credentials remain unqualified. CORDIS widget credentials
do not qualify the extraction API. Existing API/source admission and Microsoft native gates still apply.

Provided credentials are held in macOS Keychain as `chhhs-rims.openalex`,
`chhhs-rims.opencitations`, `chhhs-rims.cordis-widget` and
`chhhs-rims.openaire` under account `rims`.
Names are public configuration; values never belong in source, logs, query URLs,
fixtures or receipts. The OpenAlex adapter accepts `OPENALEX_API_KEY` from a
process environment, otherwise reads the named Keychain item. This is local
preparation credential handling, not a deployed Microsoft connection. Keep
credential transfer into Microsoft under the existing supported secure connector
configuration/ownership path; no plaintext key in flow/model definitions.

The selected preparation entry is `scripts/prepare_openalex_enrichment.py`:

```sh
python3 scripts/prepare_openalex_enrichment.py \
  --input private/ops/<reviewed-record-snapshot>.json \
  --output private/ops/<new-enrichment-candidate>.json --limit 3
```

Inputs are a frozen publication-record list with DOI values, taken from an
accepted source slice with its separate acceptance/provenance receipt. Output is
an exclusive owner-readable private candidate, never a source overwrite. Complete
raw OpenAlex response bytes/payload, SHA256, exact DOI match, attempts/status and
observation time accompany derived fields. Unknown raw fields and nulls survive.
A successful non-null enrichment may update the candidate; failed/not-found
attempts preserve existing values and successful-observation timestamps.

OpenAlex: timeout per request, at most three attempts; only transient transport,
429 and selected 5xx are retried. Respect Retry-After up to the bounded wait;
long waits stop the pass. 401/403, quota/service failures stop further candidate
requests. 404 is not-found, not zero citations; malformed, foreign-DOI and partial
batch responses cannot become accepted enrichment. Authorization is header-only;
redirects are refused. Request/error diagnostics never include credentials or
provider response text. The legacy dictionary/None wrappers remain compatible
but cannot expose every status; use the observation/candidate entry for admission.
The older multi-provider batch runner is not the hardened acceptance route.

Focused OpenAlex tests cover failure preservation, finite retry, rate limits,
malformed data, identity, partial batches, raw fields and candidate overwrite.
A real three-DOI slice from accepted DoRA archived pages completed three successful
OpenAlex responses, retained full bytes and preserved the original snapshot;
private candidate/provenance use prefix `2026-10-13-openalex-enrichment-`.
This proves local live preparation only. Equivalent native provider failure
branches, last-good commit, refresh/consumer binding and operational acceptance
remain open under T11/E01. OpenCitations connectivity worked with its token, but
its anonymous endpoint did not independently validate token identity. No blanket
claim is made for OpenAIRE/CORDIS failure handling before their adapters exist.

## Historical cost review before credential authorisation — 13 October 2026

A required API key does not necessarily imply a fee. OpenAlex, OpenAIRE and
CORDIS have documented free keyed routes; ORCID has purpose/eligibility limits.
See the [cost and access assessment](FUTURE_SOURCE_ENRICHMENT.md#keyed-access-cost-and-eligibility)
for the provider-specific evidence. These findings do not amend the existing
zero-key/account policy below. A future explicit policy change can permit free
credentials selectively without permitting subscriptions, automatic top-ups or
unlimited calls; no accounts or credentials were created by this review.

## Current scope and source-limit correction — 13 October 2026

Keyless refers to optional external enrichment providers, not Microsoft tenant authentication. The older benefits below are design aims, not guarantees of compliance, availability or operational acceptance. Current OpenAlex limits supersede the historical 100,000-request polite-pool assumption. See the [source assessment](FUTURE_SOURCE_ENRICHMENT.md#additional-source-discovery--13-october-2026) for documented candidates and access gaps; discovery does not waive this policy or enable a provider. ACTIVE labels below describe historical intended/local integration, not current native-runtime proof.


Status: **Approved Architecture & Implementation Plan** (2026-09-18)  
Target Environment: **Queensland Health M365 Tenant (`{{TENANT_ID}}`)**
Primary User: **RIMS maintainer (configured privately)**
Current constraint: **Selected free credentials permitted; no paid subscription or automatic top-up**

---

## 1. Historical September keyless mandate

The 18 September design required operation without external API keys, tokens, subscriptions or registrations. The current policy above supersedes that restriction for the selected user-authorised free credentials; this historical rationale does not prohibit their use.

This constraint aims to reduce external-provider credential management; it does not guarantee:
1. **Zero Operational Friction:** No credential rotation, expired tokens, credit card ceilings, or vendor access requests.
2. **Enterprise Cloud Compliance:** Power Automate flows, Power Query transformations, and Python routines run purely over open public protocols with zero secrets stored in the tenant or codebase.
3. **Institutional Longevity:** Ingestion and enrichment remain durable, reproducible, and self-sustaining across staff transitions without institutional account maintenance.

---

## 2. Provider Audit: Keyless vs. Key-Required Matrix

All potential data sources and enrichment providers are audited against the keyless constraint:

| Provider / Source | Access Model | Key / Token Required? | Status in CHHHS Pipeline | Notes / Enforcement |
| :--- | :--- | :---: | :---: | :--- |
| **PubMed (NCBI E-Utilities)** | Public REST API | **NO** | **ACTIVE (Core)** | Standard anonymous access (up to 3 req/sec). Comprehensive biomedical metadata, MeSH, grant lists, clinical trial links. |
| **OpenAlex** | Public REST API with usage budgets | Anonymous use is limited; a key increases budget | Local adapter; native eligibility must be reverified | [Current authentication](https://help.openalex.org/api/authentication/) and [pricing](https://help.openalex.org/access/pricing/) supersede the old keyless quota. Qualify anonymous budget for the actual workload; retain last-good data on exhaustion. No account/key/purchase is implied. |
| **Crossref** | Public REST API (Polite Pool) | **NO** | **ACTIVE (Enrichment)** | Public polite pool header. DOI resolution, publisher-deposited funder registries, award numbers, clinical trial numbers. |
| **Internal Rule Engine** | Deterministic Algorithmic Classifier | **NO** | **ACTIVE (Governance)** | Pure Python / Power Query rule sets running locally and in cloud flows over harvested metadata. |
| **Europe PMC (EBI)** | Open REST API (Keyless) | **NO** | **ACTIVE (Enrichment)** | Keyless open API from EMBL-EBI. Provides PMCID, open-access full-text URLs, author ORCID identifiers, and grant funder linkages. |
| **Dimensions.ai API** | Proprietary REST / DSL API | **YES** | **EXCLUDED** | Automated API access requires an institutional Dimensions Analytics subscription and API token. Excluded from automated cloud ingestion. |
| **Scopus (Elsevier) API** | Proprietary REST API | **YES** | **EXCLUDED** | Requires Elsevier Developer API key (`X-ELS-APIKey`). Excluded from automated cloud ingestion. Staged manual CSV intake only if available. |
| **Web of Science API** | Proprietary REST API | **YES** | **EXCLUDED** | Requires Clarivate API key (`X-ApiKey`). Excluded from automated cloud ingestion. Staged manual CSV intake only if available. |
| **ARDC RLA API** | Authenticated Registry API | **YES** | **EXCLUDED** | Requires institutional access request, registered authentication, and signed service schedule. Excluded from automated ingestion. |

---

## 3. Keyless Funding Architecture & Columns

Publication funding-acknowledgement enrichment in this historical design draws from **OpenAlex, Crossref, Europe PMC, and PubMed**, supplemented by internal deterministic categorization:

```
Harvest Pipeline (Zero Keys):
┌─────────────────────────┐
│ PubMed (GrantList)      │──┐
├─────────────────────────┤  │
│ Europe PMC (EBI Grants) │──┤
├─────────────────────────┤  ├─► [Harmonization & Deduplication] ─► [Rule Classifier] ─► SharePoint / PBI
│ OpenAlex (Grants Array) │──┤
├─────────────────────────┤  │
│ Crossref (Funder Array) │──┘
└─────────────────────────┘
```

### Approved Funding & Governance Columns (Keyless):

| Column Name | SharePoint EntityPropertyName | SharePoint Type | Source / Derivation Method | Value & Operational Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **`PMCID`** | `PMCID` | Single line of text | Europe PMC / PubMed | PubMed Central identifier for direct open-access full-text retrieval. |
| **`AuthorORCIDs`** | `Author_x0020_ORCIDs` | Multiple lines of text (Note) | Europe PMC (`authorList.author[].authorId[type=ORCID]`) | Author persistent digital identifiers for researcher attribution. |
| **`FunderNames`** | `FunderNames` | Multiple lines of text (Note) | OpenAlex, Crossref, Europe PMC, PubMed | Preserves acknowledged funding bodies (NHMRC, MRFF, Emergency Medicine Foundation, etc.). |
| **`GrantIDs`** | `GrantIDs` | Multiple lines of text (Note) | OpenAlex, Crossref, Europe PMC, PubMed | Exact award reference numbers. |
| **`FundingType`** | `Funding_x0020_Type` | Choice | Deterministic Regex Classifier on `FunderNames` | Categorization: Commonwealth (NHMRC/MRFF), State / Qld Health, Philanthropic / Foundation, Commercial / Industry Trial, University Partner, Unfunded / Departmental. |
| **`IsInternalFunding`** | `Internal_x0020_Funding` | Choice (`Yes`, `No`) | Rule Match on Cairns Foundation / SERTA | Quantifies ROI from internal CHHHS research trust funds. |
| **`ClinicalTrialID`** | `Clinical_x0020_Trial_x0020_ID` | Single line of text | Regex (`ACTRN\d{14}`, `NCT\d{8}`) | ANZCTR and ClinicalTrials.gov registry tracking. |
| **`IndigenousHealthFocus`** | `Indigenous_x0020_Health_x0020_Fo` | Choice (`Yes`, `No`) | Rule Classifier on MeSH / Keywords / Title | Tracks First Nations health equity research in Far North Queensland. |
| **`FieldOfResearch`** | `Field_x0020_of_x0020_Research` | Single line of text | OpenAlex (`primary_topic.field.display_name`) | ANZSRC FoR clinical specialty mapping. |
| **`StudyDesign`** | `Study_x0020_Design` | Choice | MeSH / PublicationType classifier | Evidence hierarchy: RCT, Systematic Review, Observational/Cohort, Guideline, Case Report. |
| **`EuropePMC_OpenAccess`** | `Europe_x0020_PMC_x0020_Open_x002` | Single line of text | Europe PMC | Open access status indicator. |
| **`EuropePMC_FullTextURL`** | `Europe_x0020_PMC_x0020_Full_x002` | Hyperlink (URL) | Europe PMC | Direct full-text PDF or HTML link. |
| **`EuropePMC_CitedByCount`** | `Europe_x0020_PMC_x0020_Citations` | Number | Europe PMC | Open Europe PMC citation count. |

---

## 4. Implementation Status

- [x] **Phase 1: Local Rule Engine & Keyless Adapters (COMPLETED)**
  - Created [`scripts/enrich_europe_pmc.py`](../scripts/enrich_europe_pmc.py) with batch query support.
  - Created [`scripts/keyless_classifiers.py`](../scripts/keyless_classifiers.py) for FundingType, InternalFunding, IndigenousHealthFocus, StudyDesign, ClinicalTrialID.
  - Extended [`scripts/enrich_openalex.py`](../scripts/enrich_openalex.py) with batch query and FieldOfResearch extraction.
  - Extended [`scripts/batch_enrich_sources.py`](../scripts/batch_enrich_sources.py). All 1,265 records enriched and cached in under 40 seconds.
  - All 184 unit tests passing.
- [x] **Phase 2: SharePoint List Schema Update & Live In-Place Sync (COMPLETED)**
  - Created 11 new columns directly on `Publication Registry` (`{{SHAREPOINT_LIST_ID}}`) via REST API.
  - Mapped exact `EntityPropertyName` values.
  - Synchronized all 1,265 items in-place using [`scripts/sync_sharepoint_seed.py`](../scripts/sync_sharepoint_seed.py).
- [x] **Phase 3: Executive Reporting & Governance Visuals (COMPLETED)**
  - Updated [`scripts/export_monthly_docx.py`](../scripts/export_monthly_docx.py) to incorporate executive funding governance breakdowns, study design distribution, First Nations health focus counts, and direct PMCID / OA links.
  - Updated [`config/SharePointPublicationRegistry.m`](../config/SharePointPublicationRegistry.m) with complete typed schema.

## Qualified NHMRC identifier routes — 21 October 2026

The optional Python GNT, APP and explicit application-source projectors retain
original identifiers and add evidence edges. They do not merge awards by numeric
suffix, title or investigator similarity.

- `scripts/nhmrc_gnt_crosswalks.py` requires independently bound NHMRC identity,
  pinned RGMS guide/migration evidence and the exact matching registry record's
  historical dates. Nonmatching records sharing an ID cannot supply those dates.
- `scripts/nhmrc_app_crosswalks.py` requires explicit issuer and target-field
  contracts and an externally pinned source catalogue. APP is not a universal
  prefix-stripping rule. Both packet projectors require an independently supplied
  `expected_batch`; obtain it from the operator's selected batch, never by reading
  the untrusted manifest. Changed batch labels fail before evidence is emitted.
- `scripts/nhmrc_remaining_application_sources.py` qualifies explicit institutional,
  publisher and protocol paths. A historical application reference does not
  establish a current registry award. Crossref metrics remain provider-scoped.

The matching model-preparation helpers produce candidates against an exact
accepted evidence-table contract. Preserve the preimage and bindings, inspect the
candidate, and use the existing native owner for any deployment. Repeated
preparation refuses an already-applied marker; it is not a native replay test.

The three M projectors are withheld: their original implementation compares
recorded hashes and byte lengths without hashing the payload read. A same-length
replacement is therefore not rejected by that check. Native integration needs a
qualified actual-byte verification or independently verified immutable readback
contract before promotion. This public port does not repair the existing native
implementation, establish M parity or supply an automatic deployment.

The focused `test_nhmrc*.py` fixtures cover source binding, ambiguous identifiers,
tampering, batch relabeling, same-ID date confusion and preservation. Public
fixtures use example targets; private payloads, deployment profiles and native
receipts are excluded. The port derives from private implementation commits
`b572a120`, `9a3fbcf7` and `03e5d88a`, with the Python review fixes above.
Two MRFF alias pairs still lack explicit equivalence evidence and remain unmerged.
No source flow, report mutation, notification or release replacement is introduced.
