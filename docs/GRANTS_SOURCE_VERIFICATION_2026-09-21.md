# Grant-source verification snapshot

Verification date: 2026-09-21 (Australia/Brisbane). This is source-page
evidence, not a tenant ingestion or unattended-feed acceptance receipt.

| Source | Evidence observed | Intake decision |
|---|---|---|
| NHMRC | The official funding calendar exposes current and upcoming schemes with application-open, minimum-data and closing dates. The page warns that dates are planning dates and final guidelines must be checked. | Keep the bounded HTML adapter as `Needs Review`; do not promote to unattended RSS/API intake. |
| MRFF | The official calendar exposes open, forecast and closed opportunities, including application, minimum-data and closing dates. Forecast dates are explicitly indicative and GrantConnect is the notification authority. | Keep open/forecast/closed rows review-gated; do not promote to unattended RSS/API intake. |
| ARC | The official Grants Dataset page documents a public JSON API and distinguishes funded-project data from opportunity discovery. | Keep the API route `awards_only`; never treat awards as open opportunities. |
| Queensland Grants Finder | The public CKAN package endpoint is a valid metadata response, but the reviewed package exposes contribution-resource metadata rather than opportunity rows. | Keep `metadata_only`; follow linked agency pages for actual calls. |

The bounded review-only adapter was also re-run against fresh HTTPS responses:
NHMRC produced 13 candidate rows and MRFF produced 179 candidate rows. These
are still `Needs Review` candidates, not accepted opportunities; no source row
URL, eligibility decision or tenant write was invented.

## Acceptance boundary

These observations refresh authority-page evidence only. They do not prove a
permitted RSS/Atom endpoint, stable API contract for opportunities, row-level
eligibility review, SharePoint write, Power Automate run, schedule, notification
or organisation-wide target. The fail-closed reviewed-import path remains the
approved fallback for current opportunities until a row has a source URL,
source/row identity, observed timestamp, review notes and `ReviewStatus=Reviewed`.

Official references:

- https://www.nhmrc.gov.au/funding/calendar
- https://www.health.gov.au/our-work/mrff/grant-opportunities-calendar
- https://www.arc.gov.au/funding-research/funding-outcomes/grants-dataset
- https://www.data.qld.gov.au/dataset/grants-finder

## First-party route decision refresh — 2026-09-21

- The [NHMRC funding schemes and calendar](https://www.nhmrc.gov.au/funding/calendar) remains a first-party HTML calendar and search surface; it is not promoted as RSS/Atom or an unattended API.
- The [MRFF grant opportunities calendar](https://www.health.gov.au/our-work/mrff/grant-opportunities-calendar) publishes open, forecast and closed tables, while the page directs users to GrantConnect for current opportunities and notifications. Forecast dates remain indicative.
- The [ARC GrantConnect guidance](https://www.arc.gov.au/funding-research/grantconnect) identifies GrantConnect as the authoritative opportunity/guidelines source; the separate public ARC JSON route remains an awards/project context source, not an open-opportunity feed.
- The [Queensland Grants Finder catalogue](https://www.data.qld.gov.au/dataset/grants-finder) remains a contribution-resource dataset. Its public CKAN presence does not establish a row-level opportunity API.

Decision: retain `reviewed_import`/`manual_review` for these opportunity routes until an approved export, permitted feed/API, or human-reviewed row package supplies stable row identity, source URL, observation timestamp, eligibility/review notes and explicit admission status. No unattended source route is inferred from page reachability or search indexing.

## First-party recheck — 2026-09-22

The current official source guidance does not change that decision. The ARC
Grants Search help documents a public paginated JSON API, but the dataset is
grant/project-search data and is not an open-opportunity feed. ARC and the
Department of Health identify GrantConnect as the authoritative Commonwealth
opportunity and guideline source. NHMRC and MRFF continue to publish calendar
pages rather than an accepted RSS/Atom/API opportunity source. Keep these
routes review-gated until an approved export/API or reviewed row package is
available; do not infer a feed from HTML reachability.
