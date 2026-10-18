# Implementation plan

## Connector-assisted funding sources — 13 October 2026

Incorporate the [connector/source selection](../../../docs/FUTURE_SOURCE_ENRICHMENT.md#microsoft-connector-and-contextual-source-selection--13-october-2026)
into existing source qualification and G04 adapter handoff. Prioritise approved
internal research/award SharePoint registers and official NHMRC/MRFF workbooks;
read exact fields/identities and permission/reuse scope before intake. Excel row
reading needs a table; prepare a separate table copy while retaining source bytes,
sheet/cell provenance, date and dictionary. File download is a separate qualified
operation, not an assumed feature of the Excel connector.

Official RSS may discover funding announcements where an actual stable feed is
verified; finite coverage and award/opportunity identity remain explicit. ABN Lookup
may resolve a named Australian funder/partner legal-entity gap, and Zenodo may supply
related outputs; neither creates eligibility or award-to-publication proof. HTTP/
custom licence/DLP and source credentials must be qualified separately from API
price. Funding chat prepares one source-specific mapping; shared catalogue/flow/
relationship integration remains serial and owner-controlled. No new source enabled.

## Parallel funding qualification — 13 October 2026

The funding chat can prepare one bounded source-specific mapping independently
of publications under the [parallel assignments](../../../docs/PLATFORM_COMPLETION_PLAN.md#parallel-delivery-assignments--13-october-2026).
Reuse G02 source qualification and G04 integration, not a separate source backlog.
First select an NHMRC or MRFF official award workbook, record permitted use, stable
grant/funder identity, source vintage, full field coverage and update semantics.
These award exports supplement the older calendar-only observations below;
they do not establish an opportunity feed or admit an enabled source.

The [expanded assessment](../../../docs/FUTURE_SOURCE_ENRICHMENT.md#free-api-coverage-review--13-october-2026)
adds NIH RePORTER for exact award/PMID links and Grants.gov as a documented
keyless opportunity candidate, conditional on foreign-applicant eligibility and
actual CHHHS relevance. UKRI, CORDIS and ARDC remain targeted conditional routes.
API keys may be free; cost, institutional eligibility, reuse terms and the current
keyless policy are separate checks. No registration, API-key purchase or provider
admission follows from discovery. Keep existing ARC awards and Qld catalogue
classifications; no raw awards in Git or automatic opportunity conversion.
Source catalogue/plan updates merge through the coordinator, with no concurrent
G02 writer. Complete one qualified source handoff before expanding the shortlist.

**Access scope:** current-user source inspection and reviewed/manual intake
only. No shared feed credentials, organisation-wide collector or unattended
source schedule is part of this tranche.

- [x] Record scope and acceptance requirements.
- [x] Inspect current inputs, dependencies and relevant platform objects. The reviewed delivery source map and official authority pages were inspected; endpoint payloads remain unverified.
- [x] Implement: Convert the researched source map into configuration with authority, format, access, sample and coverage status.
- [x] Implement fallback: Add a fail-closed reviewed-import route for sources without a permitted feed/API; require source/row identity, evidence URL, timezone-aware observation, reviewer notes and explicit `Reviewed` status.
- [x] Preserve review context: the bounded HTML calendar adapter retains the complete observed source row under `SourceColumns`, alongside the normalised title and raw deadline, without promoting candidates.
- [~] Verify: Verify NHMRC, MRFF, ARC, QH, EMF, Advance Queensland and local foundation intake; use reviewed import where feeds are unavailable. Authority-page/configuration evidence is complete, including additional Queensland Health, Metro North, Metro South, Torres and Cape and Cancer Council sources. The ARC public JSON awards API has a bounded HTTP-200 sample and is explicitly `awards_only`; NHMRC and MRFF now have bounded HTTP-200 HTML calendar candidate extraction, while unattended feeds/APIs, row-level review, source links and eligibility verification remain open.
- [x] Record local and live evidence separately before closure; the catalogue marks unverified intake explicitly and does not promote it to a working feed.
- [x] Review fix: make catalogue freshness validation use the declared Australia/Brisbane business date so UTC-based CI cannot reject a same-day verification date (commit `c00560f`).

## First-party source recheck — 2026-09-22

- [x] Recheck the official NHMRC and MRFF calendars and the ARC Grants
  Search/API guidance. NHMRC and MRFF remain HTML calendar/search surfaces;
  the current MRFF page directs applicants to GrantConnect for current
  opportunities and notifications. ARC documents a public JSON API for the
  Grants Search dataset, but GrantConnect remains the authoritative source for
  Commonwealth grant opportunities and guidelines.
- [x] Preserve the source classification: ARC JSON remains `awards_only` for
  this registry and must not be promoted to open-opportunity intake; NHMRC and
  MRFF remain review-gated HTML candidates until a permitted export or API
  supplies stable row-level identity, evidence and eligibility.
- [~] Keep G02/G04 open for a permitted opportunity export/API or an explicit
  reviewed row package. Authority-page reachability is not feed acceptance.

## Queensland source freshness recheck — 2026-09-22

- [x] Recheck the official NHMRC calendar: it exposes current/upcoming scheme
  rows and explicitly cautions that dates are planning information requiring
  confirmation in the final guidelines. Keep the HTML adapter review-gated.
- [x] Recheck Queensland Health, Health Practitioner Research Scheme, Metro
  North and Metro South sources. The pages expose current programme or round
  information, including the HPRS 2027 round, Metro North curated openings
  and Metro South 2027 RSS/INNOVATE dates; each remains manual-review intake
  with scheme/employment eligibility preserved.
- [x] Refresh `last_verified` to `2026-09-22` for those five catalogue entries.
- [ ] Do not promote any of these pages to unattended RSS/API ingestion until
  a permitted row-level export/API, stable identity and eligibility evidence
  are obtained. G02/G04 remain active.

## Native reviewed-row acceptance — 2026-09-22

- [x] Use the official Metro South Health 2027 INNOVATE page as a reviewed
  HTML source, retaining its row URL, published dates, amount and employee
  eligibility statement. No feed/API promotion was made.
- [x] Admit the canonical reviewed row `metro-south-innovate-grants-2027`
  through the existing current-user Grants Registry flow; native run
  `08584115872127113780695944024CU04` succeeded and SharePoint readback
  returned one item (ID 8).
- [x] Delete the exact test row and read back the empty registry; receipt:
  `private/ops/2026-09-22-powerautomate-g02-g04-metro-south-reviewed-row.json`.
- [~] Keep unattended source/API promotion, broader row-level eligibility
  review and production acceptance open.

## Phase: Review Fixes

- [x] Task: Preserve positional source cells alongside the convenience header map in the review-only HTML adapter (review fix `24e880c`).
- [x] Task: Fail closed on malformed authority/API URLs and source verification dates (bb8ed64).
- [x] Task: Treat non-HTTP(S) opportunity links as non-actionable evidence and retain them as review-needed records (da0b657).
- [x] Task: Require scalar source IDs and reject future catalogue verification dates (`e4985b2`).
- [x] Task: Require typed reviewed-import identities, URLs, review status and notes without coercion.
- [x] Task: Reject malformed ARC award identities, links and descriptive fields without coercion (03568d7).
- [x] Task: Require structurally valid HTTP(S) ARC evidence URLs, not just a URL prefix (`96079a0`).
- [x] Task: Preserve row-level HTTP(S) provenance for review-only HTML calendar candidates (e62b6f5).
- [x] Task: Require distinct row-level evidence URL and explicit eligibility statement before reviewed import (working-tree review fix).
- [x] Task: Reject reviewed rows whose `SourceRowURL` is identical to the general opportunity URL (`ffdc5a8`).
- [x] Task: Reject malformed optional descriptive fields before reviewed-row normalization (`04642b1`).
- [x] Task: Reject non-string authority/API URLs in the source catalogue (`18dd567`).
- [x] Task: Reject authority/API URLs with surrounding whitespace before intake validation (`ec5322c`).

## Phase: Conductor review fix — 2026-09-22

- [x] Task: Reject malformed optional source metadata (`record_kind`,
  `sample_fixture` and non-API `api_url`) without coercion; preserve explicit
  `null` fixtures (`25ad9d8`). Permitted opportunity feeds and unattended
  intake remain open.

## Phase: Conductor review fix — 2026-09-22

- [x] Task: Reject surrounding whitespace in optional `api_url` values for all catalogue rows, including non-API rows (`69c6acb`).
- [x] Verification: focused source-ingestion tests (25), full local suite (451 tests, 8 skipped), project checks (460), web-first contracts, Conductor validation and diff validation pass locally.
- [~] Permitted opportunity feeds, row-level review/eligibility evidence and unattended intake remain open.

## Phase: Conductor review fix — optional metadata identity boundary — 2026-09-22

- [x] Task: Reject surrounding whitespace in optional `record_kind` and `sample_fixture` metadata instead of silently accepting non-canonical provenance labels (`851962c`).
- [x] Verification: focused source-ingestion tests (26), full local suite, project checks (460), web-first contracts, Conductor validation and diff validation pass locally.
- [~] Permitted opportunity feeds, row-level review/eligibility evidence and unattended intake remain open.

## Phase: Conductor review fix — reviewed-import evidence boundary — 2026-09-22

- [x] Task: Reject surrounding whitespace in reviewed source, identity, URL and review-status fields instead of stripping reviewer evidence before admission (`12f5f41`).
- [x] Verification: focused reviewed-import tests (9), full local suite, project checks (460), web-first contracts, Conductor validation and diff validation pass locally.
- [~] Permitted opportunity feeds, row-level review/eligibility evidence and unattended intake remain open.

## Phase: Conductor review fix — ARC award evidence boundary — 2026-09-22

- [x] Task: Reject surrounding whitespace in ARC award code/ID and evidence URL values instead of stripping awards-only provenance before preservation (`6bc6e26`).
- [x] Verification: focused ARC adapter tests (5), full local suite, project checks (460), web-first contracts, Conductor validation and diff validation pass locally.
- [~] ARC remains awards-only; permitted opportunity feeds, row-level review/eligibility evidence and unattended intake remain open.
