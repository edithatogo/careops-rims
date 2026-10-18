# Grants and funding opportunities system

Scope extension: [RIMS funding pages, institutional dates and subscriptions](RIMS_GRANTS_EXPERIENCE.md) is the current integration design. G01–G08 are now registered in Conductor. The original E06 local MVP remains the foundation; its completion does not cover the new tracks.

Status: **Local MVP implemented; platform deployment not yet authorised or performed**

## MoSCoW requirements

### Must have

- One canonical opportunity schema with many source observations.
- RSS/Atom and API-shaped input normalization.
- Stable source identity, URL, retrieval time, evidence hash, raw dates, and date precision.
- Explicit nullable fields for funder, amount, eligibility, geography, deadline, status, and contact.
- Conservative duplicate detection and idempotent merge.
- Review states for missing, inferred, conflicting, or uncertain data.
- SharePoint-compatible mapping and Power BI-ready exports.

### Should have

- Source health, last-seen, and stale-opportunity indicators.
- Funder taxonomy, opportunity type, discipline, geography, and CHHHS relevance review.
- Deadline reminders as a future approved workflow, never enabled by default.
- API adapters only for documented public APIs that add material coverage or structure.

### Could have

- Saved searches, staff watchlists, and controlled email/Teams notifications.
- Matching against research themes, facilities, investigators, and prior grants.
- Historical snapshots of changed amounts, deadlines, and eligibility.

### Won't have in the first release

- Automated applications or eligibility decisions.
- Scraping sources that prohibit automated access.
- A claim that the feed set is a complete funding census.
- Multiple competing SharePoint lists or platform flows for the same registry.

## Canonical schema

The local implementation is `scripts/grants_registry.py`. Its canonical fields are:

`OpportunityKey`, `Title`, `Funder`, `Source`, `SourceID`, `RoundID`, `URL`, `SourceRowURL`, `Description`, `Eligibility`, `Geography`, `Amount`, `Deadline`, `DeadlineRaw`, `DeadlinePrecision`, `Status`, `Contact`, `CHHHSRelevance`, `ReviewStatus`, `ReviewNotes`, `RetrievedUTC`, `RetrievedTimestampStatus`, `EvidenceHash`, and `SourceObservations`. Observation timestamps without an explicit timezone remain `Needs Review`; source deadlines retain raw values and precision. Reviewed imports require a distinct actionable `SourceRowURL` and an explicit eligibility statement; neither is inferred from the source page title.

## Mermaid architecture

```mermaid
flowchart LR
  F[Official RSS and Atom feeds] --> N[Canonical normalizer]
  A[Documented public APIs] --> N
  N --> V[Validation and date precision]
  V --> D[Stable identity and conservative deduplication]
  D --> R[Review-gated canonical registry]
  R --> SP[One SharePoint Grants Registry]
  R --> PB[Power BI-ready export]
  R --> H[Source history and evidence]
  D --> Q[Duplicate or uncertainty queue]
  Q --> R
```

## Canonical platform rule

The platform should have one `Grants Registry` list and one canonical ingestion flow. New sources add source observations to that registry; they do not create parallel lists or duplicate flows. Any future live deployment must inspect existing platform objects, update in place where appropriate, and verify readback before declaring the system canonical.

### Connector boundary: SharePoint list versus OneDrive archive

The grants registry is a structured-list workload. Its canonical cloud flow must use the **SharePoint Online** connector and target the single `Grants Registry` list by its resolved site and list IDs. It must not use OneDrive file actions for registry writes.

OneDrive remains valid only for the separate source-archive/readback contract used by the existing publication validation flow. That flow is not the grants registry flow and must not be repurposed as the list upsert flow. The existing publication upsert flow is also a separate canonical object targeting the Publication Registry list.

Accordingly, the live deployment gate is:

1. resolve whether a `Grants Registry` list already exists;
2. if it exists, inspect and update that object in place;
3. if it does not exist, create exactly one list after the approved platform gate;
4. configure exactly one SharePoint-based ingestion flow against that list; and
5. prove a list create/update/readback with a non-production test record before any production scheduling or notifications.

No live list, flow, schedule, notification, sharing change, or Power BI object is created by the local MVP.
