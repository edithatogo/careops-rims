# Agent instructions

## Public source CI

For this public edition, use START_HERE.md and its tenant-free public runner.
The private CURRENT_STATE and full private harness inputs are intentionally absent;
that does not block isolated source CI. Preserve the five named private-suite
exclusions, outbound-network denial, strict secret/privacy flags and native
ownership. CI packaging and canaries never activate a native route or qualify
production acceptance. Keep receipts and tool caches in ignored .local paths.

## Current route precedence — 13 October 2026

Follow the [shared-data delivery contract](docs/PLATFORM_COMPLETION_PLAN.md#shared-data-delivery-contract--13-october-2026): CLI/API-first on qualified exact targets, existing archive bootstrap, complete raw payload/schema retention before vertical filtering, and one writer per file/object. Historical browser-first/no-CLI statements and dated completion claims do not override this direction. Preserve current source scope, permissions, isolation, rollback and explicit activation/delivery gates. The publications chat retains its current objects and checkpoint; shared-data work requires disjoint scope or explicit handoff.


Solo-repository harness: after the required entry documents, read `handoff/CURRENT_STATE.md`. Run `python3 scripts/agent_harness.py context --task grants` (or publications/organisation/platform) for targeted context. See `docs/SOLO_AGENT_WORKFLOW.md`. Use existing Conductor plans; keep one short checkpoint and avoid extra approval or project-management layers. `python3 scripts/agent_harness.py check --task all` runs the three required checks with the active interpreter and preserves failures. Local success never proves tenant acceptance.

Read conductor/index.md and handoff/POWERBI_PLUGIN_START_HERE.md first. Use the existing Git history and the user's existing Power BI report, not a new Fabric project.

Primary route: supported CLI/API operations qualified on the exact target, with BrowserOS neo fallback under shared-UI ownership. Reuse established discovery/isolation evidence unless inputs changed. Data querying is not authoring; T16/T17 remain conditional.

No shared/original model writes without an approved isolation/rollback path. No blind rename of old fields. Preserve source/date uncertainty. Full canonical bibliography and monthly exports must reconcile to model key sets. Synthetic fixtures are never live data.

Validation cadence: use changed-behavior tests and affected structural checks. Documentation-only changes need structural/link checks, not new mirror tests. Run `python3 scripts/agent_harness.py check --task all` at integration/release milestones or broad shared-contract changes. Native M/DAX, report rendering, live refresh and scheduled delivery remain separate gates.

Keep actual tenant IDs, screenshots, auth tokens, raw API snapshots and caches in ignored private paths. Do not copy old workforce row data to this repository or an unapproved third-party plugin. Do not change sharing, publish, enable schedules, purchase capacity or change an existing VM without the specific approval gate.

## Required Python execution

All active Python development, build, test, automation and CI execution uses
Python3.15, currently exact patch3.15.1. Use an explicit repo-local interpreter,
verify its version, and align constraints, locks and current setup instructions.
Older runners are not compatibility defaults; preserve only historical evidence
and intentional synthetic version tests. Do not replace a running environment.

PyYAML6.0.3 currently has no Linux CPython3.15 wheel. CI tool qualification permits
its hash-verified source distribution explicitly; other tool dependencies retain
binary-only installation. Keep the Python3.15 interpreter and test actual builds.
