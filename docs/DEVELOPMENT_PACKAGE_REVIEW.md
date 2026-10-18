# Development package review — 2026-09-12

The user-authorized ZIP download is saved at `private/ops/development-package/CHHHS-Research-DEV-package.zip`, inside the repository's ignored private directory. The original archive is preserved; extracted code has not replaced runtime definitions. The standalone README is saved alongside it. No live collection or tenant modification was performed.

ZIP: 8,431 bytes; SHA-256 `24c47528f7cdae43c47d9c7cec8ac6b7b1bfa587163e03dcabe21b52ae3e2bda`.

All five member hashes declared by validation.json match the downloaded members. A separate manifest includes every member, including validation.json. The package's five synthetic parser tests passed locally after code inspection. Its schema executes successfully in an in-memory SQLite database with foreign keys enabled and creates seven tables. These checks do not certify live collection, registry behavior or native Power BI execution.

## File reconciliation

| File | Verified content | Reuse decision |
|---|---|---|
| collect_pubmed.py | ESearch date splitting; batched EFetch XML parser; author affiliations; bounded request retries; response hashes; unique run directories; candidate JSON; final manifest. | Useful candidate for the T11 external collector. Harden the findings below before adoption. Keep separate from the existing direct-M runtime until the release adapter is defined. |
| test_collector.py | Five parser tests: date preservation, errors, duplicate fetched records, conflicting DOI, unsupported records. | Reuse parser cases; add orchestration/configuration/restart tests. Existing tests do not cover collection completeness. |
| registry-schema.sql | Publication, identifiers, runs, source mappings, organisation reviews, review events and reporting releases. | Useful logical starting point. No code currently performs ingestion, identity resolution, review persistence or promotion against it. It lacks explicit per-source record versions and conflict storage required by its design prose. |
| source-config.json | Four affiliation aliases, provisional coverage, PubMed enabled, DORA disabled, schedule disabled. | Reconcile with Git facility configuration. Do not treat the four aliases as full district coverage or activate schedules. |
| README.md | Registry/release design plus an explicit initial-collector implementation section. | The ZIP member is 5,377 bytes; standalone README is 4,805 bytes. A line comparison confirms the added implementation section is the sole text difference. |
| validation.json | Hashes and claims of five parser tests, schema/config validity, no live PubMed, no DORA and no deployed replacement. | Member integrity and parser/schema claims were checked locally. Preserve the explicit non-deployment status. |

## Findings before reuse

| ID | Evidence | Required correction |
|---|---|---|
| P01 | Collector.ids converts idlist to a set before comparing its length with count. Offline response count=1, idlist=[123,123] was accepted. | Reject duplicate returned IDs and malformed IDs before deduplication. |
| P02 | A split parent count is not reconciled with the union of child IDs. An offline parent count=10,000 with child counts 1 and 0 returned one ID successfully. | Fail closed on parent/child disagreement; record source changes and retry or restart deliberately rather than accepting lost coverage. |
| P03 | main reads only config.pubmed.query. Request base, pacing, batch size, limit and ingestion kind are hardcoded; enabled is not honored. | Validate and apply supported configuration; refuse disabled collection and reject unsupported values. Record effective configuration, not merely the supplied JSON. |
| P04 | The manifest is written only in finally, and CLI has no resume input. Unique run directories and archived responses alone do not provide restartable execution. | Persist a running receipt before requests and checkpoint progress atomically; verify archived hashes and configuration before resuming. |
| P05 | Rate limiting is instance-local; multiple Collector instances/processes do not share a limiter. | Define and enforce one shared request budget for the approved execution process or service. |
| P06 | No code populates registry tables, preserves review decisions, resolves cross-source conflicts or promotes releases. DORA has no adapter. | Implement these separately against reviewed real source schemas; do not claim a completed pipeline from this archive. |

P01/P02 were reproduced without network access using controlled response bodies. P03–P06 are source-inspection findings. Private audit results and README diff are stored next to the archive. No changes were made to the archived source to make its tests pass.

## Relationship to existing Git work

Git's PubMedHarvest.m uses ESummary and fails at the retrieval limit; this module adds EFetch metadata and recursive splitting, but its split reconciliation needs repair. Git's CanonicalPublications.m and canonical_reference.py still use unique title/year merges; the ZIP collector does not replace or solve canonical reconciliation. Git's complete bibliography exporters and native acceptance gates remain applicable. A persistent registry/release adapter must map stable publication identity to CanonicalKey and reconcile complete key sets before report implementation.

The download/contents blocker is resolved. T08's remaining metadata/capability work and T10's recovery/isolation gate remain open; no live implementation track is marked complete by this review.
