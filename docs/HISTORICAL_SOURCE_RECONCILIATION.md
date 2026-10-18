# Historical source reconciliation — 2026-09-12

The public DoRA CHHHS collection was traversed through its ordinary pagination: 36 index pages yielded 709 distinct item URLs, and all 709 full metadata records were retrieved. Every response has a local hash. A fresh final index check retained the count and first-page keys. This establishes coverage of the observed public collection, not all CHHHS research activity or a transactionally frozen repository snapshot. No article PDFs were downloaded.

The collector is `scripts/collect_dora_history.py`. It checkpoints downloads, verifies archived bytes on resume, checks pagination counts and unique keys, and validates each item's canonical handle. One legacy HTTP handle was accepted only because it identifies exactly the same host/path as its HTTPS item. A malformed DOI containing an article title is retained as an explicit source warning and is never used for matching. Issued dates are read from explicit publication metadata, with original text and missing precision retained.

## Combined evidence

| Result | Count |
|---|---:|
| PubMed source records | 1,261 |
| DoRA source records | 709 |
| Source-record overlap reconciled by identifiers | 645 |
| Registry identities before exclusion | 1,325 |
| Evidence-reviewed inclusions | 1,296 |
| Records needing further review | 28 |
| Publisher-confirmed duplicate excluded | 1 |
| Provisional bibliography entries, including review cases | 1,324 |
| Exact-month export groups | 309 |

Four earlier source-only keys were retained as aliases after metadata enrichment established exact identifier matches. No contradictory-identifier ingest was silently merged. Eight additional cross-source title/year groups remain separate because identifiers are missing or inconsistent. Their candidate keys and reasons are recorded privately; these are not confirmed distinct publications. Therefore the provisional bibliography count must not be used as an accepted headline count.

The original two title/year groups were reviewed against archived PubMed metadata. One consists of an article and a separate comment, which remain distinct. The other is an unintended duplicate explicitly identified by a published correction; the duplicate is excluded from bibliography exports but retained in the audit. A further same-title pair has distinct DOI and journal citation evidence and remains separate.

Affiliation reviews use explicit source statements and configured facility aliases, with geographic constraints where required. They are automated source-evidence decisions, not human institutional approval. Existing decisions are preserved. Open cases include historical Cairns Public Health Unit scope, investigator-only participation, incomplete attribution, malformed metadata, and unresolved cross-source identities. Source dates and institutional scope are not inferred from a locality alone.

## Artifacts and reproduction

All real records, raw pages, source receipts, SQLite state and review evidence remain in ignored `private/ops/`. The latest candidate is `private/ops/candidate-releases/reconciled-history-20260912/`. Earlier candidate releases remain immutable and are superseded for review. Its full CSV/HTML and all monthly CSV/HTML exports reconcile to the local staged keys. Excluded records remain in `registry-metadata.json`; retired keys remain in `identity-aliases.json`.

```sh
python3 scripts/collect_dora_history.py private/ops/dora-history/NEW_ARCHIVE
python3 scripts/stage_collected_publications.py --pubmed private/ops/pubmed-baseline/RUN_ID --dora private/ops/dora-history/NEW_ARCHIVE --history --database private/ops/publications.sqlite --output private/ops/candidate-releases --release-id NEW_RELEASE
python3 scripts/review_publication_candidates.py private/ops/publications.sqlite private/ops/review.json
```

The review command defaults to recommendations. `--apply-supported` records explicit-evidence inclusions without overriding existing review events. Historical title/identifier exceptions require a separate documented decision; they must not be auto-merged by title. An interrupted writer lock may be removed only after confirming the writer is no longer active. Staged exports are not automatically refreshed after review decisions; create a new immutable stage using `Registry.stage` and render it again.

## Native gates

Power BI access was retried through the supported browser route and was denied because the browser could not verify its admin-enforced security policy. See [the access recovery handoff](../handoff/POWERBI_ACCESS_RECOVERY.md). Baseline recovery, independent model isolation, canary/report persistence, native M/DAX, three-page rendering, live refresh, native/export key reconciliation and release acceptance remain open. No sharing, publishing, delivery schedule, VM or tenant settings were changed. T11/T14 receive local preparation evidence only; their native dependencies are not waived.

Validation: 147 unit tests, 212 project checks and PASS_LOCAL_ONLY contracts. These results do not certify the live report.

## Subsequent identity review

The eight pending identity groups above are now resolved. Evidence came from the archived DoRA full-record fields, the exact ORCID works linked by those records, and archived PubMed citations. It included explicit PMID/DOI or PMC matches, or matching full author lists, journal, year, volume, issue and article/page identifiers. The two incorrect DoRA DOI values received explicit old/new corrections, rather than a general punctuation/truncation rule. Raw source versions remain unchanged.

The registry now has 1,317 active identities: **1,306 evidence-reviewed inclusions, ten unresolved scope/attribution cases, and one excluded publisher-confirmed duplicate**. The complete provisional bibliography therefore contains **1,316 entries**, including the ten review cases. All 309 exact-month export groups were regenerated in the new immutable `private/ops/candidate-releases/identity-resolved-20260912/` stage. Earlier stages are superseded for review. These are still local registry counts, not Power BI readback.

`Registry.resolve_identity` requires explicit hashed evidence and a reason/actor/timestamp. Identifier conflicts require corrections matching the current old and new values exactly. It preserves original keys as aliases, donor review events, raw source records and a decision ledger; it refuses excluded identities and aliases as new merge inputs. Reviewed exact corrections persist when the same source value is seen again. A private SQLite backup predates these decisions. Future DoRA imports also retain citation, linked ORCID, relation URL and journal fallback fields to support the same review.

The remaining ten cases comprise six Cairns Public Health Unit scope questions, two investigator-only participation cases, and two DoRA records without confirmed CHHHS author affiliation. One further record with an invalid DOI was accepted on explicit CHHHS attribution and stable DoRA identity while retaining its missing-identifier warning. PubMed corroboration for the eating-disorders article lists affiliations outside CHHHS, so collection placement alone was not treated as proof of institutional authorship.

Latest validation: **148 unit tests**, **212 project checks**, and **PASS_LOCAL_ONLY** contracts. The supported Power BI browser route was retried and returned the same admin-policy verification denial. Native isolation, authoring, refresh, rendering, model/export reconciliation and release acceptance remain open.
