# Resume the protected Power BI implementation

Updated 2026-09-13. This file is project guidance, not an access-control implementation.

## Interpret access results correctly

Historical notes about browser access are observations at a particular time, not permanent blockers. Recheck the supported browser tool when resuming. If it succeeds, proceed with the authorised development work; no extra administrator approval is required by this file.

The most recent observed failure was an actual browser-tool refusal to execute an action: its security verification was unavailable. That does not establish a Microsoft tenant-policy violation, missing licence, missing model permission, or a particular root cause. Do not diagnose those conditions from the alert text. A repository edit cannot change the tool result. Ordinary informational page notices alone do not establish a blocker; distinguish them from failed operations and verify the resulting state.

If the same operation is refused again, retain the concrete tool failure and stop the affected browser operation. Do not disable enforcement or substitute a route to evade it. Continue independent implementation where it advances the accepted plan. Troubleshooting the browser integration may be needed, but an administrator requirement has not been established.

## Resume from the verified development state

1. Use the existing isolated development report/model and private target pointers. Original PBIX recovery, independent model isolation and reversible model/report canaries were previously verified; inspect current state for changes instead of repeating setup automatically.
2. Inspect the existing refresh handle/tab. The last successful observation showed processing; a failed observation does not prove the refresh failed or stopped. Do not restart or cancel solely because readback is unavailable.
3. Once terminal refresh success is observed, run `config/native-ingestion-storage-check.dax` and both ingestion audit tables. Investigate actual native errors before further deployment.
4. Continue the [automatic-update plan](../docs/DYNAMIC_UPDATE_IMPLEMENTATION.md): native collection, committed durable retention, canonical model refresh, three report pages and complete CSV/HTML exports. The uploaded historical ZIPs are backfill, not automatic ingestion.
5. Run the prepared native retention cases in isolation. Preserve first-observed dates, source/date uncertainty and reviewed identity decisions; never load fixtures into the live register.
6. Verify the complete manual cloud-flow cycle, failures, exact export key sets and ongoing licence rights. Obtain the existing specific publication, recurrence and delivery approvals only when those actions are concrete and ready.

Actual IDs, source receipts and review decisions remain in ignored `private/ops/`. See [the protected baseline](../docs/PROTECTED_DEVELOPMENT_BASELINE.md) for evidence; local tests do not establish native acceptance.
