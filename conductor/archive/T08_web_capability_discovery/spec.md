# T08_web_capability_discovery: Prove the plugin and web UI capabilities

## Outcome
Identify the existing Power BI report and its actual semantic model. Discover, rather than assume, which operations the user's Power BI plugin and ordinary Power BI Service web UI can perform.

## Dependencies
Entry track; conditional activation rules still apply.

## Acceptance criteria
- Exact existing report and model IDs are recorded privately.
- Each required capability has actual tool or UI evidence; untested means unknown.
- A documented operation-by-operation route is selected without Fabric Git/capacity prerequisites.

## Evidence boundary
The plugin directory exposed no identifiable Power BI editor in this chat on 2026-09-12. Remote Desktop Commander returned an empty device list. These observations do not establish a limitation in the user's other plugin-enabled session.

## Safety and scope
Read `conductor/workflow.md` and `contracts/web-first-execution.contract.json`. Preserve the existing report/model until an approved, isolated write path and rollback are proven. Do not require Fabric Git integration, capacity purchase, public publishing or a new repository. Do not enter or expose credentials in Git or this pack.
