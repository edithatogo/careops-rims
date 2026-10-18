# Antigravity CLI (agy) / Plugin Handover

## Current delivery reference — 13 October 2026

Use the [shared-data delivery contract](docs/PLATFORM_COMPLETION_PLAN.md#shared-data-delivery-contract--13-october-2026). Historical completion labels below cannot close T11/E01 raw retention, T14 exports or T15 operational acceptance. All-source field completeness, exact-client permissions and native runtime readback remain scoped evidence requirements.


## Overview

This document records historical Antigravity setup. Current execution follows AGENTS.md and the shared-data delivery contract; tool availability and ownership are verified in the active session.

Read `conductor/index.md`, `AGENTS.md`, and `handoff/POWERBI_PLUGIN_START_HERE.md`. The active path is CLI/API-first on existing qualified resources, with BrowserOS neo fallback under shared-UI ownership. Reuse the existing report, isolated model and archive flow.

---

## Agent Environment & Customization Loading

Antigravity automatically discovers and loads configuration and skills across the following hierarchy:

1. **Workspace Rules & Guidance:**
   - [`AGENTS.md`](AGENTS.md): Strict workspace instructions, test gates, privacy boundaries, and approval requirements.
   - [`.agents/plugins/conductor/rules/conductor_antigravity.md`](.agents/plugins/conductor/rules/conductor_antigravity.md): GUI and sequential interaction rules for Conductor workflows.
2. **Workspace Skills (`.agents/skills/`):**
   - `conductor-status`: Parses tracks registry and plan files for overall project progress.
   - `conductor-implement`: Orchestrates phase and task execution.
   - `conductor-new-track`: Scaffolds new features or fixes.
   - `conductor-review`: Reviews completed work against quality gates.
3. **Global Configuration & Skills:**
   - Machine-global skills: `~/.gemini/config/skills/` (`asw`, `asw-loop`, `asw-review`, etc.).
   - Built-in Antigravity skills: `~/.gemini/antigravity-cli/builtin/skills/` (`agy-customizations`, `antigravity-guide`).

---

## Tooling & Verification Discipline

- **Shell Execution:** Always execute commands using the workspace Python environment (`python3`).
- **Integration-milestone verification commands (use focused checks for smaller changes):**
  ```bash
  python3 -m unittest discover -s tests -v
  python3 scripts/validate_project.py
  python3 scripts/webfirst_contracts.py validate
  python3 scripts/webfirst_contracts.py route --input private/ops/capabilities.json
  ```
- **Live Power BI Operations:**
  - Use qualified CLI/API operations first and BrowserOS neo only for a bounded native fallback with explicit ownership.
  - Changes are applied **only** to the isolated development model ([`private/ops/isolated-baseline-observation.json`](private/ops/isolated-baseline-observation.json)), never to the production report/model without an approved rollback path.
  - Exact target UUIDs, before/after states, and checksum receipts must be stored in ignored `private/ops/` paths.
  - Never commit workforce row data, API tokens, or tenant credentials to Git.

---

## Historical route and status claims — superseded as current acceptance

- **T08 (Web Capability Discovery):** Complete. The `web_first` route is established and recorded in `private/ops/capabilities.json`.
- **T09 (Execution Contracts):** Complete (local work package).
- **T10 (Isolated Baseline):** Complete (isolated canary persistence and rollback proven).
- **T11 (Sources & Reconciliation):** Complete (live PubMed/DORA ingestion, metadata storage and retention verified).
- **T12 (Research Model):** Complete (canonical reporting model, DAX readback, multi-source integration).
- **T13 (Web Visuals):** Complete (36 research-only visuals across three pages, legacy pods eliminated).
- **T14 (Complete Exports & Monthly):** Complete (full bibliography export engine, executive Word DOCX generator, flow packages).
- **T15 (Web Acceptance & Release):** Complete (handover package, versioning architecture, local artifact export).
- **Multi-Source Enrichment:** Complete (OpenAlex, Crossref, Dimensions, Scopus, Web of Science, ARDC RLA integrated into registry, enrichment pipeline, and seed datasets).
- **Historical platform deployment claims (not current acceptance):**
  - **SharePoint List:** 1,265 publications synced to `Publication Registry` (`{{SHAREPOINT_LIST_ID}}`), 500 major versions configured, 13 metadata columns created, 3 specialized views live.
  - **Power Automate:** In-place flow update of `{{FLOW_ID}}` via `sharepoint-upsert.zip`, OpenAlex HTTP enrichment, zero cloud sprawl.
  - **Executive Word Digest:** `reports/CHHHS-Publications-Monthly-2026-08.docx` verified and delivered.
  - **Power BI Service:** Semantic model `{{ISOLATED_MODEL_ID}}` evaluated via `config/native-canonical-check.dax` with 100% PASS on all 3 statements; three-page development report `{{ISOLATED_REPORT_ID}}` verified with 36 research visuals rendering cleanly and zero broken field errors.
- **T16 / T17 (UTM Windows / Desktop Fallback):** Gated conditional fallbacks; not activated because the web-first route is functional and accepted.
