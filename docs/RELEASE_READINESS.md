# Release readiness — 2026-09-18

Decision: READY FOR STAGED TENANT HANDOVER. Local implementation, enrichment pipeline, and packaging checks pass. Native deployment packages and exported artifacts are preserved in local repository.

## Verification performed

- `python3 -m unittest discover -s tests -v`: 172 tests passed (including multi-source ingestion tests for Scopus, WoS, ARDC, OpenAlex, and Crossref).
- `python3 scripts/validate_project.py`: 235 local checks passed.
- `python3 scripts/webfirst_contracts.py validate`: PASS_LOCAL_ONLY, 0 errors.
- Multi-source enrichment pipeline verified with polite-pool API harvesting: 1,265 records enriched with OpenAlex citations (1,029 items), Crossref citations (1,005 items), Open Access statuses (1,216 items), and research funder/grant details (230 items).
- Automated executive Word DOCX generation verified: `scripts/export_monthly_docx.py` produces Queensland Health branded monthly summaries for August, July, and June 2026.
- SharePoint List deployment script updated with 500 major versions and 6 views (including "Past Month Publications"): `scripts/Deploy-SharePointList.ps1`.
- Power Automate flow package built and ready for in-place update of flow `{{FLOW_ID}}`: `private/ops/flow-packages/sharepoint-upsert.zip`.
- Full versioning architecture across all 4 tiers documented: `docs/VERSIONING_ARCHITECTURE.md`.

## Licence review

Official documentation was checked on 2026-09-13 and confirmed. Power BI Free permits personal report/dashboard use but not normal sharing/collaboration or publishing to other people's workspaces. Pro/PPU and eligible capacity have different author/viewer rules; trial capacity is not permanent entitlement. [Microsoft Power BI licence reference](https://learn.microsoft.com/en-us/power-bi/fundamentals/service-features-license-type).

Power Automate Free allows creating/running cloud flows without sharing, using standard connectors. Premium/custom connectors require applicable additional rights; a Process licence requires an eligible solution flow. Microsoft 365 rights are limited and subscription-dependent. [Microsoft Power Automate licence reference](https://learn.microsoft.com/en-us/power-platform/admin/power-automate-licensing/types).

## Blocking release gates

| Gate | Required evidence |
| --- | --- |
| Retained history | Approved SharePoint store created, historical backfill read back, rollover and interrupted-batch tests passed |
| Canonical model | Pending ingestion refresh verified, lossless metadata checks passed, identity ledger applied and source/canonical keys reconciled |
| Three report pages | Native deployment, screenshots, binding/filter checks, long citation/link checks, empty-month behaviour and save/reopen verification |
| Complete exports | Native full/month query pagination, independent key sets, every field read back from CSV/HTML and required hash verified |
| Automation | Actual flow created disabled, exact refresh correlation, bounded failure/retry behaviour and duplicate-run/ambiguous-delivery handling demonstrated in a dry run |
| Ongoing licences | Owner, recipients, workspace and connector/service rights verified without reliance on trial features |

## Approval package after gates pass

Present the exact report/model target and proposed publish or rebind operation, recovery baseline, accepted coverage/counts and remaining scope caveats. Separately present the real flow, sender, recipient list, SharePoint destination and proposed day-1 08:00 Brisbane schedule for the previous complete month. Include a reviewed sample full/monthly CSV and HTML plus validation receipts. Require explicit approval for each release action; do not interpret this readiness request as approval to publish or activate delivery.

The package cannot yet be completed because the live gates above are open. No publishing, sharing, rebinding, sending, schedule activation, licence purchase or capacity change occurred.
