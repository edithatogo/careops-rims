# T15_web_acceptance_release: Verify the live web implementation and hand over

## Outcome
Accept the web implementation using actual runtime, source and export evidence. Preserve the existing production item until release approval and an exact restore/rebind path exist.

## Dependencies
T14_complete_exports_monthly

## Acceptance criteria
- Actual native/runtime evidence passes in addition to local tests.
- All three report pages and full/monthly exports agree with the same canonical dataset.
- Owner-approved deployment is recoverable and no accidental sharing or downstream impact occurs.
- Any remaining PBIX/download/schedule limitations are explicit.

## Evidence boundary
This is the preferred acceptance path. A successful browser implementation does not require a VM.

## Safety and scope
Read `conductor/workflow.md` and `contracts/web-first-execution.contract.json`. Preserve the existing report/model until an approved, isolated write path and rollback are proven. Do not require Fabric Git integration, capacity purchase, public publishing or a new repository. Do not enter or expose credentials in Git or this pack.
