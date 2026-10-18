# CHHHS publications: web-first implementation package

**This is a Conductor implementation/handoff release, not a newly compiled PBIX or a verified live dashboard.**

Use your existing report in Power BI. Start in the chat that exposes your Power BI plugin: attach the package and paste the opening prompt in `handoff/POWERBI_PLUGIN_START_HERE.md`. Ordinary Power BI web authoring is the first route; no Fabric Git integration or new capacity is required by this plan.

Read `conductor/tracks.md` for the ten new tracks and `docs/WEB_FIRST_FINDINGS.md` for defects in the existing source baseline. The source has three pages and two sources, but native M/DAX and live-source acceptance still need to be performed.

## Files to use

- `handoff/POWERBI_PLUGIN_START_HERE.md`: plugin session's first read-only task.
- `conductor/tracks/`: specifications, plans, metadata, per-track prompts and reviews.
- `contracts/web-first-execution.contract.json`: routing, safe-write and evidence gates.
- `contracts/publication-export.contract.json`: full bibliography requirements.
- `scripts/webfirst_contracts.py`: local policy/structure checks.
- `scripts/export_publication_register.py`: complete CSV/print-ready HTML renderer, with synthetic/live labels.
- `handoff/UTM_FALLBACK.md`: gated existing-VM fallback, not the primary route.

## Local verification

```
python -m unittest discover -s tests -v
python scripts/validate_project.py
python scripts/webfirst_contracts.py validate
```

Do not call these native Power BI tests. They do not run Power Query, DAX, browser rendering, live refresh or flow execution.

## Current boundaries

The Power BI editor is not exposed in the originating chat, and Remote Desktop Commander returned no connected devices. No live report or VM was changed. This does not establish that the user's separate plugin-enabled session cannot edit.

The original employment-derived PBIX must not become the research release through cosmetic relabelling. Protect the original, prove model isolation, then replace the actual model/bindings in a development target. Do not reimport the supplied historical DORA rows.

Conductor upstream remains a pinned but unpopulated gitlink. Context, tracks, local gates and prompts are included and usable independently. No new remote repository or tenant resource was created.
