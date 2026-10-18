# Live register and printable monthly report

The delivery has two reader-facing products from one isolated semantic model:

1. **CHHHS Publications** is continually updated after each accepted source batch and includes the supporting **Source Reconciliation** page.
2. **Monthly Publications** is a printable, frozen report for the previous complete Brisbane calendar month. It identifies its accepted source batch, reporting run, refresh time and query version.

The PBIR project retains exactly three pages so its operational provenance remains available without duplicating the model.

Prepared in the existing PBIR project on 2026-09-13: exactly three pages, 36 visuals and the existing six-table model, now with 18 measures. This is local authoring, not a deployed or rendered report. The Power BI web route again failed its admin-enforced policy verification; no tenant writes were attempted after denial.

| Page | Prepared content |
| --- | --- |
| CHHHS Publications (live) | Provisional canonical total, PubMed/DORA/both counts, facility/year/source/attribution filters, wrapped register with stable key and date precision, UTC refresh timestamp |
| Monthly Publications (printable) | Previous complete Brisbane month, accepted batch/run identity, selected-period count and source mix, facility matches, unallocated-date count, full authors/DOI/source links in a print-safe citation register |
| Source Reconciliation (live support) | Source counts, review count, source overlap, reconciliation methods, search counts/warnings, attribution evidence, raw dates and precision |

## Outcome-linked revisions to the 36-visual baseline

- Overview footer becomes a refresh-time card; the register is shortened to avoid overlap. The caption labels counts provisional.
- Monthly comparison card becomes the frozen reporting-month/run identity. The trend visual becomes selected-month facility contributions, avoiding a misleading 24-month label under a month filter. Historical visual IDs are retained for traceability.
- Reconciliation facility chart becomes a search-coverage/warnings table; facility contributions are available on Monthly Publications.
- Register fields expose full author/date/evidence information. The inaccurate title/year automatic-merge caption is removed.
- Three new measures support selected-month counts and blank register row suppression. Cards retain zero for valid empty months; register measures return blank for out-of-period or unmatched rows. The production monthly artifact uses its accepted run rather than a reader-selected rolling month; a draft view may still use the selector for validation.

## Remaining live gates

First finish the canonical model's identity ledger, source acceptance and native deployment. Apply these bindings to the isolated report one visual at a time, without rebinding or publishing the original. Verify links and full strings against retained metadata; model string storage still needs native validation. The report register is not an accepted complete export.

Test default, selected, multiple and empty months; null dates; unassigned facilities; and multi-facility deduplication. Confirm blank register measures suppress unrelated rows in the native table visual. Compare headline and monthly results with independent DAX output. Capture each rendered page privately and reopen to prove order, saved state, keyboard navigation and legibility. Long citations may require native column-width adjustments; local geometry checks cannot establish readability.

No native rendering evidence is available. Publishing, sharing and schedule gates remain unchanged.
