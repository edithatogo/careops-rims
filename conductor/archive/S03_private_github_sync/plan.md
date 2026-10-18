# Sanitised private GitHub synchronisation: executable plan

Status: complete. Source-only synchronisation and remote readback are complete; Power Platform/native acceptance remains separate.

## S03.1 Inventory and safe candidate

- [x] S03.1.1: Verify origin and remote PRIVATE visibility; inspect remote branches before assuming it is still empty. Do not create a second repository.
- [x] S03.1.2: Inventory tracked files and all history intended for push. Report paths/categories, not secret values. Include tenant identifiers, connection exports, ZIP internals, cache/data exports and .git content.
- [x] S03.1.3: Prepare a sanitised source-only candidate in a separate temporary working directory, with an exclusion/remediation manifest. Preserve the original checkout and local history.
- [x] S03.1.4: Replace hardcoded runtime identities with private configuration and tracked example placeholders. Adapt tests/generators so the clean source package is usable without tenant credentials.
- [x] S03.1.5: Choose a clean source-only initial history; retain the original local history privately and do not rewrite or push it.
- [x] Checkpoint: write commands/results, changed paths and remaining blockers in review.md; update CURRENT_STATE. Stop dependent work on failure.

## S03.2 Verify and publish source

- [x] S03.2.1: Test the exact candidate with the harness, bootstrap its pinned Conductor dependency and scan every reachable Git object intended for upload. A clean working tree alone is insufficient.
- [x] S03.2.2: Confirm no synthetic test record is promoted into live data and no private receipts are staged. Keep authenticated configuration out of Git even though the remote is private.
- [x] S03.2.3: Commit the candidate with a source/version manifest and push the clean `main` branch to the existing private origin. No force-push or original-history rewrite was used.
- [x] S03.2.4: Read back remote commit SHA and PRIVATE visibility; the candidate and fresh extraction passed 319 checks and 258 tests, with private runtime dependencies explicitly absent.
- [x] S03.2.5: Document the source-only candidate, remote branch and safe sync boundary in CURRENT_STATE and GITHUB_SYNC.
- [x] Checkpoint: write commands/results, changed paths and remaining blockers in review.md; update CURRENT_STATE. Stop dependent work on failure.
