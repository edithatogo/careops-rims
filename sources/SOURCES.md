# Primary-source register

## Current source-discovery reference — 13 October 2026

The [additional-source assessment](../docs/FUTURE_SOURCE_ENRICHMENT.md#additional-source-discovery--13-october-2026) records an official-source search for ROR, DataCite, Crossref Retraction Watch, ClinicalTrials.gov, ANZCTR, NHMRC/MRFF awards, ResearchOnline@JCU, Unpaywall, ORCID and Research Data Australia, with overlap against existing providers. It documents value, API/file routes, rights and unresolved access; candidate identification is not enabled ingestion. Reuse the existing catalogue and raw archive.

The September reference list and runtime statements below are historical; current source completeness and native acceptance require the active task's dated evidence.


Checked 11 September 2026. This records references and implementation use; it is not an archive of complete source pages.

| Source | Used for |
|---|---|
| https://www.cairns-hinterland.health.qld.gov.au/hospitals-and-health-centres | Facility coverage. Search aliases and reporting groups are project decisions, not an official author registry. |
| https://www.ncbi.nlm.nih.gov/books/NBK25499/ | NCBI E-utilities parameters, contact/tool attribution, result limits and batching. |
| https://dora.health.qld.gov.au/qldresearchjspui/feed/rss_2.0/1/849 | Live DORA RSS source for the CHHHS collection. The supplied XML was used only to establish structure and attribution fields; its historic rows are not embedded in production data or fixtures. |
| https://www.data.qld.gov.au/dataset/database-of-research-activity-dora | Queensland Open Data DoRA project/activity resource and CKAN package/datastore API. Its source columns are preserved in the separate DORA Activity Registry; it is not treated as a publication feed. |
| https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-overview | PBIP source-control architecture. |
| https://learn.microsoft.com/en-us/fabric/cicd/git-integration/source-code-format | Fabric Git item structure, `.platform` metadata and source-code formats. |
| https://learn.microsoft.com/en-us/fabric/cicd/git-integration/git-get-started | Browser Git integration workflow and capacity prerequisites. |
| https://learn.microsoft.com/en-us/fabric/admin/git-integration-admin-settings | Tenant controls for Git/GitHub integration. |
| https://learn.microsoft.com/en-us/analysis-services/tmdl/tmdl-overview | TMDL semantic-model source representation. |
| https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-report | PBIR report definitions and relative semantic-model references. |
| https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.0.0/schema.json | PBIR visual-container structure. |
| https://github.com/microsoft/json-schemas/blob/main/fabric/item/report/definition/visualConfiguration/2.0.0/schema-embedded.json | Query-state, projection and field-reference structure. |
| https://github.com/gemini-cli-extensions/conductor/tree/f06add33b598f4262a190f234828dda551db70d7 | Pinned Conductor source/protocol. |

## Interpretation limits

Affiliation searches generate candidate institutional publications, not verified employment or institutional ownership. DORA provides a complementary Queensland Health repository signal. Cross-source matching is deliberately conservative; ambiguous matches remain separate and require review. No live Fabric refresh has been completed in this build environment. Local validation checks source definitions and contracts but does not execute the Microsoft Power Query/DAX engines.
