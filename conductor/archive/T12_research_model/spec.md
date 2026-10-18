# T12_research_model: Replace the underlying model, not just its labels

## Outcome
Build a research-native semantic model and rebind the isolated report. Remove legacy employment semantics at model and report levels; do not merely hide or rename them.

## Dependencies
T11_sources_and_reconciliation

## Acceptance criteria
- All model fields and bindings are research-native, including hidden metadata.
- DORA-only items appear in counts and the register.
- Facility counts are labelled overlapping and are not summed into the HHS total.
- Native M/DAX execution and actual read-back are recorded, not inferred from local parsing.

## Evidence boundary
Native acceptance remains open until actual Power BI execution. A clean JSON/TMDL tree alone is insufficient.

## Safety and scope
Read `conductor/workflow.md` and `contracts/web-first-execution.contract.json`. Preserve the existing report/model until an approved, isolated write path and rollback are proven. Do not require Fabric Git integration, capacity purchase, public publishing or a new repository. Do not enter or expose credentials in Git or this pack.
