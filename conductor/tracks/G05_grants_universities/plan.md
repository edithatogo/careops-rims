# Implementation plan

**Access scope:** current-user permitted source inspection and reviewed/manual
institution intake only. No cross-user directory or unattended portal access
is assumed.

- [x] Record scope and acceptance requirements.
- [x] Inspect current inputs, dependencies and relevant platform objects. University research-office pages and access boundaries were checked; no institutional login or portal export was used.
- [x] Implement: Record JCU, UQ, QUT and Griffith authority pages, formats, access, eligibility scope and only source-backed internal lead-time facts.
- [~] Verify: Public-page evidence is recorded; permitted feed/export routes and internal portal access remain unverified, with unknown lead times retained as null.
- [x] Record local and live evidence separately before closure.

## University source freshness recheck — 2026-09-22

- [x] Recheck UQ's public current-funding table and research-office guidance:
  internal and external closes are distinct, with a stated standard ten
  working-day internal close and scheme-specific exceptions. UQ access and
  submission workflow remain manual-review boundaries.
- [x] Recheck QUT's public research/ARC guidance: public pages identify
  scheme information and direct applicants to the Research Office for internal
  deadlines; no permitted feed/export was exposed.
- [x] Refresh the UQ and QUT catalogue `last_verified` dates to `2026-09-22`.
- [x] Recheck JCU and Griffith through their current official pages. JCU's
  current application-procedures page confirms one-week Australian and
  two-week overseas internal submission lead times; Griffith's public page
  confirms the Research Funding support route is internal-only. Neither public
  route supplies a permitted feed/export or authenticated portal route.
- [~] Keep JCU and Griffith at manual-review intake with unknown or qualified
  lead-time fields; do not promote either institution to unattended ingestion
  without a permitted export/API or authenticated portal evidence.

## Phase: Review fixes

- [x] Task: Validate known institutional lead-time objects while retaining null for unknown evidence (a179d73).
- [x] Task: Reject boolean lead times and invalid authority/verification metadata before source use (f0ee882).
- [x] Task: Reject fractional institutional lead times so catalogue values match integer-day planning inputs (ae2a630).
- [x] Task: Reject non-object rows, non-string institution identities and future verification dates using the Australia/Brisbane business date.

## Phase: Conductor review fixes — 2026-09-22

- [x] Task: Reuse the strict university catalogue validator before bounded authority probing, so malformed rows cannot be mistaken for source evidence (`1a073b7`).
- [x] Verification: focused source-probe/university tests (12), full local suite (449 tests, 8 skipped), project checks (460), web-first contracts, Conductor validation and diff validation pass locally.
- [~] Permitted institutional feed/export or authenticated portal acceptance remains open; authority-page probes remain read-only evidence only.

## Phase: Conductor review fix — authority URL boundary — 2026-09-22

- [x] Task: Reject surrounding whitespace in university `authority_url` values instead of stripping a source identity before validation (`1f5c25f`).
- [x] Verification: focused university tests (9), full local suite, project checks (460), web-first contracts, Conductor validation and diff validation pass locally.
- [~] Permitted institutional feed/export or authenticated portal acceptance remains open; authority-page probes remain read-only evidence only.
