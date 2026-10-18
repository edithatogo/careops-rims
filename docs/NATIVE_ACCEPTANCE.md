# Native acceptance gate: T05

Owner: CHHHS research reporting / Power BI administrator. Status: NOT RUN.

Keep the old files unchanged for comparison, but do not publish them as the research report. Never repair this by pasting a script into the old PBIX and assuming the old active model disappeared.

## Desktop

- [ ] Open the new PBIP in current Power BI Desktop, not Report Server Desktop. Record Desktop version and any schema/engine errors verbatim.
- [ ] Confirm the model has only Publication, Facility, PublicationFacility, Date, SearchAudit and ReportingWindow. No Employee, EmplID, hiring or separation objects.
- [ ] Set pNCBIEmail to an operational contact. Use Anonymous web credentials for NCBI and the organisation-approved privacy setting. Limit parallel loading during acceptance.
- [ ] Refresh successfully. An error must remain an error, not be accepted as a zero-publication result. Any query over 10,000 PMIDs requires date segmentation before release.
- [ ] Check SearchAudit for all 28 queries, source translations, counts and warnings. Validate phrase warnings, particularly small facilities that have no publications.
- [ ] Verify a sample of actual article affiliations in PubMed, including Cairns Base Hospital, a hinterland facility and a multi-facility paper. Do not assume the broad database phrase match proves institutional ownership.
- [ ] Reconcile the unique PMID count and facility bridge. Sum of facility counts is allowed to exceed the unique HHS total.
- [ ] Compare the last complete month's register with raw citation dates. Check month-only/year-only dates, leap days, 30/31-day dates and the Brisbane month boundary. Confirm the correct treatment of dates before 1900.
- [ ] Inspect all three contract-bound pages, every slicer, title, table, tooltip and cross-filter interaction. Check long titles, table scrolling, empty months and no-result facility selections. Adjust native visual formatting where necessary.
- [ ] Save as a NEW PBIX. Reopen it and verify the active model and visuals again. Also save a PBIP and run the local validator against the saved definitions.
- [ ] Run `python scripts/check_saved_pbix.py "C:\path\new.pbix"`. This is a metadata/cache regression gate, not proof that all binary model content has been decoded.

## Service and scheduled report

- [ ] Select the approved workspace, owner and sharing permissions. Confirm licenses, data policies, cloud refresh connectivity and export capability.
- [ ] Publish only after Desktop acceptance; configure NCBI credentials and test Service refresh.
- [ ] Configure monthly orchestration with a persisted run record, concurrency one, refresh completion polling and a freshness check. Never export immediately after merely requesting a refresh.
- [ ] Test success, rate limiting, request failure, zero results, repeated run and stale-refresh cases. Delivery must not occur on failure or stale data.
- [ ] Archive the PDF/HTML, monthly citation register, query audit, query version, refresh ID and reporting month. Confirm recipients before enabling actual distribution.
- [ ] Record evidence and sign-off in this track before changing T05 to completed.

No item on this checklist was executed in the Linux build environment. Python tests exercise reference policies and static definitions, not the actual Power Query/Tabular engine.
