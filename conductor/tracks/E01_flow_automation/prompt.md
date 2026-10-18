# Task Prompt: E01 Power Automate Ingestion Canonicalization

Execute the canonicalization of the Power Automate cloud ingestion flow:
1. Eliminate manual button triggers in favor of a 06:00 AEST daily recurrence schedule.
2. Enforce production naming: "CHHHS Research Publications - Daily Ingestion & Enrichment".
3. Rebuild the deployable package under `private/ops/flow-packages/sharepoint-upsert.zip`.
4. Verify that the scheduled refresh in Power BI aligns at 07:00 AEST daily.
