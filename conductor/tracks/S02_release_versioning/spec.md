# Reproducible source and deployment versioning

## Outcome

Generate trustworthy build identities and separate source release, private tenant snapshot and accepted data batch versions without a new hosted service.

## Inputs and edit scope

scripts/package_release.py; docs/VERSIONING_ARCHITECTURE.md; scripts/agent_harness.py; config/agent-harness.json; contracts/runtime-baseline.manifest.json

Read [execution protocol](../../PUBLICATION_STABILISATION.md) first. Add focused tests and safe configuration examples as required. Other files require a stated dependency reason in review.md. Preserve unrelated edits.

## Acceptance

Every task in plan.md must have evidence. Tests first for changed behaviour; use synthetic fixtures locally. Current platform observations go in ignored private storage. No missing capability, source fixture, string check or old screenshot proves native acceptance.

## Out of scope

Grant feature implementation, new Fabric infrastructure, assumed schedule/sharing approval, destructive history rewrite, automatic activity notifications and changes to an existing VM.
