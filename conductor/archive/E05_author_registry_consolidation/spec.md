# Specification

## Overview

Create a conservative, derived author registry from the publication system without changing the canonical publication register or treating name-only matches as confirmed identities.

## Requirements

- Preserve source, author order, affiliation evidence, identifiers, URLs, and review state.
- Support PubMed structured author evidence and DORA author records.
- Provide deterministic identity states and author statistics with completeness disclosed.
- Keep ResearchGate discovery-only and review-gated.

## Acceptance criteria

- Local builder and regression tests pass.
- Documentation contains MoSCoW requirements and Mermaid flow.
- No live platform object is duplicated or changed by this track.
