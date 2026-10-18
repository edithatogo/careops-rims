# Implementation Plan: E03 Open Access Mandate Compliance and Clinical Trial Linkage

## Phase 1: Taxonomy & Identifier Extraction Rules
- [x] Task 1.1: Formulate Open Access categorization aligned with the 2022 NHMRC Open Access Policy.
- [x] Task 1.2: Specify regex extraction rules for ANZCTR (`ACTRN\d{14}`) and ClinicalTrials.gov (`NCT\d{8}`).
- [x] Task 1.3: Document data dictionary extensions in `docs/OPEN_ACCESS_TRIALS_SPEC.md`.

## Phase 2: Ingestion Architecture
- [x] Task 2.1: Specify keyless Europe PMC REST endpoint schema.
- [x] Task 2.2: Map fields to SharePoint List columns (`OACategory`, `OALicense`, `TrialRegistryID`).
- [x] Task 2.3: Formulate DAX compliance measures (`[% Open Access Compliant]`).
