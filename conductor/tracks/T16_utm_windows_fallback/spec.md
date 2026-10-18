# T16_utm_windows_fallback: Finish the existing UTM Windows VM only if needed

## Outcome
Use the user's existing UTM installation and Windows 11 copy only after a verified web-authoring blocker and explicit fallback activation. Do not create a second VM blindly or bypass tenant policy.

## Dependencies
Entry track; conditional activation rules still apply.

## Acceptance criteria
- A genuine web-authoring blocker and owner fallback activation are recorded.
- The existing VM is preserved and host/guest architectures are matched.
- Windows boots with official updates/tools and without security bypasses.

## Evidence boundary
Not started. No connected device was available when this package was created. UTM configuration, licensing, storage and Windows setup stage remain unknown.

## Safety and scope
Read `conductor/workflow.md` and `contracts/web-first-execution.contract.json`. Preserve the existing report/model until an approved, isolated write path and rollback are proven. Do not require Fabric Git integration, capacity purchase, public publishing or a new repository. Do not enter or expose credentials in Git or this pack.
