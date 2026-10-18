# Specification: E01 Power Automate Ingestion Canonicalization and Recurrence Scheduling

## 1. Overview & Business Value
Power Automate cloud flow `{{FLOW_ID}}` was initially configured with a manual button trigger and development nomenclature (`"CHHHS Publications - DEV manual ingestion validation"`). This caused operational uncertainty because the flow did not execute autonomously on schedule.

This track establishes the **single canonical production version** of the ingestion flow:
- Renamed cleanly to `CHHHS Research Publications - Daily Ingestion & Enrichment`.
- Replaces the manual trigger with a daily recurrence trigger scheduled at **06:00 AEST (20:00 UTC)**, precisely 1 hour prior to the Power BI dataset scheduled refresh at **07:00 AEST**.
- Retains idempotent upserts into the Queensland Health SharePoint publication registry (`{{SHAREPOINT_LIST_ID}}`).
- Continues token-free OpenAlex citation enrichment and field-level auditing.

## 2. Functional Requirements
1. **Recurrence Trigger:**
   - Type: `Recurrence`
   - Frequency: `Day`, Interval: `1`
   - Schedule: `hours: ["20"]`, `minutes: [0]`, `timeZone: "UTC"` (06:00 AEST daily).
2. **Canonical Nomenclature:**
   - Flow Display Name: `CHHHS Research Publications - Daily Ingestion & Enrichment`.
   - Manifest Resource Display Name: `CHHHS Research Publications - Daily Ingestion & Enrichment`.
3. **Upstream & Downstream Alignment:**
   - Executes at 06:00 AEST to harvest new citations and write to SharePoint.
   - Power BI dataset scheduled refresh triggers at 07:00 AEST daily with `notifyOption: MailOnFailure` to digest the freshly written SharePoint records into VertiPaq.
4. **Zero-Sprawl Deployment:**
   - Package generator (`scripts/build_sharepoint_upsert_package.py`) updates the existing flow definition in-place without generating orphan cloud logic flows.

## 3. Acceptance Criteria
- [x] Flow definition `config/flows/publication-registry-upsert.definition.json` contains recurrence trigger at 20:00 UTC and canonical display name.
- [x] `config/flows/manifest.template.json` reflects canonical display name.
- [x] `scripts/build_sharepoint_upsert_package.py` packages definition into `private/ops/flow-packages/sharepoint-upsert.zip`.
- [x] Zip package verified containing Recurrence trigger and canonical title.
