# Publication platform acceptance

This is the evidence contract for the publication system. Local tests and generated packages prove implementation structure; they do not prove that the tenant has accepted the current list, flow, model, refresh, or exports.

## Canonical objects

| Object | Canonical target | Required connector or route |
|---|---|---|
| Publication Registry | One SharePoint list | SharePoint Online |
| Publication upsert flow | Existing canonical flow (`{{FLOW_ID}}`) | SharePoint Online list actions |
| Source archive | Approved private archive location | OneDrive/SharePoint file actions |
| Grants Registry | Future single SharePoint list | Separate SharePoint Online flow |

The source archive is not the publication registry. OneDrive file actions must not be treated as evidence of SharePoint list persistence.

## Acceptance gates

1. **Target identity** — read back the site URL, list ID, list display name, flow ID, model ID, and report ID from the platform.
2. **Schema** — read back required internal column names and types; do not rely on display names or positional `field_N` mappings without confirming them against the live list.
   The organisational enrichment fields must be added as an additive schema change and backfilled only from explicit affiliation evidence. Existing review decisions and canonical keys must remain unchanged.
3. **Create** — submit one isolated, clearly marked test record and prove it appears in the Publication Registry list.
4. **Idempotent replay** — replay the same `SourceKey` and prove no second item is created.
5. **Update preservation** — prove `LastObservedUTC` changes while `FirstObservedUTC`, `ReviewStatus`, `ReviewNotes`, and manual attribution fields remain unchanged.
6. **Concurrency** — run or otherwise test overlapping submissions and prove duplicate creation is prevented or quarantined.
7. **Failure safety** — submit an incomplete or failed batch and prove it cannot replace the last accepted batch or silently delete absent records.
8. **Reconciliation** — compare canonical key sets and field completeness between the accepted source batch, SharePoint list, semantic model, and complete exports.
9. **Refresh/readback** — correlate the requested refresh to terminal completion and read back the resulting model/report state.
10. **Monitoring** — expose last accepted batch, source status, counts, duplicate/quarantine counts, and last successful ingestion time.

## Current position

The repository implementation and local regression suite pass. Historical platform evidence exists for SharePoint synchronization and flow import. The remaining gates above require current authenticated platform readback; they must not be closed from local fixtures, package contents, a saved flow definition, or a non-terminal spinner.

## Safe next platform test

Use the existing flow and list in an isolated test cycle. Do not enable a new schedule, alter sharing, or rebind the production report. Capture the list item readback, flow run result, and before/after key-set comparison in a private evidence receipt before declaring acceptance.
