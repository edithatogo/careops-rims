# Publication defects and report scope

## Outcome

Correct known local attribution and flow defects, and reconcile publication report scope against the existing native report before live acceptance.

## Inputs and edit scope

scripts/organisation_enrichment.py; config/organisation-hierarchy.json; scripts/clinical_attribution.py; scripts/build_sharepoint_upsert_package.py; scripts/validate_publication_platform_contract.py; scripts/build_report.py; scripts/build_legacy_report_json.py; contracts/dashboard.contract.json; contracts/runtime-baseline.manifest.json

Read [execution protocol](../../PUBLICATION_STABILISATION.md) first. Add focused tests and safe configuration examples as required. Other files require a stated dependency reason in review.md. Preserve unrelated edits.

## Acceptance

Every task in plan.md must have evidence. Tests first for changed behaviour; use synthetic fixtures locally. Current platform observations go in ignored private storage. No missing capability, source fixture, string check or old screenshot proves native acceptance.

## Out of scope

Grant feature implementation, new Fabric infrastructure, assumed schedule/sharing approval, destructive history rewrite, automatic activity notifications and changes to an existing VM.
