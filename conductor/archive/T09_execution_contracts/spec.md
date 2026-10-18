# T09_execution_contracts: Reconcile context and implement the execution gates

## Outcome
Create an executable, web-first work package with exact scope, safe-edit gates, reproducible exports and an explicit fallback decision. Local planning and policy tests must never be presented as live Power BI acceptance.

## Dependencies
Entry track; conditional activation rules still apply.

## Acceptance criteria
- New scripts run without Power BI, credentials or third-party runtime packages.
- Adversarial tests reject unsupported completion claims and unsafe edits.
- Ten tracks, handoff prompts and two gated fallback tracks are present.
- No live report, model, scheduled flow or VM is claimed to have been changed.

## Evidence boundary
Local implementation scope only; the current M/DAX definitions remain a source baseline awaiting runtime remediation and native execution.

## Safety and scope
Read `conductor/workflow.md` and `contracts/web-first-execution.contract.json`. Preserve the existing report/model until an approved, isolated write path and rollback are proven. Do not require Fabric Git integration, capacity purchase, public publishing or a new repository. Do not enter or expose credentials in Git or this pack.
