# Sanitised private GitHub synchronisation

## Outcome

Synchronise reviewed source to the already-created private GitHub repository while preserving local history, private artefacts and uncommitted user changes.

## Inputs and edit scope

handoff/GITHUB_SYNC.md; AGENTS.md; .gitignore; .gitmodules; scripts/package_release.py; scripts/download_canonical_artifacts.py; git history and exact proposed Git objects

Read [execution protocol](../../PUBLICATION_STABILISATION.md) first. Add focused tests and safe configuration examples as required. Other files require a stated dependency reason in review.md. Preserve unrelated edits.

## Acceptance

Every task in plan.md must have evidence. Tests first for changed behaviour; use synthetic fixtures locally. Current platform observations go in ignored private storage. No missing capability, source fixture, string check or old screenshot proves native acceptance.

## Out of scope

Grant feature implementation, new Fabric infrastructure, assumed schedule/sharing approval, destructive history rewrite, automatic activity notifications and changes to an existing VM.
