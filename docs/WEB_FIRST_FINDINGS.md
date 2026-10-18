# Source baseline findings and implementation obligations

Basis: actual v0.3.0-rc1 source at commit 92c1d0e0ddfe5ee3400b054d50ad3abeb11a8665. These are local source findings, not observations of the report now in the user's Power BI workspace.

| ID | Finding | Track | Required resolution |
|---|---|---|---|
| F01 | Product guidance still described four pages and distinct PMID counting while the generated report has three pages and CanonicalKey counting. | T09 | Reconcile current guidance and retire Fabric/native-first prerequisites. Fixed locally in this package. |
| F02 | `powerquery/CanonicalPublications.m` expands `PubMedRows{0}[Canonical]` unconditionally. An empty PubMed result has no first record, even if DORA has records. | T11 | Explicit typed canonical schema repaired locally on 2026-09-12; source and generated model aligned. Native tests for each empty-source combination remain unverified. |
| F03 | Both the M canonicaliser and `scripts/canonical_reference.py` use unique normalised title/year, without PMID/DOI conflict or author compatibility checks. Earlier prose promising stronger matching is not implemented by this baseline. | T11 | Conservative exact identifier matching repaired locally on 2026-09-12 in M and Python reference; title-only matches remain review candidates. Native execution remains unverified. |
| F04 | DORA RSS dates become `PublicationDatePrecision="day"`; an uncorroborated feed timestamp cannot establish actual publication-date precision. | T11/T12 | Raw feed date is preserved with unknown precision and no inferred publication month in the local M repair of 2026-09-12. Native execution remains unverified. |
| F05 | DORA is reread from a finite RSS window; there is no durable write-back registry in the M source. Items can disappear on later refreshes. | T11 | Persist observed records in an existing approved store or keep full historical coverage explicitly unaccepted. |
| F06 | Text-normalisation functions and XML extraction have not been compiled in the actual web Power Query engine. | T11 | Native function/schema tests; do not equate Python tests with M compatibility. |
| F07 | Existing monthly blueprint mentions a PMID register, which can exclude DORA-only publications. | T14 | Canonical-key reconciliation and complete exports. The new target contract prohibits the old rule. |
| F08 | Source-level validators passed without exercising live M/DAX, source availability, browser save/reopen or full bibliography export. | T09/T15 | Separate policy checks from native/tenant acceptance with explicit evidence gates. |

The supplied historical DORA attachment is design evidence only. It is not embedded in the new fixtures or candidate data. Prior workforce files remain external historical inputs; no employee rows are imported into this work package.

The frozen v0.3 definition manifest is a drift-detection baseline, not a certification that this code is correct. Remediation must update source and generated definitions with a reviewed contract revision. The new target requirements intentionally remain unmet by parts of the baseline until the corresponding live implementation tracks run.
