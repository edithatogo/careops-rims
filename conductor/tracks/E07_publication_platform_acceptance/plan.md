# Implementation plan

**Access scope:** current-user isolated publication list/flow/report route and
manual readback, matching the publications development pattern. Organisation-
wide sharing and unattended recurrence are future extensions.

- [x] Phase 1: Review current publication platform claims against protected evidence
- [x] Phase 2: Define canonical SharePoint/flow/model acceptance gates
- [x] Phase 3: Correct completion language and document connector boundaries
- [ ] Phase 4: Run an isolated live SharePoint create/replay/update test
- [ ] Phase 5: Verify concurrency, failure safety, key-set reconciliation, refresh, and report readback
- [ ] Phase 6: Add monitoring evidence and close the track only after terminal platform proof
- [x] Phase 7: Add versioned organisational hierarchy enrichment locally with evidence/confidence fields
- [ ] Phase 8: Read back additive organisational columns in SharePoint and run a controlled backfill
- [x] Review fix: require SharePoint connector and lookup-target parity for create/update writes (9001654).
- [x] Review fix: require explicit `GetItems`, `PostItem` and `PatchItem` operation IDs plus connector authentication metadata (6230e1e).
