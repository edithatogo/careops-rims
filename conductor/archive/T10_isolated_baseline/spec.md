# T10_isolated_baseline: Protect the existing report and prove an isolated write

## Outcome
Establish a recoverable, isolated development target before any persistent write. A report copy that still references the original model is not isolation.

## Dependencies
T08_web_capability_discovery, T09_execution_contracts

## Acceptance criteria
- Original definitions/checkpoint and downstream dependencies are recorded.
- Development report points to a distinct development semantic model.
- A canary round trip and rollback actually succeed; no production or shared-model write occurs.

## Evidence boundary
Power BI web changes can autosave. Report-only copying is not sufficient protection.

## Safety and scope
Read `conductor/workflow.md` and `contracts/web-first-execution.contract.json`. Preserve the existing report/model until an approved, isolated write path and rollback are proven. Do not require Fabric Git integration, capacity purchase, public publishing or a new repository. Do not enter or expose credentials in Git or this pack.
