# Browser-first two-source publication report

## Outcome
Create a Fabric-deployable CHHHS publication report that can be operated without Power BI Desktop and combines PubMed with the CHHHS DORA RSS feed.

## Requirements
- PubMed affiliation strategy includes the supplied library aliases and named services.
- DORA RSS is a live source; supplied historic XML is used only to understand schema.
- Canonical count includes DORA-only items.
- Unique title+year cross-source matches may be merged; ambiguous matches must not be silently merged.
- Report surface is strictly limited to publication register, monthly publications and source reconciliation.
- Fabric Git system metadata is present and browser deployment is documented.
- Synthetic fixtures enforce deduplication behavior without embedding the user's historical DORA data.
