# Canonical model completion

Local changes prepared on 2026-09-13; native deployment and readback remain blocked by Chrome's admin-policy verification failure on Power BI. No tenant model changes were made in this continuation.

## Counting correction

The previous Publications measure always intersected the facility bridge. Consequently, records retained for affiliation/scope review but lacking a facility link could disappear from the headline even with no facility filter. The revised measure counts all canonical keys in the current publication context, applies the bridge only when Facility or PublicationFacility is directly filtered, and returns zero for an empty result. Existing publication/date filters remain effective.

## Reconciliation evidence

CanonicalPublications now returns SourceMap (one observed source identity to one canonical key), Audit (source identity uniqueness, mapping coverage, bridge integrity and count balance), and explicit CandidateKeys in DoraReconciliation. Multiple DORA records can map to one PubMed key, so source-record overlap must not be confused with the number of canonical publications carrying both sources. Identifier conflicts and title/year candidates remain separate review cases; they are not silently merged.

## Remaining acceptance work

1. Verify the pending full ingestion refresh and all metadata/storage audits before canonical deployment.
2. Transfer the existing evidence-backed identity decisions, exact old/new identifier corrections, aliases and exclusions from the private registry into the approved durable review store. Validate those decisions against current source versions before applying them. The current M matcher does not yet apply that ledger; automatic identifier matching alone does not reproduce the reviewed registry.
3. Compile CanonicalPublications in the isolated native model and inspect Audit, SourceMap and DoraReconciliation. Reconcile exact source and canonical key sets; inspect every unmatched or ambiguous candidate.
4. Load the six-table research model and relationships after comparing current tenant definitions. Run config/native-canonical-check.dax, including unfiltered counts, every facility and an empty context. Also verify multiple selected facilities count a shared publication once.
5. Reconcile the complete bibliography and monthly exports to those actual model keys. Excluded duplicates remain in the audit, unresolved scope cases remain visibly provisional, and uncertain dates remain unallocated to a month.

The historical private registry previously established 1,317 active identities: 1,306 included, ten needing scope/attribution review and one excluded duplicate, yielding 1,316 provisional bibliography entries. These are historical local reference counts, not refreshed native results and not hard-coded acceptance targets. The current source batch may legitimately differ; every difference needs source/decision evidence.
