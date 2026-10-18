# Implementation plan

**Access scope:** current-user isolated DEV list and manual readback only;
relationship data is not shared or delivered to other users in this tranche.

- [x] Record scope and acceptance requirements.
- [x] Inspect current inputs, dependencies and relevant platform objects. Existing publication `GrantIDs` are treated as award evidence candidates, not as opportunity identities.
- [x] Implement: Add typed, evidence-required relationships for awards, opportunity relevance and investigator affiliation, plus an additive SharePoint relationship-bridge schema and Power Query definition.
- [x] Verify: Local tests preserve the distinction between confirmed award links and candidate topic relevance; publication rows are not mutated.
- [x] Record local and live evidence separately before closure. The isolated DEV list exists with all eight canonical fields read back, and `RelationshipKey` is required, unique and indexed. On 2026-09-22 a synthetic evidence-bearing relationship was created and read back through the native SharePoint UI. The correlated Publication Registry receipt was unchanged before and after: 1,468 rows, 1,265 nonblank/distinct `CanonicalKey` values, no continuation link, SHA-256 `2b1b81200fe8e816bc15dce02ff80d4013c908925c2b855b777d241c595fe413`. The exact synthetic row was subsequently deleted through the native SharePoint `Delete?` confirmation and the list REST readback returned zero items; no publication item was mutated. Shared organisation-wide binding is a future extension.
- [x] Task: Fail closed on non-HTTP evidence links and unsupported relationship review statuses (7375728).
- [x] Task: Reject whitespace-only AwardID values for confirmed award relationships (e329641).
- [x] Task: Reject non-string relationship identities, evidence URLs and review fields without coercion (8cf6b4f).
- [x] Task: Declare `RelationshipKey` required, indexed and unique in the tracked schema (`2e39aee`).
- [x] Task: Complete a current-user synthetic relationship create/read/update/read/delete round-trip and read back the publication-list boundary (2026-09-21).

### Local relationship model projection — 2026-09-22

- [x] Add the eight-field source-preserving `GrantRelationships` projection to the canonical local semantic model using the existing SharePoint-only M query.
- [x] Preserve `RelationshipKey` as the bridge identity and retain `FromKey`, `ToKey` and optional `AwardID` as separate endpoint identities; add regression coverage.
- [x] Rebuild TMDL and update the reviewed source-only runtime baseline; local validation passes without claiming native binding.
- [x] Read back the relationship table through the authorised native Power BI model route. Power Query created and saved the `Grant Relationships` query from the authenticated QLD Health SharePoint list; the model readback showed `Grant Relationships table 27 of 27` with 30 columns and zero rows. Shared organisation-wide binding remains outside the current user-scoped evidence.

### Native invariant readback continuation — 2026-09-22

- [x] Read the authenticated personal `Grant Relationships` list through SharePoint REST: `ItemCount=0`; `RelationshipKey` is required, indexed and unique; all eight relationship fields are present.
- [x] Read the personal `Publication Registry` through SharePoint REST: `ItemCount=1468`; the current page returned all 1,468 rows with no continuation link, 1,265 nonblank `CanonicalKey` values, and no duplicate nonblank keys.
- [x] Capture a correlated before/after key-set receipt around a relationship round-trip. Before and after both read 1,468 rows, 1,265 nonblank/distinct keys, no continuation link, and SHA-256 `2b1b81200fe8e816bc15dce02ff80d4013c908925c2b855b777d241c595fe413`; the relationship row was visible in native SharePoint after save. Native deletion was separately confirmed through the exact-item SharePoint delete dialog and the list returned to zero items.

## Phase: Conductor review closure — 2026-09-22

- [x] Apply review fixes: reconcile stale cleanup/model-binding claims with the native SharePoint and Power BI readback above.
- [x] Confirm the current-user scope is complete; retain organisation-wide sharing and unattended delivery as explicit future extensions.
- [x] Archive this completed current-user track after local validation and remote synchronisation.
