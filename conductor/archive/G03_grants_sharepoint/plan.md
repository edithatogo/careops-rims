# Implementation plan

**Access scope:** authenticated current-user isolated DEV SharePoint and
manual flow operation, matching the publications development pattern. Shared
organisation-wide binding and unattended recurrence are future extensions.

- [x] Record scope and acceptance requirements.
- [x] Inspect current inputs, dependencies and relevant platform objects. The canonical G01 mapping and existing publication SharePoint conventions were inspected; no live grants object was found/read back in this tranche.
- [x] Implement: Generate the explicit additive `Grants Registry` schema and Power Query read definition with `OpportunityKey` as the only local identity.
- [x] Verify: Local schema/mapping parity is tested and the isolated DEV list has been created and read back with synthetic create/update/duplicate/concurrent-create/delete evidence. The reviewed-import flow has been read back Off with native Flow Checker 0 errors and 1 warning limited to the inactive state; controlled authenticated DEV replay proved synthetic create and same-key update, with the flow restored Off. On 2026-09-21 the existing flow was updated in place: the personal `Grants Registry` received the `SourceRowURL` Hyperlink column, and the Create/Update actions were read back with source-row and choice mappings. A fresh native package export contains those mappings and a current server modification timestamp. The synthetic replay row was subsequently deleted through the authenticated SharePoint UI and the API read back `ItemCount=0`. The existing semantic model reads the `Grants Registry` table as table 21 of 27 with 44 columns. This closes the current-user isolated manual-operation scope; shared organisation-wide target approval and unattended acceptance are future extensions.
- [x] Record local and live evidence separately before closure; isolated DEV writes are synthetic fixtures only, and the replay cleanup was completed with post-delete API readback.

## Phase: Review fixes
- [x] Task: Apply review corrections for the controlled native replay and preserve the remaining acceptance boundary (0536b98).

## Phase: Conductor review — 2026-09-21

- [x] Review the schema, flow contract, controlled replay receipt and native diagnostic-expression correction; retain G03 as in progress because target and operational acceptance are incomplete.
- [x] Task: Reconcile superseded historical replay statements and the current cleanup boundary (12574e7).
- [x] Task: Fail closed on malformed SharePoint targets and unresolved flow-package placeholders (007259d).
- [x] Task: Cover explicit SharePoint operation IDs and authentication metadata in the reviewed-import flow contract tests (3fc2c2f).
- [x] Task: Add an exact-one-match update guard so duplicate SharePoint matches cannot write (054aa2e).
- [x] Task: Add a standalone grants-flow validator and CI gate for the tracked definition (bcbee3f).
- [x] Task: Extend the validator to inspect generated private grants packages when present (0bb59fb).
- [x] Task: Persist reviewed `SourceRowURL` evidence in the canonical create/update mapping (working-tree review fix).
- [x] Task: Add regression coverage requiring the grants validator to remain in source-only CI (`35ef830`).
- [x] Task: Declare `OpportunityKey` required, indexed and unique in the tracked schema (`b8ee2a6`).
- [x] Task: Bootstrap from the existing native flow export where useful, reject the legacy importer’s duplicate-only route, add the missing native `SourceRowURL` column, and persist/read back the canonical in-place mappings (2026-09-21).

## Phase: Conductor review closure — 2026-09-22

- [x] Apply review fixes and reconcile the current-user native list, flow, model and cleanup evidence.
- [x] Confirm organisation-wide binding and unattended recurrence remain explicitly deferred extensions.
- [x] Archive this completed current-user track after local validation and remote synchronisation.
