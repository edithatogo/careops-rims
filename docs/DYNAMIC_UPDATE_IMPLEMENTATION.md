# Automatic publication updates

Updated 2026-09-13. Required outcome: new and changed PubMed/DORA observations reach the retained canonical register and the existing Power BI report without manual file uploads. Historical ZIPs are recovery/backfill evidence only. They do not implement ongoing ingestion.

## Execution sequence

1. Validate the in-flight native staging refresh and metadata/key audits in the isolated model. Record terminal success or failure; a long-running spinner is not success.
2. Create a manually triggered development flow in the existing Power Automate environment. Prove the standard Power BI query action against the isolated model and existing OneDrive for Business/SharePoint storage. Inspect existing flows first. Do not activate recurrence during development.
3. Persist immutable source batches and a run manifest in the approved development source archive. Extract all staged records and metadata chunks with bounded pagination and exact source-ID checks. Read files back before committing a batch. Keep raw source metadata and explicit date/coverage uncertainty.
4. Upsert the durable register by source ID; preserve FirstObservedAtUTC and separately update LastObservedAtUTC. Retain absent feed records. Apply versioned reviewed aliases/identity decisions without overwriting their evidence. Keep failed/incomplete batches uncommitted and the last accepted batch readable.
5. Point the canonical model at an explicitly committed retained batch and review version. Separate staging collection from report consumption; never have a model overwrite its own unversioned input. Refresh the report model only after the batch commit.
6. Correlate the requested refresh to terminal completion, verify batch identity and exact source/canonical key coverage, and expose last successful refresh plus source status on the report. A fixed delay or a changed timestamp alone does not qualify.
7. Generate the continually updated full-register CSV/HTML after each accepted update. Generate a separate printable monthly CSV/HTML for the previous complete Brisbane month, pin it to the accepted batch/run and retain its immutable output manifest. Reconcile every field and independent key sets. Export failures must not be reported as a successful delivery.
8. Demonstrate two successive live cycles, idempotent replay, a smaller DORA feed, an updated record, source failure, interrupted commit and truncated export. Native fixture tests remain isolated from live data. Verify post-trial rights before release.
9. Obtain the existing specific approval gates for recurrence, publication and delivery only after the dry run is reviewable.

## Proposed cadence and licences

Daily collection at 08:00 Brisbane; monthly output on the first day at 09:00 Brisbane after an accepted update. These are configurable proposals, not enabled schedules. Use the Power Automate Windows timezone identifier `E. Australia Standard Time` when configuring recurrence. Monthly processing must wait for a verified accepted batch rather than rely on the one-hour interval, then retain a frozen printable monthly artifact instead of a reader-selected rolling view.

Prefer existing My workspace, Power Query and standard Power BI/OneDrive for Business/SharePoint actions. No Fabric trial dependency. Probe action execution before committing to this route. If query/retention actions or exact refresh correlation cannot run with the assigned rights, record the precise failed action and use a verified existing licensed route; assisted manual operation remains an explicitly incomplete fallback for this automatic-update requirement.

## Acceptance status

- Plan and local query definitions: prepared.
- Historical source ZIP upload: observed in the existing private development folder; remote byte verification and consumption pending.
- Native full ingestion: refresh processing; not accepted.
- Automatic cloud collection, committed retention, report refresh and complete cloud exports: not yet proven.
- Recurrence and delivery: not enabled; separate approval remains required.

## Implementation evidence this turn

Prepared `scripts/build_source_extraction.py` and five generated DAX page queries for both publication tables, both metadata-chunk tables and author evidence. Compound source-ID/index cursors prevent skipping the rest of a publication at a page boundary. Consumers must still verify unique tuples and independent total/key counts; TOPN alone is not a completeness guarantee. `config/daily-update.blueprint.json` defines the manual development cycle and inactive proposed recurrence; the monthly blueprint now explicitly depends on an accepted update batch. Neither blueprint is an importable or deployed flow.

Local verification: 161 unittest tests passed; 235 project checks passed; web-first contracts PASS_LOCAL_ONLY. These checks do not execute the new DAX in Power BI.

Cloud attempt: the existing Power Automate licence panel was readable, but closing it was denied because browser admin policy could not be verified. No cloud flow was created. The Power BI refresh was still processing at the last successful observation; no terminal outcome was read. Restore supported browser access before deploying and testing these queries. Do not route around that denial.

### Native retention implementation

`powerquery/fnRetainSourceObservations.m` implements a source-scoped merge against durable prior observations. It preserves missing records and first-observed timestamps, rejects duplicate IDs, invalid JSON, incomplete batches and older observation times, and keeps review decisions in a separate ledger. The outer validation guard is required even for empty inputs because M is lazily evaluated. `tests/native/retention-cases.m` provides nine isolated native cases; these are prepared but have not executed in the native engine. Storage wiring and batch commit remain pending. A fresh Power Automate access check was again denied by the browser security verifier; this is not evidence of a tenant licence or policy configuration.

## Later source expansion

After the current automatic PubMed/DORA cycle, retained history, canonical model, reports and exports pass acceptance, follow [the deferred enrichment plan](FUTURE_SOURCE_ENRICHMENT.md). Optional-source failures must preserve the base pipeline and its last accepted enrichment. This future phase does not alter the current two-source completion criteria.
