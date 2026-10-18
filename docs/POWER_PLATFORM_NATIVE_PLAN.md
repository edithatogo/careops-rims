# Power Platform native implementation and licence decisions

Updated 2026-09-13. This plan supplements T08–T15; it does not mark native execution, deployment or delivery complete. Prefer the existing isolated report/model in My workspace. No Fabric migration is required for the proposed core solution.

## Required automatic outcome

The [automatic-update implementation sequence](DYNAMIC_UPDATE_IMPLEMENTATION.md) is now part of T11–T15 acceptance. Historical uploads are backfill only. Implement and prove collection → retained batch/review state → canonical refresh → complete exports, with daily collection proposed separately from monthly output. Manual dry runs precede schedule approval.

## Observed entitlements

Read-only Chrome checks in the signed-in organisation account showed:

| Surface | Observed | Planning consequence |
| --- | --- | --- |
| Power Automate My licenses | Power Automate Free and Power Automate for Office 365; standard connectors enabled; premium, custom, on-premises and RPA capabilities unavailable | Default to standard cloud connectors and built-in data operations. Do not assume HTTP or custom connector rights. |
| Power BI profile | Free account; Power BI trial with 57 days remaining | Personal development is available; do not treat trial functionality as a permanent production entitlement. |
| Preferred My workspace settings | Workspace type Power BI Pro | This is a workspace classification, not evidence of a personal Pro licence. Keep existing report and isolated model here for development. |
| Separate workspace settings | Fabric Trial, FTL64, template-app workspace, no items | Temporary capacity is not a durable deployment dependency. Do not move the solution here automatically. |
| M365 subscriptions | Account selection returned to sign-in | Exact M365 SKU, SharePoint/Exchange assignments and Power Apps/Dataverse entitlements remain unverified. |

These observations describe the current UI, not every tenant entitlement. No licence, capacity, sharing, schedule or source setting was changed. Tenant identifiers and raw evidence belong only in ignored private paths.

## Authoring versus execution

Building report layouts and drafting flows can proceed before distribution. Connector rights apply to executing actions, including development/test runs, and may also be checked when creating connections or saving a flow. Publishing is not the only enforcement boundary. Power BI app distribution is distinct from saving a report in My workspace; this project continues personal report/model development with the available rights. The free [Power Apps Developer Plan](https://learn.microsoft.com/en-us/power-platform/developer/plan) permits premium-connector development and testing in a developer environment, not production operation. That is a valid development alternative if tenant policy permits it, but it is not an entitlement established by the observed Office 365 licence or the current default environment. No developer environment has been created or activated.

## Licence alternatives

| Licence / service | Relevant capabilities | Use in this project |
| --- | --- | --- |
| Power BI Free | Personal content in My workspace; sharing/collaboration requires additional rights | Current development target. Pro-labelled workspace does not confer Pro user rights. |
| Power BI Pro | Authoring and sharing in shared workspaces; recipients generally also need Pro or PPU without eligible capacity | Possible future organisational report distribution; not necessary to migrate to Fabric for this. |
| Power BI PPU | Additional premium BI features; PPU workspace consumers need PPU | Optional, not a fix for automated report ExportToFile. |
| Paid Fabric/Premium/Embedded capacity | Capacity features; eligible F64+ capacity permits free Power BI viewers with permissions; authoring still has user-licence requirements | Optional only after permanent entitlement and workspace compatibility are verified. Trial capacity is not the baseline. |
| Power Automate for Office 365 | Standard cloud connectors within seeded use rights | Planned RSS, SharePoint, Power BI and Outlook connectors, subject to service access, DLP, limits and action-level requirements. |
| Power Automate Premium / Process | Premium/custom connector rights; Process is allocated to an eligible solution flow | Optional direct HTTP collection route if already licensed or separately approved. Power Apps premium rights are not blanket rights for unrelated scheduled flows. |
| SharePoint / Exchange / Dataverse | Separate service provisioning and permissions matter | Verify library/list and mailbox access. Dataverse is optional; do not assume or provision it. |

Microsoft sources: [Power BI licences](https://learn.microsoft.com/en-us/power-bi/fundamentals/service-features-license-type), [Power Automate licence types](https://learn.microsoft.com/en-us/power-platform/admin/power-automate-licensing/types), [licensing FAQ](https://learn.microsoft.com/en-us/power-platform/admin/power-automate-licensing/faqs). Feature and tenant availability must be rechecked at implementation and after trial expiry.

## Native architecture and fallbacks

1. **Repair native refresh in isolation (T10).** Inventory and remove obsolete persisted SQL queries/partitions and their dependencies only in the protected development model, using the approved backup/rollback path. Unlinking a connection alone did not remove the dependency. Prove source-free execution, then each cloud source and persisted refresh independently. Use cloud-compatible Power Query `Web.Contents`; avoid browser-based web functions that require a gateway. Personal gateway mode is a gateway execution mode, not the account licence. Gateway removal is an execution gate, not a promised outcome of licensing.
2. **Retain source observations (T11).** Use SharePoint lists/library for immutable source batches, durable first-observed dates, source metadata, canonical register, review decisions and monthly snapshots. Verify access, list indexing/pagination and complete schema first. Use stable source identifiers and idempotent upserts; never derive first-observed dates anew on refresh.
3. **Collect DORA (T11).** Prefer recurrence plus the standard RSS connector's List all RSS feed items, not solely its new-item trigger. Finite feeds do not establish historical completeness; equal/older publication timestamps can evade triggers. Prove full author and metadata parity; if RSS actions omit fields, use a proven Power Query XML route, licensed HTTP, or a controlled native import. Preserve raw date, precision and coverage uncertainty.
4. **Collect PubMed with current rights (T11/T12).** Candidate standard route: Power Query `Web.Contents` retrieves and parses paginated NCBI results; the standard Power BI Run a query against a dataset action extracts validated observations into SharePoint. Prove this action works for this account and My workspace, with tenant ExecuteQueries enabled and Read/Build permissions. Bound pagination, rate limits, retries, result sizes and exact key coverage. Connector classification alone does not prove the action can execute. Premium fallback: direct Power Automate HTTP collection. If neither is available, use a controlled manual native import and explicitly classify the workflow as assisted.
5. **Separate collection from reporting (T11/T12).** Use collection batch IDs and freeze validated retained observations before refreshing the final canonical model. Avoid a circular refresh in which a model both consumes and overwrites its own unversioned register. Preserve reviewed merges, aliases, provenance and full bibliography. Use native M/DAX and retain exactly the three planned report pages: CHHHS Publications, Monthly Publications, Source Reconciliation.
6. **Orchestrate and export (T14).** Power Automate runs with concurrency one, a stable run key, source-health checks and a refresh completion gate. Prove a supported completion signal correlated to the requested refresh; an in-model batch marker requires an isolated single-refresh design and successful checks. A fixed delay is not evidence. If exact completion cannot be demonstrated with available actions, require manual confirmation and leave unattended acceptance open. Use built-in Select, Create CSV table and Create HTML table, SharePoint Create file and an archive manifest. Python remains a local test/reference tool, not a hosted production dependency.
7. **Prove complete output (T14).** Export the full canonical register and selected month; preserve full authors and identifiers, filters, source coverage and date precision. Partition queries deterministically within API row/value/size limits and compare exact model/export key sets. Keep the existing hash contract: prove a supported native hash implementation or propose a reviewed contract change before acceptance; do not invent a Power Automate hash expression. Report-page PDF is not the bibliography. Automated Power BI report ExportToFile requires supported capacity and does not support PPU; default to complete CSV/HTML with optional manual printing. Licensed paginated output is a separate capability check.
8. **Use supported current packaging (T14/T15).** Prefer solution-aware flows, connection references and environment variables where an existing Dataverse-backed environment and permissions allow. M365 standard-only flows can be solution-aware when the environment has Dataverse; Dataverse is not automatically licensed/provisioned by that fact. Fallback to ordinary cloud flows with documented configuration and exported packages. Do not depend on preview editors, Copilot, AI Builder, a new environment or a new capacity.
9. **Accept and release (T15).** Test native M/DAX, persistence, report rendering, live refresh, complete bibliography, failed/partial sources, duplicate triggers and dry-run monthly outputs separately. Recheck operation without trial-only features. Schedule activation, destinations, recipients and sending remain explicit approval gates. If organisational sharing is required, verify durable Pro/PPU or eligible capacity and audience rights before choosing the distribution route.

Technical references: [Power BI connector](https://learn.microsoft.com/en-us/connectors/powerbi/), [ExecuteQueries limits](https://learn.microsoft.com/en-us/rest/api/power-bi/datasets/execute-queries), [RSS connector](https://learn.microsoft.com/en-us/connectors/rss/), [data operations](https://learn.microsoft.com/en-us/power-automate/data-operations), [web model editing](https://learn.microsoft.com/en-us/power-bi/transform-model/service-edit-data-models), [Web connector troubleshooting](https://learn.microsoft.com/en-us/power-query/connectors/web/web-troubleshoot), [report export requirements](https://learn.microsoft.com/en-us/power-bi/developer/embedded/export-to).

## Remaining evidence gates

The preferred workspace is feasible for continued personal development. End-to-end unattended execution is not yet proven. T08 must verify service assignments, DLP, connector actions and post-trial rights; T10 has resolved inherited SQL execution for source-free M and the first DORA cloud source; T11–T15 must prove native parity, durable state, correlated refresh and complete exports. The existing monthly-flow JSON remains a blueprint until revised and configured against these decisions. No flow has been deployed or schedule enabled by this plan update.

## Deferred additional sources

The [future-source plan](FUTURE_SOURCE_ENRICHMENT.md) adds OpenAlex, Crossref, conditional ARDC research activities and freely permitted Dimensions capabilities after the current foundation is accepted. Reuse the existing workspace and native collection/retention pattern. Provider free tiers do not grant premium connector rights. No new source is enabled by this amendment.
