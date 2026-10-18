# T11_sources_and_reconciliation: Repair and prove PubMed plus DORA ingestion

## Outcome
Implement an empty-safe two-source harvester and conservative reconciliation in the actual Power Query engine. Retain real provenance and distinguish date precision, source failure and true zero results.

## Dependencies
T10_isolated_baseline

## Acceptance criteria
- Native M handles PubMed-only, DORA-only, both-empty and source-failure cases correctly.
- No conflicting identifier is automatically merged; ambiguous matches remain auditable.
- DORA date precision and missing metadata are explicit, not invented.
- RSS persistence/coverage is either verified or labelled incomplete; no complete institutional census claim.
- The Queensland Open Data DoRA activity resource is treated as a separate project/activity entity. Its current source columns and provenance are retained without being collapsed into publication rows.
- Historical attachment contents and synthetic examples are absent from the release model.

## Evidence boundary
Known local defects are listed in docs/WEB_FIRST_FINDINGS.md. Existing Python policy tests are not native M tests.

## Safety and scope
Read `conductor/workflow.md` and `contracts/web-first-execution.contract.json`. Preserve the existing report/model until an approved, isolated write path and rollback are proven. Do not require Fabric Git integration, capacity purchase, public publishing or a new repository. Do not enter or expose credentials in Git or this pack.
