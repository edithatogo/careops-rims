# T14_complete_exports_monthly: Export every citation and stage the monthly workflow

## Outcome
Produce complete bibliographic exports, not just report-page screenshots. Stage a reliable, monthly refresh/validate/export/archive process using existing approved Power BI and Power Automate capabilities.

## Dependencies
T13_web_visuals

## Acceptance criteria
- Every expected canonical record appears exactly once in full register exports.
- Human-readable bibliography is not clipped or silently limited by a report visual.
- Dry run and failure handling have actual receipts before any schedule activation.
- No flow deployment, monthly schedule or email send is claimed without evidence.

## Evidence boundary
The full-register renderer can be tested locally on synthetic data now. Live extraction, PDF rendering and scheduled delivery require the authorised Power BI/Power Automate environment.

## Safety and scope
Read `conductor/workflow.md` and `contracts/web-first-execution.contract.json`. Preserve the existing report/model until an approved, isolated write path and rollback are proven. Do not require Fabric Git integration, capacity purchase, public publishing or a new repository. Do not enter or expose credentials in Git or this pack.
