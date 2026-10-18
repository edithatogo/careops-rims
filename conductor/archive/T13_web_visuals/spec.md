# T13_web_visuals: Implement the three-page publication report

## Outcome
Use the existing report as a visual reference while enforcing the approved three-page scope. Make the full publication register the primary output, with no unrelated dashboard additions.

## Dependencies
T12_research_model

## Acceptance criteria
- Exactly the three contracted pages exist and every visual has a stated publication-reporting purpose.
- No residual workforce/trial-proxy/impact content, broken field references or hidden legacy filters remain.
- Register entries reconcile with model counts under identical filters.
- Rendered browser evidence and persistence checks are recorded.

## Evidence boundary
Thirty-six visuals in v0.3 are a structural starting point, not a reason to add unnecessary content. Any change to that exact baseline must have an outcome-linked contract revision.

## Safety and scope
Read `conductor/workflow.md` and `contracts/web-first-execution.contract.json`. Preserve the existing report/model until an approved, isolated write path and rollback are proven. Do not require Fabric Git integration, capacity purchase, public publishing or a new repository. Do not enter or expose credentials in Git or this pack.
