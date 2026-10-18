# Specification

## Overview

Build a locally testable grants and funding opportunities registry that can later be persisted in the existing SharePoint/Power Platform pattern and consumed by Power BI. One canonical normalized opportunity record may have many source observations.

## Functional requirements

- Normalize RSS, Atom, and API records into one canonical opportunity schema.
- Preserve source URL, source identifier, raw dates, retrieval time, and raw evidence hash.
- Keep eligibility, geography, funder, amount, deadline, status, and contact fields explicit and nullable.
- Detect duplicates using stable identifiers first, then conservative URL/normalised-title candidates.
- Mark uncertain dates, eligibility, and duplicate matches for review.
- Keep closed, withdrawn, and superseded opportunities rather than silently deleting them.
- Produce a SharePoint-compatible field map and Power BI-ready export contract.
- Make source adapters pluggable without allowing a source to overwrite another source's evidence.

## Non-functional requirements

- No credentials or source payloads in Git; private receipts remain ignored.
- No claim of complete funding coverage from a finite feed set.
- No automated submission, application, notification, or external sharing.
- Deterministic, idempotent local processing with unit tests.

## Initial source policy

- RSS/Atom: preferred low-friction discovery route where official feeds exist.
- Public APIs: use only when documented, permitted, and valuable beyond feeds.
- ResearchGate is not relevant to funding authority; funder/agency source pages remain authoritative.
- Human review is required for ambiguous eligibility, dates, duplicates, and inferred CHHHS relevance.

## Acceptance criteria

- A canonical schema and builder exist locally.
- RSS/Atom-shaped records and API-shaped records normalize into the same model.
- Duplicate and date-uncertainty tests pass.
- Documentation includes MoSCoW requirements, Mermaid architecture, SharePoint field mapping, and platform canonicalization rules.
- Required repository checks pass.

## Out of scope

- Live SharePoint list creation or modification.
- Power BI report deployment, scheduled delivery, or notifications.
- Automated grant application or eligibility decisions.
- Scraping sites that prohibit automated access.
