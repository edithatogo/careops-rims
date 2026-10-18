# Implementation Plan: E04 Microsoft Fluent 2 Visual Polishing and IBCS Standards Alignment

**Access scope:** current-user isolated report authoring and visual readback
only. Do not broaden sharing or alter production bindings in this tranche.

## Phase 1: Geometric Grid & Spacing Audit
- [x] Task 1.1: Audit all visual elements in `powerbi/CHHHS Research Publications.Report/` to certify 8-point base grid compliance.
- [x] Task 1.2: Validate symmetrical 32px margins and 16px visual gutters across all 3 pages (`PublicationRegister`, `MonthlyPublications`, `SourceReconciliation`).
- [x] Task 1.3: Document mathematical coordinates in `docs/VISUAL_STANDARDS_SPEC.md`.

## Phase 2: Modern Visual Archetypes Specification
- [x] Task 2.1: Specify Modern New Card visual structure with reference labels for KPI tracking.
- [x] Task 2.2: Establish horizontal bar chart standards for clinical specialty and facility breakdowns.
- [x] Task 2.3: Design custom 320x200 hover tooltip canvas blueprint.

## Phase 3: Contrast & Accessibility Verification
- [x] Task 3.1: Validate color contrast against WCAG 2.1 AA standards.
- [x] Task 3.2: Confirm compatibility with standard Queensland Health corporate theming.

## Reopened acceptance audit — 2026-09-21

- [~] Reconcile the local geometry/contrast evidence with the current native report inventory and capture a production-report audit before closure. The 2026-09-22 readback shows six pages, including the two grants pages, while nine Clinical Analytics visuals still report field errors.

## Phase: Conductor review — 2026-09-21

- [x] Review local standards evidence against the current native report; the 2026-09-22 readback now shows six pages and nine Clinical Analytics visuals still have native field-binding errors, so E04 remains in progress.
- [x] Record the isolated authoring-route readback result; preserve the repair gate because the authenticated route returned an access-request error and no shared-model write was attempted.
- [x] Refine the blocker evidence: the workspace model view bootstraps the original model in its iframe and fails with module MIME errors/`NG04002`; no mutation was attempted.
- [x] Review fix: reject missing, non-finite, negative or non-positive visual geometry before claiming 8px-grid compliance (b747011).

## Native report audit refresh — 2026-09-22

- [x] Read back the current authenticated report page inventory and record the
  six visible pages, DORA table headers and nine Clinical Analytics visual
  errors in `private/ops/2026-09-22-powerbi-e04-native-audit.json`.
- [~] Reconcile the nine deployed Clinical Analytics bindings through an
  isolated authoring route. No shared-model write is authorised by this audit;
  the isolated repair route remains the required next gate.
- [~] Current-user Power BI edit-mode retry exposed the nine broken visuals and
  `Fix this` controls, but the visual grid intercepted normal clicks and the
  forced retry did not open a repair mapping dialog. No Save occurred; the
  report was returned to read mode. Receipt:
  `private/ops/2026-09-22-powerbi-e04-edit-repair-attempt.json`.
