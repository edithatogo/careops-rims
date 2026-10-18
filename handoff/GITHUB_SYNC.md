# GitHub synchronization

Requested and created on 2026-09-20: https://github.com/edithatogo/chhhs-research-publications (private).

The initial upload completed from a separate sanitised source-only candidate at
`e48e54bd73f97c7145436e24bba034ade55a3a7c`. The original local history remains
private and was not rewritten or pushed. The candidate excluded
`private/`, `downloads/canonical_live_artifacts/`, ZIP/bundle runtime exports
and Git history; runtime identities were replaced with tracked placeholders.

The canonical remote is the private `main` branch of
https://github.com/edithatogo/chhhs-research-publications. Later pushes must
come from a newly reviewed source-only candidate or a clean checkout of remote
`main`, never directly from the dirty original checkout.

The remote readback confirmed private visibility, default branch `main`, and
the published commit. The candidate passed 319 project checks, 258 tests and a
fresh-extraction source release with `NativeAcceptance=false`. Do not automate
background pushes or upload private receipts. GitHub synchronisation does not
prove Power Platform/native acceptance.
