# Codex / plugin handover

> [!NOTE]
> Active development has transitioned to **Google Antigravity (`agy`)**. See [AGY_HANDOVER.md](AGY_HANDOVER.md) for current Antigravity environment, skill loading, and agent execution guidelines.

Read START_HERE.md, conductor/index.md and handoff/POWERBI_PLUGIN_START_HERE.md. The current route is the existing Power BI report through its actual plugin/web UI, not Fabric Git deployment.

Preserve baseline Git history, detect uncommitted work, use the dependency-satisfied track, and record exact operations and evidence. Do not assume tool capabilities, target IDs, native validation, file conversion or a completed flow. The two UTM/Desktop tracks are conditional only.

For a missing Microsoft connector, create a concrete handoff for the user's plugin-enabled session rather than automatically falling back to a VM. The source's known runtime defects are listed in docs/WEB_FIRST_FINDINGS.md.
