# Deferred source enrichment and reconciliation

## Microsoft connector and contextual-source selection — 13 October 2026

Incorporated at the user's request. These are planned source routes, not evidence
of enabled tenant connections or new access authority. Finish the current accepted
source/archive/consumer path first. Prefer approved existing internal registers
before adding another external aggregator; actual register identities and permission
proof stay in the existing S02 configuration and private receipts.

| Priority / information | Planned source and Microsoft route | Useful retained evidence / admission boundary |
| --- | --- | --- |
| First internal slice: projects, awards and investigator links | Existing approved research/grants SharePoint lists and Excel tables, using [SharePoint](https://learn.microsoft.com/en-us/connectors/sharepointonline/) / [Excel Online Business](https://learn.microsoft.com/en-us/connectors/excelonlinebusiness/) standard connectors | Local project/award IDs, investigators, statuses and source dates missing from public sources. Qualify the exact list/file and audience. Excel row actions require a table; retain the original workbook and prepare a separate structured copy when needed. File acquisition and parsing are separate supported operations. |
| First identity slice: internal researcher profiles | [Office 365 Users](https://learn.microsoft.com/en-us/connectors/office365users/) standard connector, initially approved exact-ID lookups | Explicitly selected ID/name/department/job title/office fields only when authorised and necessary. No tenant-wide directory harvest or default full profile. Internal employment/directory assertions remain dated separate evidence; scholarly attribution uses existing exact identifiers and exception policy. |
| Supporting organisation/team context | Approved organisational SharePoint register; [Office 365 Groups](https://learn.microsoft.com/en-us/connectors/office365groups/) standard connector only for selected groups | Group identity/membership and approved unit mappings. A group is not automatically an organisational unit, and membership is not proof of employment, affiliation or project investigator status. Preserve source namespace and effective/observed dates. |
| First contextual slice: regional population/geography | [ABS APIs](https://www.abs.gov.au/statistics/application-programming-interfaces-apis) or official file releases, through a qualified existing Microsoft Web/HTTP route or staged approved files | Region codes, population and statistical geography edition; preserve period, units, suppression and geographic vintage. Use accepted region-code crosswalks. Organisation mailing address, study site and service catchment are different concepts. |
| Low-cost discovery where an official feed exists | [RSS](https://learn.microsoft.com/en-us/connectors/rss/) standard connector | Funding/publication announcements with feed/item identity and observation time. Verify the actual official endpoint and retained fields. Feed projection/history limits remain explicit; complete payload retention may need an existing qualified Web/API acquisition alongside the feed connector. |
| Optional Australian legal-entity context | [ABN Lookup web services](https://abr.business.gov.au/Tools/WebServices), HTTP/custom route after registration/terms qualification | Legal entity/ABN/ACN/name/status context for funders and partners. Complements ROR rather than replacing research organisation identity; exact ABN match preferred. Credentials/permissions and costs must be qualified for the exact route. |
| Optional biomedical metrics | [NIH iCite API](https://support.icite.nih.gov/hc/en-us/articles/9513563045787-Bulk-Data-and-API), HTTP/custom route | PMID-based provider-specific bibliometric observations, only for a measured metric gap. Preserve metric definitions and observation dates; do not combine overlapping provider counts or infer individual research quality. |
| Optional related research outputs | [Zenodo Records API](https://developers.zenodo.org/), HTTP/custom route | Known DOI-related datasets/software and deposited metadata, version and relation direction. Reuse DataCite overlap before another collector. Record/file licences differ; no upload/publish or blanket file download. |
| Conditional geocoding | [Azure Maps connector](https://learn.microsoft.com/en-us/connectors/azuremaps/), currently Standard / Preview | Site/address coordinates and confidence only when an actual location-resolution gap exists. Requires an Azure Maps subscription key; connector tier does not establish free service use. Existing provision/budget/rights first, no subscription creation or personal-address processing. |

### Connector qualification and proportional implementation

A public free API does not imply a free Power Automate integration. General HTTP
and custom routes need applicable premium/custom-connector entitlement; verify
actual action classification, licence, DLP, region, connection owner and endpoint
before selection. The [licensing guidance](https://learn.microsoft.com/en-us/power-platform/admin/powerapps-flow-licensing-faq)
is distinct from the provider's price and terms. Microsoft service-specific HTTP
actions are scoped to supported service endpoints, not public-API proxies. An
existing qualified Power Query Web/source-processing route is an alternative
when it provides the needed native acquisition; it is not a licence workaround.
Copilot connectors, Power Query connectors and Power Automate connectors are
separate capabilities; installed chat plugins do not deploy a tenant connector.

Select one source that closes a named dependency. Read its schema and intended
native target, retain complete authorised source fields in protected staging,
then produce the smallest Microsoft mapping/update and scoped rollback. For
internal profiles, minimise the approved acquisition fields before raw retention;
no sensitive workforce rows in Git, external providers or alternate development
accounts. Exact-ID source links and documented uncertainty precede subject views.

Adopt the OpenAlex failure contract for each new native source path: finite retries,
respect Retry-After, stop unchanged access denial, preserve raw failed-generation
status and last-good consumers, reject partial paging/schema drift, commit last,
and distinguish a real empty result from failure. Directory permission withdrawal
also needs an explicit retention/disposal decision; a transient outage is not
permission to delete accepted records or keep revoked access indefinitely.

Owned preparation: projects/activity under T11-H03/H04; funding source qualification
under G02 then G04; researcher/organisation mapping under existing author design
and T11/G06 integration. ABS is a supporting geography mapping for a named consumer,
not a new dashboard milestone. Shared schemas/catalogues, native writes and active
checkpoint remain coordinator/object-owned. Optional ABN/iCite/Zenodo/Azure Maps
stay deferred unless they close a demonstrated gap. No new chats or feeds launched.

## Selected credential and implementation update — 13 October 2026

The user now permits the selected free credentials supplied in this chat;
the earlier keyless-policy deferrals below are historical selection boundaries.
OpenAlex keyed access and a bounded three-DOI local raw-response preparation are
verified. OpenCitations responded successfully to a token-bearing request, without
independent token-validation proof. CORDIS remains widget-only/unqualified for
extraction. OpenAIRE now has a supplied token in Keychain and one successful
Graph V3 token-bearing read (HTTP200); refresh handling and source admission
remain open. No additional provider/key,
paid usage or native deployment follows automatically.

Use the [current credential/failure policy](KEYLESS_ENRICHMENT_PLAN.md#current-free-credential-policy-and-failure-handling--13-october-2026).
API outages must retain last-good enrichment and explicit source status; do not
turn a failure into zero citations, missing funding or an empty successful batch.
The implemented evidence applies to OpenAlex local preparation; require separate
native readback/failure evidence for each selected Microsoft runtime adapter.

## Free API coverage review — 13 October 2026

We are not using every relevant free API, and the available evidence does not
establish that all existing adapters are active native feeds. The earlier
shortlist remains valid. This second official-documentation review adds the gaps
below; it is broad coverage of relevant infrastructure, not a claim of an
exhaustive global census. API availability, price, permission to reuse data,
privacy, local implementation and native acceptance are separate facts.

| Area / additional source | Added value and documented access | Decision / existing work owner |
| --- | --- | --- |
| Cross-domain: **OpenAIRE Graph** | [V3](https://graph.openaire.eu/docs/apis/graph-api/) exposes research products, organisations, projects and persons. [Terms](https://graph.openaire.eu/docs/apis/terms/) allow free anonymous/authenticated use and CC-BY reuse; rate limits differ. V4 is beta. | T11/G06 candidate after existing-source comparison; use stable V3 and exact identifiers, cursor paging for large sets, retain attribution and asserted links. Aggregation is not independent corroboration of an upstream source. |
| Award links: **NIH RePORTER** | [Public API](https://api.reporter.nih.gov/) supports project and publication searches, including PMID/project-number links; documents a one-request-per-second recommendation, paging limits and CLI examples. | G02/G04/G06: bounded existing-PMID/award lookup when relevant, preserving fiscal-year/application versus core-project identity. Awards are not open opportunities; eligibility and reuse details still need source admission. |
| Funding opportunities: **Grants.gov** | Official [search2 API](https://www.grants.gov/api/common/search2) explicitly requires no authentication and returns opportunity search results. | G02/G04: conditional international coverage. Qualify detail retrieval, pagination, deadlines, foreign-organisation eligibility and reuse; US listing alone never proves CHHHS eligibility. No application/subscription actions. |
| Funding/project context: **UKRI Gateway to Research** | [Official guide](https://www.ukri.org/publications/gateway-to-research-guide/a-guide-to-gateway-to-research/) documents public project/people/organisation/output data, quarterly releases and APIs, but explicitly calls the API unsupported. | Conditional G02/G06 exact-award context; preserve release date, avoid name-based affiliation assumptions and new critical-runtime dependence on an unsupported route. |
| EU project/award context: **CORDIS** | [Data Extraction API](https://cordis.europa.eu/about/dataextractions-api) is free but requires an account/API key and enforces limits. | Conditional G02/G06, currently excluded from automated use by keyless policy. Select only for a relevant EU award/project gap; a permitted versioned export may bootstrap later. |
| Citation relationships: **OpenCitations** | [Official quickstart](https://github.com/opencitations/oc_docs/blob/main/docs/api/quickstart.md) documents anonymous Index/Meta access and an optional free token. | Optional T11 enrichment using exact DOI/PMID, dated provider-scoped observations; never sum counts from overlapping providers or infer research quality from counts. |
| Journal/OA context: **DOAJ** | [Terms](https://doaj.org/terms/) make journal/article metadata CC0 and expose API, OAI-PMH and dump routes. API documentation retrieval failed in this review, so exact limits/schema remain unqualified. | Optional T11 exact-ISSN/DOI context; journal listing is not a quality guarantee or permission to copy full text. Reuse Europe PMC overlap before adding ingestion. |
| Preprints: **bioRxiv/medRxiv** | [Provider API](https://api.biorxiv.org/) documents metadata, date/cursor retrieval and published-paper links. | Optional T11/projects only if preprints are selected scope and existing Europe PMC misses required fields. Preserve server, version and preprint/published relation; do not count versions as independent papers. Confirm chosen content rights separately. |
| Repository coverage: **CORE** | [Official FAQ](https://core.ac.uk/faq) search evidence says API access is free without registration, subject to limits; direct FAQ/API-page reads failed in this review. | Conditional T11 candidate only: verify actual v3 route, terms and limits before adoption. Do not rely on older claims that all use requires a key or assume metadata licences cover full text. |
| Author/paper/citation enrichment: **Semantic Scholar** | [Provider API](https://webflow.semanticscholar.org/product/api) includes keyed endpoints/higher-rate access. [Dataset/API licence](https://api.semanticscholar.org/license/) has substantive use restrictions. | Conditional T11/author-design candidate; verify chosen endpoint's key approval, cost and applicable licence for organisational retention/redistribution. No blanket free institutional-use claim. |

### Coverage across the requested entities

- Publications: retain PubMed/DoRA first; reuse Crossref, OpenAlex and Europe PMC;
  select DataCite and retraction/update relations next. DOAJ, OpenCitations,
  CORE, Semantic Scholar and preprint endpoints require measured added value.
- Researchers: reuse deposited ORCID and source author identifiers/affiliations;
  qualify direct ORCID or OpenAIRE only for missing evidence. Public profiles are
  not an authoritative staff roster; private workforce data is outside scope.
- Organisations: ROR plus existing source organisation assertions; preserve
  historical names, parent/child relationships and funder identifiers separately.
- Projects/research outputs: DoRA activity first, then scoped ClinicalTrials.gov,
  permitted ANZCTR exports and DataCite; OpenAIRE adds cross-source relationships.
- Funding: ARC, NHMRC and MRFF award evidence; NIH/UKRI/CORDIS when an actual
  international award warrants them. GrantConnect remains the existing Australian
  opportunity authority without a qualified public API; Grants.gov is a distinct
  international opportunity candidate. ARDC RDA remains a conditional local
  project/grant/data route, not interchangeable with ARDC RLA.

### Keyed access: cost and eligibility

| Provider | Is a key/token free? | Remaining boundary |
| --- | --- | --- |
| OpenAlex | [Yes](https://help.openalex.org/api/authentication/); [pricing](https://help.openalex.org/access/pricing/) currently gives a free account $1/day API budget without a payment method | Higher usage costs money; anonymous access also exists with a smaller budget. No automatic purchase/top-up; data openness does not make serving unlimited. |
| OpenAIRE | [Yes](https://graph.openaire.eu/docs/apis/terms/), authenticated and anonymous API use are free; documented limits are currently 7,200/hour and 60/hour respectively | Registration and token lifecycle for higher limits; CC-BY attribution. Recheck limits at implementation and account for all clients sharing a quota. |
| CORDIS | [Yes](https://cordis.europa.eu/about/dataextractions-api), but a registered API key is required | Terms and quotas apply; above-limit service can require additional agreement/charges. Current keyless policy blocks this automated route. |
| ORCID | [Public API licence](https://info.orcid.org/public-client-terms-of-service/) is royalty-free for permitted non-commercial use | Individual credential and organisational-use eligibility must be checked; member functionality/extensive use can involve fees. Public data-file reuse is a separate route. |
| OpenCitations | [Optional token is free](https://opencitations.net/accesstoken/); current quickstart supports anonymous use | Use current endpoint/header documentation; no registration needed for initial anonymous qualification. |
| Semantic Scholar | No paid plan prerequisite established by this review; keyed access is subject to request/endpoint rules | Free research tooling is not proof of unrestricted institutional API retention rights; verify cost/approval and exact API/dataset licence before selection. |
| ARDC RDA / RLA | Not established for the exact proposed route and organisational arrangement | RDA [Research Activities API](https://documentation.ardc.edu.au/rda/research-activities-api) and other RDA services differ from RLA; verify access, credentials and fees individually. |
| Scopus / Web of Science / Dimensions | A developer key or limited free access does not establish entitlement to the required dataset | Keep the existing excluded/restricted status unless exact institutional API entitlement and permitted use are verified; no subscription assumed. |

Free-with-key candidates remain conditional under the existing keyless policy;
this review does not register accounts, accept agreements or change that policy.
If the user later allows free credentials, prefer no-payment-method tiers, bounded
quotas and already approved institutional credential storage, with no paid fallback.
Microsoft connector/runtime licensing is a separate check even for a free provider.

### Integration decision and acceptance

Use the existing source catalogue/Conductor evidence, not another registry.
For a selected source record: intended consumer and gap, exact endpoint/version,
anonymous/key/account requirement, cost ceiling, permitted raw retention and
redistribution, request budget, bootstrap/incremental route, source IDs, full
returned field inventory, paging and freshness/deletion limits. Compare a bounded
accepted identifier set against existing providers before promotion; reported
incremental coverage must come from actual evidence, not these recommendations.
No live API payload collection or source admission was performed for this review.
One coherent source adapter and native consumer path is the unit of delivery.

## Additional-source discovery — 13 October 2026

Official documentation was searched and compared with the existing source and
grants catalogues, author design and local enrichment adapters. This is a bounded
source-discovery assessment, not an exhaustive census or a native integration
claim. No source was enabled, credentials registered, agreement accepted, support
message sent or business-record harvest run. Priorities below are recommendations
for selection after the current shared-data path is accepted; already authorised
current-source field retention continues under T11/E01.

### Recommended additions and refinements

| Priority / source | Added value and vertical | Documented acquisition / rights boundary | Smallest useful integration and existing owner |
| --- | --- | --- | --- |
| First shortlist: **ROR** | Shared organisation/funder identifiers, names, status and relationships supporting all verticals | [Registry is CC0](https://ror.org/); [v2 REST API](https://ror.readme.io/docs/rest-api) and data dump. The [client-ID page](https://ror.readme.io/docs/client-id) currently says registration is paused and ID-based limits are not enforced during that pause; recheck at adoption. API defaults to active organisations and has a result ceiling. | Resolve a bounded set of existing organisation IDs/aliases, retain full records including nulls, include inactive/predecessor evidence when needed. Matching is candidate evidence, not employment proof. Existing author/organisation design and T11 retention; use a dump only if scale justifies it. |
| First shortlist: **Crossref Retraction Watch extension** | Publication correction/retraction provenance beyond ordinary bibliographic fields | [Crossref](https://www.crossref.org/documentation/retrieve-metadata/retraction-watch/) exposes Retraction Watch updates through REST and a downloadable CSV; retain source attribution and the chosen dataset's current reuse terms. Corrections/expressions of concern are less comprehensive than retractions. | Reuse the existing Crossref adapter and exact DOI matches; retain update relationships/status separately, preserving the original publication and notices. T11/E07; no automatic deletion or publication-count inflation. |
| First shortlist: **DataCite** | Dataset/software/other research-output metadata, DOI relationships, creators, ORCID/ROR and funding references | [Public REST retrieval](https://support.datacite.org/docs/api) needs no authentication; [public metadata files](https://support.datacite.org/docs/datacite-public-data-file) are CC0. Linked content has separate rights. [Full metadata options](https://support.datacite.org/docs/api-queries) require explicit affiliation/publisher parameters; detail adds further attributes. | Start with DOI relationships already present in accepted records. Preserve resource type and relation direction; datasets are not publications. Shared T11 retention and later projects/researcher consumers. No whole-corpus download by default. |
| Next projects slice: **ClinicalTrials.gov** | Registered study identity, status, sponsor/site context and publication links; strengthens projects/activity rather than inferring trials from text | NLM documents a [public REST/JSON v2 API](https://www.nlm.nih.gov/pubs/techbull/ma24/ma24_clinicaltrials_api.html). Current API/terms pages returned only application shells in this review, so current quota, full schema and reuse conditions remain to verify. | Start with exact NCT identifiers already present, qualify the current schema and preserve complete scoped records. Crosswalk registry aliases rather than counting each registration as a separate project. T11-H03/H04 and existing relationship design; registry listing is not local governance approval. |
| Next projects slice, assisted route: **ANZCTR** | Australian/New Zealand trials and local recruitment context; ACTRN identity and links to other registrations | Current [FAQ](https://www.anzctr.org.au/Faq.aspx) documents Excel downloads, superseding older XML-only guidance. [Terms](https://www.anzctr.org.au/Support/Terms.aspx) restrict unauthorised collection software and require attribution, currency, processed date and modification disclosure for permitted reuse. | Use permitted export intake after rights/refresh qualification; do not invent or reverse-engineer an API. Retain complete workbook and schema, then project trial records. T11-H03/H04. ANZCTR also displays regional ClinicalTrials.gov records, so those are overlapping evidence. |
| Next funding slice: **NHMRC award datasets** | Authoritative health-research award context, distinct from funding opportunities and publication acknowledgements | [Official statistics/data](https://www.nhmrc.gov.au/funding/outcomes-and-data-research/research-funding-statistics-and-data) provides annual snapshots and a dictionary; page reports update on 25 March 2026. Select the grant-level workbook, confirm its fields/licence and preserve its vintage. | Bootstrap a versioned official-file import through existing storage, with grant IDs and administering institution. G02/G04/G06. Aggregate disease-topic amounts can overlap and must not be summed as unique grant totals. |
| Next funding slice: **MRFF grant recipients** | Australian health-research awarded projects, grant identifiers, recipients, dates and values | [Official dataset](https://www.health.gov.au/resources/publications/medical-research-future-fund-mrff-grant-recipients) offers Excel and PDF. Published 27 August 2026, data as at 10 July 2026, excluding media-embargoed awards. Confirm workbook licence/reuse at selection; no API established here. | Prefer complete official Excel file over PDF extraction; retain workbook plus table/field provenance. G02/G04/G06; reconcile grant/agency IDs against GrantConnect and publication acknowledgements without treating them as independent awards. |
| Conditional local coverage: **ResearchOnline@JCU** | JCU research outputs potentially missing from existing publication sources; useful local overlap/gap evidence | [Repository information](https://researchonline.jcu.edu.au/information.html) describes its reviewed deposits. The [repository policy page](https://researchonline.jcu.edu.au/policies.html) currently has no defined policies; [JCU procedure](https://www.jcu.edu.au/policy/academic-governance/research-management/researchonline-procedure) distinguishes metadata from restricted full text. Bulk endpoint/reuse remains unqualified. | First assess a small set of known missing DOI/handle records through permitted access. Require actual CHHHS attribution rather than importing every JCU record. T11 source qualification; full-text download is separate. |
| Conditional OA gap: **Unpaywall** | DOI-based OA locations, versions and per-location licence evidence | [Data format](https://unpaywall.org/data-format) describes location/version/licence fields. The [API page](https://unpaywall.org/products/api) was JavaScript-only to this reader; current identification, quota and data-use terms were not verified. | Assess only if existing Europe PMC/OpenAlex coverage leaves a measured OA gap. Retain location evidence, not an assumed licence to download every linked article. Existing enrichment work; no new integration on this evidence alone. |
| Conditional researcher route: **ORCID direct data** | Public researcher identifiers, works and affiliation assertions with provenance | [Public API terms](https://info.orcid.org/public-client-terms-of-service/) distinguish individual credentials and allowed use; do not infer organisational entitlement. The [public data file](https://info.orcid.org/privacy-policy/) is CC0, with privacy/community-use considerations. | Prefer ORCIDs already deposited with source works. Qualify institutional member access or a justified public-file route separately. Never assign a person from name alone or infer current employment. Existing author/organisation design; no writeback or account registration. |
| Conditional Australian dataset/activity context: **Research Data Australia** | Collections, parties and activities complementary to Research Link Australia | [ARDC web services](https://documentation.ardc.edu.au/rda/web-services) and [getMetadata](https://documentation.ardc.edu.au/rda/getmetadata-api) document a key-bearing route. RDA and RLA are different services; this review does not establish API entitlement or record-level reuse. | Reuse DOI/organisation/activity identifiers from accepted data, select one demonstrated relationship gap and qualify access. T11 source qualification / existing ARDC extension. Under current keyless policy, retain as conditional or link-only. |

### Existing sources: reuse before adding another adapter

- **Europe PMC is already represented in local code**, including
  `scripts/enrich_europe_pmc.py`; it is not a newly discovered provider.
  Its [REST documentation](https://europepmc.org/RestfulWebService) distinguishes
  default lite results from core metadata. Audit full core response retention
  before writing a second collector. Publication/grant links are source evidence;
  API software licensing is not a blanket licence for article text.
- **Crossref and OpenAlex already have local adapters.** Current OpenAlex
  [authentication](https://help.openalex.org/api/authentication/) and
  [pricing](https://help.openalex.org/access/pricing/) describe limited anonymous
  usage and a larger free keyed budget. The old 100,000-request keyless/polite-pool
  assumption is retired. Keep keyless policy and actual source limits explicit;
  do not register an account or buy credits automatically.
- **ARC, Queensland Grants Finder/QGIP, university calendars and GrantConnect**
  already appear in local funding planning/catalogues. NHMRC/MRFF award files
  extend award evidence, not open-opportunity intake. Finance confirms
  [GrantConnect's official role](https://www.finance.gov.au/individuals/find-grant-grantconnect),
  but this search did not establish a supported public API. Existing permitted
  import/interface-verification decisions remain; HTML search results are not
  an API or reusable institutional entitlement.
- Dimensions, Scopus and Web of Science remain conditional under their existing
  entitlement/reuse gates. Do not duplicate their records through aggregators
  and claim independent corroboration or automatically enable paid sources.

### Selection and bootstrap rule

Recommended first shortlist is ROR, the existing Crossref update/retraction
path, and DataCite; projects then evaluates ClinicalTrials.gov/ANZCTR, while
funding evaluates NHMRC/MRFF award snapshots. This is a recommendation based on
entity/field value and documented routes, not a measured coverage ranking.
For each selected source, record incremental known-key coverage/field fill,
false links, upstream overlap, operation cost, rights and maintainability using
a small agreed benchmark before wider collection. Keep every raw field actually
returned, while explicitly requesting documented full-metadata modes; a default
API response is not necessarily all fields the source can provide.

Use the existing T11/E01 raw archive and source adapters, then typed vertical
projections. Bootstrap with exact-ID lookups or authorised official files;
retain file bytes, schema, version/as-of date, retrieval time and licence record.
Native Microsoft acquisition/retention and replay must work before a source is
marked enabled. No new runtime, resource catalogue or commissioning track.
Implementation remains subject to the current-source completion and existing
post-MVP/access gates; this discovery does not interrupt the publications owner.


Plan amendment requested 2026-09-14. Status: planned, not enabled. This extends the existing Power Platform-native dashboard after the PubMed/DORA foundation is properly set up; it does not delay or replace its acceptance criteria. Keep the existing Power BI workspace, retained storage and current approved report scope. No new source collection, account registration, access application, purchase or deployment is authorised by this planning amendment.

## Start gate and order

- [ ] Finish T11–T15 foundation: committed retained history, full metadata reconstruction, conservative canonical identities, the current approved rendered report pages, complete CSV/HTML outputs and a validated monthly automation dry run.
- [ ] Prove successive refresh cycles, exact refresh/batch correlation, idempotent replay, DORA rollover, interrupted writes, incomplete exports and continued operation under ongoing licence rights. Retain review decisions and the last good report state.
- [ ] Resolve the existing publishing/schedule/delivery approval gates separately. A withheld delivery approval must not be interpreted as technical failure or permission to enable it.
- [ ] Once the foundation is accepted, implement OpenAlex and Crossref enrichment first, ARDC research-activity context second, and Dimensions only within documented free/reuse entitlements. Each source is independently optional and can be disabled without breaking the accepted two-source baseline.

## Earlier source roles and dated access evidence

Documentation checked 2026-09-14; verify again when implementation starts. Free provider access and Power Platform connector execution rights are separate questions.

| Source | Intended added value | Access and fallback |
| --- | --- | --- |
| OpenAlex | Broader publication discovery; work/author/institution identifiers; topics, open-access locations and reference/citation relationships where supplied. Use institutional candidates to identify possible coverage gaps, not as conclusive CHHHS affiliation evidence. | Public API has a small anonymous allowance; a free account/key currently supplies $1/day usage, with no payment method required. Configure a strict free-budget ceiling, caching and resumable bounded queries; do not buy credits automatically. Prefer exact DOI lookups before wider discovery. Recheck current request costs, limits and data/content rights. |
| Crossref | DOI resolution and publisher-deposited bibliographic enrichment; publication-date variants, funders/awards, ORCID/ROR, licences and update/retraction relationships where deposited. | Public REST API requires no sign-up. Follow documented rate-limit headers/backoff and polite-pool guidance. Metadata availability varies; abstracts may carry separate copyright. Do not assume a DOI guarantees complete affiliations, references or full text. |
| Scopus (Elsevier) | Comprehensive multidisciplinary citation index; author Scopus IDs, standardized affiliation profiles (AF-ID), and verified citation counts. | Requires institutional subscription or Elsevier Developer API key. For Queensland Health, verify whether existing institutional library entitlements permit API-based metadata harvesting or whether scheduled CSV exports via Scopus web interface should be used as the ingestion fallback. Never store proprietary full-text or raw XML beyond permitted metadata fields. |
| Web of Science (Clarivate) | Authoritative core collection indexing; Clarivate ResearcherID, journal citation indicators, and funding acknowledgment parsing. | WoS Starter API or Expanded API requires institutional access keys. Fallback route: structured manual/scheduled RIS/BibTeX/Excel exports ingested through the SharePoint staged file intake. Citation counts isolated in `CitationCount_WoS`. |
| ARDC research activities — provisional mapping to Research Link Australia (RLA) | Link publications to Australian researchers, organisations and funded activities; retain project/grant identifiers, relationships and provenance as contextual entities. | The supplied Google redirect could not be resolved. RLA is the likely intended service based on its research-activities scope; confirm the exact service before implementation. Official RLA documentation requires authentication, an access request and a signed service schedule. Verify no-cost eligibility and permitted organisational reuse; do not assume anonymous API access or execute an agreement. If the intended service is Research Data Australia, assess its collection/activity records and API separately. Where API rights are unavailable, use permitted reference links or explicitly assisted imports only. |
| Dimensions — freely accessible aspects only | Additional publication/dataset discovery and contextual citation information where the free service actually exposes it and permits reuse. | The free web application is for personal, non-commercial use. Analytics API access normally requires an institutional subscription; eligible scientometric projects can apply for free access, which is not established for this operational dashboard. First verify permitted organisational use, export fields/limits, retention and redistribution. Use only expressly permitted exports or link-outs; no scraping substitute for API rights. Leave automated ingestion disabled if no suitable free entitlement exists. |

Citation counts and grant information are optional source-attributed context, not new headline performance metrics. Do not add impact rankings or grant KPIs without a separate scope decision. Activities, grants, datasets, authors and organisations must never increase publication counts merely because a provider returns them. Each citation counter is recorded independently (`CitationCount_Scopus`, `CitationCount_Crossref`, `CitationCount_OpenAlex`) to preserve scientometric validity without false equivalence.

## SearchRight reuse review

Reference: [SearchRight](https://github.com/edithatogo/searchright), reviewed main revision `e1f78ecf3467a88fc95523c53babb503fb3921ef`.

Its [provider contract baselines](https://github.com/edithatogo/searchright/blob/e1f78ecf3467a88fc95523c53babb503fb3921ef/integration/provider-contract-baselines.json) include PubMed, Europe PMC, Crossref and OpenAlex, with endpoint/parser/fixture mappings and `live_canary_status: not_executed`. Reuse ideas for provenance, pagination, response-shape checks and provider failure handling after code/licence review. Do not interpret fixtures or listed providers as production integrations. Keep Rust/CLI orchestration out of the hosted runtime: translate appropriate contracts into native Power Query/Power Automate implementations. Europe PMC has since acquired a local adapter; inspect that implementation and native evidence before further work. This historical review does not prove live acceptance.

## Implementation work packages

### 1. Capability and feature comparison

- [ ] Inventory SearchRight provider contracts and parsers at a pinned revision; record which added fields genuinely improve PubMed/DORA coverage or quality and which merely repeat their upstream data.
- [ ] Confirm the intended ARDC service, current schemas, source licences, quotas, keys, export/redistribution rights and organisational eligibility. Record API availability separately from website availability and from local connector availability.
- [ ] Build a representative benchmark from accepted canonical records, DORA-only records, missing-DOI records and reviewed ambiguous cases. Measure incremental records, metadata fill rates, conflict rates, affiliation evidence and cost/request budgets before choosing bulk queries.
- [ ] Checkpoint: review the source-by-source benefit and access matrix; unavailable optional sources do not block the base dashboard.

### 2. Native adapters and retained provenance

- [ ] Define per-source schemas, persistent IDs, parser versions, query scope, retrieval time, licence/attribution, completeness flags and immutable raw observations before implementation.
- [ ] Implement OpenAlex and Crossref in isolation using cloud-compatible Power Query Web.Contents with stable origins, bounded pagination and caching; retain through the proven standard Power BI and OneDrive/SharePoint path where supported. Verify secure key handling and cloud refresh without embedding secrets in source or exports.
- [ ] Use direct Power Automate HTTP/custom connectors only if current assigned licences and tenant rules permit. If neither native route executes, classify the source as assisted/unavailable; do not introduce a Fabric trial or external hosted runtime as an implicit dependency.
- [ ] Add ARDC and Dimensions adapters only after their access/reuse gates pass. Preserve a documented link-only or approved-file-import fallback and expose its refresh limitations.
- [ ] Checkpoint: native canaries, quota/429 handling, schema drift, pagination termination, exact retained-file readback and independent key-set checks for each source.

### 3. Canonical reconciliation and enrichment

- [ ] Preserve existing canonical IDs and reviewed aliases. Match exact normalized DOI/PMID first; retain provider IDs as source aliases, not new canonical IDs. Conflicting identifiers and fuzzy title/author/year matches require review. A source addition cannot undo an existing exclusion or merge decision.
- [ ] Separate discovery candidates from accepted publications. Require the same CHHHS scope/affiliation evidence as the baseline; author identity or broad institution matching alone is insufficient.
- [ ] Keep field-level source, observed time, original value, selected value and conflict reason. Define explicit per-field precedence, preserve raw publication dates and precision, and never replace a known value with an absent enrichment field.
- [ ] Keep citation counts by provider and observation date; do not sum incomparable counts. Record upstream lineage so multiple aggregators are not mistaken for independent corroboration.
- [ ] Model Activity, Dataset, Organisation and Author relationships separately, with typed IDs and evidence-bearing links to publications. Preserve missing/uncertain links and per-record reuse conditions.
- [ ] Checkpoint: replay, conflict, false-affiliation and multi-source-duplicate tests; exact canonical key sets reconcile before/after, with every addition/removal explained.

### 4. Reports, exports and operations

- [ ] Extend Source Reconciliation within the current approved report design: source presence/overlap, incremental candidates, conflicting fields, coverage limits, last successful collection and unavailable/stale sources. Keep publication headlines canonical-key based.
- [ ] Extend full CSV/HTML export contracts deliberately for approved enrichment fields; provide separate relationship exports for one-to-many activities/identifiers when necessary. Preserve the full bibliography, field provenance, dates and attribution without row multiplication.
- [ ] Make optional-source refresh failures visible while retaining last accepted enrichment and the functional PubMed/DORA baseline. Quota exhaustion is a source-status event, never zero publications or permission to spend.
- [ ] Revalidate monthly output completeness, native rendering, runtime/licence rights and approved schedule/delivery scope. Obtain any new agreement, publishing or delivery approval only when the proposed change is concrete and reviewable.
- [ ] Checkpoint: end-to-end native dry run, exact output key/field parity, rollback and disable-one-source rehearsal before release.

## Official references

- [OpenAlex API](https://help.openalex.org/api/), [pricing](https://help.openalex.org/access/pricing/) and [operation costs](https://help.openalex.org/access/example-costs/).
- [Crossref REST API and reuse notes](https://www.crossref.org/documentation/retrieve-metadata/rest-api/).
- [Dimensions free version](https://www.dimensions.ai/products/all-products/dimensions-free-version/) and [Analytics API access](https://docs.dimensions.ai/dsl/api.html).
- [ARDC Research Link Australia](https://ardc.edu.au/services/ardc-research-link-australia/), [API access requirements](https://documentation.ardc.edu.au/rla/for-rla-api-users-how-to-access-and-reuse-rla-data) and [Research Data Australia scope](https://documentation.ardc.edu.au/rda/introduction).
