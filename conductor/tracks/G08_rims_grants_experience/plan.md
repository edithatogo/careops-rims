# Implementation plan

**Access scope:** the existing user's isolated RIMS/Power Platform route and
personal watchlist only. Shared subscriptions, cross-user notifications and
unattended delivery are future extensions.

- [x] Record scope and acceptance requirements.
- [x] Inspect current inputs, dependencies and relevant platform objects. Existing RIMS page design, planning helper and subscription scopes were inspected; native page inventory remains open.
- [x] Review fix: escape carriage returns as well as line feeds in calendar display fields (`a573598`).
- [x] Apply review fix: reject non-string opportunity/category/funder identities and malformed subscription rule objects before watchlist matching (`53d2419`).
- [x] Implement: Add local versioned policy validation and stable delivery-event idempotency keys for the future list-backed pages.
- [x] Verify: Local policy/subscription tests and isolated current-user list persistence pass. On 2026-09-21 the authenticated personal DEV SharePoint route created exactly one `My Funding Watchlist` list and exactly one `Funding Calendar` list after inventory confirmed neither existed. Read-only REST readback confirms the watchlist fields (`OpportunityKey` required/unique, `Scope`, `TargetKey`, `Active` default false) and calendar fields (`DeadlineKey` required/unique, `OpportunityKey`, `CalculatedDate`, `SourceURL`, `Cancelled` default false, `PolicyKey`, `ReviewStatus` default `Needs Review`); native synthetic calendar, watchlist and delivery-ledger rows were created/read back and subsequently removed through exact SharePoint delete confirmations on 2026-09-22, with each list returning zero data rows.
- [~] Complete the reminder ledger, calendar change/cancellation execution, native report refresh/reconciliation and delivery gates; keep cross-user delivery and unattended notifications disabled.
- [x] Record local and live evidence separately before closure; no report page, subscription, notification or calendar was created.
- [x] Harden future delivery idempotency keys to reject coercible identities and out-of-range offsets without creating ambiguous keys.
- [x] Make institutional policy and holiday validation reject non-object and non-string inputs without incidental type errors.
- [x] Review fix: require an explicit current-user key and return only that user's matching subscription (`a6e1602`, `db96224`).
- [x] Review fix: bind delivery-event idempotency keys to the explicit current user (`0b5c920`).
- [x] Review fix: constrain the watchlist `Scope` choice to `opportunity`,
  `category` or `funder`, preventing an untyped native subscription target
  (`6e1b43a`).

## Local review extension — 2026-09-20

- [x] Add deterministic iCalendar projection with versioned institutional dates, stable event IDs, tentative review state and explicit cancellation semantics; cover unknown/partial dates and duplicate-safe revisions with tests (f8d0262).

## Phase: Review fixes

- [x] Task: Reject duplicate projected calendar event UIDs before iCalendar emission (ecf3d43).
- [x] Task: Reject reversed policy ranges, malformed holiday dates and duplicate holidays (efd3abd).
- [x] Task: Require an authoritative HTTP(S) URL and stable opportunity key for exact-date calendar events (ba4f5b4).
- [x] Task: Reject malformed subscription rules and missing opportunity identity before candidate matching (b45b4e1).
- [x] Task: Reject non-string calendar opportunity identities, URLs and display fields without coercion (e03f17d).
- [x] Task: Reject non-string funder identities, including boolean false, before subscription matching (`cfc57b4`).
- [x] Task: Reject duplicate holiday dates during institutional-date projection (`d7019e0`).
- [x] Task: Require typed policy identity/version and effective-date fields before validation (`09adbe2`).

## Phase: Conductor review fix — identity isolation — 2026-09-22

- [x] Task: Reject surrounding whitespace in current-user, opportunity, subscription and delivery identity fields instead of silently collapsing access keys (`0f1fa21`).
- [x] Verification: focused planning/operations tests (35), full local suite (452 tests, 8 skipped), project checks (460), web-first contracts, Conductor validation and diff validation pass locally.
- [~] Native preference persistence, access isolation, calendar revision handling, refresh/reconciliation and delivery remain open.

## Phase: Conductor review fix — calendar change identity boundary — 2026-09-22

- [x] Task: Reject surrounding whitespace in calendar-change identities and source URLs instead of silently normalising them (`37ddc3d`).
- [x] Verification: focused calendar-change tests (4), full local suite (453 tests, 8 skipped), project checks (460), web-first contracts, Conductor validation and diff validation pass locally.
- [~] Native null-date import/readback, refresh/reconciliation and delivery remain open.

## Phase: Conductor review fix — calendar projection identity boundary — 2026-09-22

- [x] Task: Reject surrounding whitespace in exact-date `OpportunityKey` and `URL` values before event UID/evidence projection (`a9603ff`).
- [x] Verification: focused calendar tests (11), full local suite, project checks (460), web-first contracts, Conductor validation and diff validation pass locally.
- [~] Native null-date import/readback, refresh/reconciliation and delivery remain open.

## Phase: Conductor review fix — policy identity boundary — 2026-09-22

- [x] Task: Reject surrounding whitespace in institutional policy identities, effective dates and holiday dates before calendar UID/date projection (`3aa8999`).
- [x] Verification: focused planning tests (14), full local suite, project checks (460), web-first contracts, Conductor validation and diff validation pass locally.
- [~] Native null-date import/readback, refresh/reconciliation and delivery remain open.

## Phase: Calendar omission-boundary review — 2026-09-21

- [x] Task: Validate optional calendar display fields before omitting uncertain
  dates, so malformed typed data cannot disappear silently (`29d97cf`).
- [ ] Native pages, personal access, calendar change ledger and delivery remain
  open; local omission semantics do not certify tenant acceptance.

## Phase: Exact-date validation review — 2026-09-21

- [x] Task: Reject impossible ISO dates when a grant deadline is explicitly
  marked day-precision (`01231b6`).
- [ ] Native pages, personal access, calendar change ledger and delivery remain
  open.

## Phase: Holiday collection boundary review — 2026-09-21

- [x] Task: Reject malformed holiday collections explicitly in institutional
  deadline projection (`6ca91b0`).
- [ ] Native policy persistence, calendar delivery and notification acceptance
  remain open.

## Phase: Subscription container boundary review — 2026-09-21

- [x] Task: Reject malformed subscription containers before rule iteration
  (`a0c8d06`).
- [ ] Native preference persistence, access isolation and delivery remain open.

## Phase: Native current-user list bootstrap — 2026-09-21

- [x] Task: Inventory the personal DEV site and create the sole `My Funding Watchlist` and `Funding Calendar` lists only when absent; persist the minimal user-scoped schemas with inactive/cancelled defaults and read back the fields through the authenticated SharePoint API.
- [x] Task: Add current-user flow/page binding and controlled readback for the isolated lists, flows and saved report visuals; no cross-user delivery or unattended notifications were enabled.
- [~] Task: Complete the calendar revision ledger, refresh/reconciliation and delivery gates; keep cross-user delivery and unattended notifications disabled.

### Native persistence evidence — 2026-09-21

- [x] Controlled current-user calendar round-trip: created one synthetic deadline with an exact calculated date, authoritative HTTPS source URL, policy key and `Needs Review` state; read back all visible fields; edited the policy key and read it back; deleted the synthetic item and confirmed the list returned to zero rows.
- [~] Native page/report binding is evidenced for the isolated saved visuals and flow paths; revision ledger, refresh/reconciliation, reminder/change execution and delivery remain open.

The authenticated Power Automate designer was also checked for the next
current-user flow. It can expose the personal site as a custom SharePoint
address and resolve the `Funding Calendar` fields, but the manual-trigger
dynamic-content binding did not resolve reliably in the new designer. The
incomplete draft was discarded; no duplicate flow, invalid flow, schedule or
notification was saved.

### Native watchlist-flow bootstrap boundary — 2026-09-21

The existing reviewed-grants flow was cloned temporarily as a bootstrap
candidate for `My Funding Watchlist`. The designer resolved the personal
SharePoint list and its `OpportunityKey`, `Scope`, `TargetKey` and `Active`
fields, but the cloned trigger/parser still accepted the grants-opportunity
payload and could not supply a dedicated subscription scope/target contract.
The incomplete copy was discarded. The live flow inventory was read back at
three flows: the canonical publications flow, the reviewed grants flow and the
reviewed DoRA flow. No temporary watchlist flow remains. A dedicated local
watchlist input contract is required before another native copy is created.

- [x] Add the dedicated `funding-watchlist-v1` local schema and regression
  coverage for the current-user personal list. Native flow binding remains
  open until the trigger/parser uses this contract directly.
### Native dedicated watchlist flow — 2026-09-21

- [x] Add and validate a dedicated SharePoint-only `funding-watchlist-v1` manual upsert contract and target-injected package locally.
- [x] Import exactly one `CHHHS RIMS - Funding Watchlist - Reviewed Upsert` flow into the authenticated current-user DEV context; Flow Checker read 0 errors.
- [x] Run controlled synthetic create and same-key update cases. SharePoint readback showed the expected opportunity-to-category scope/target and Active changes; the flow was restored Off.
- [x] Delete the synthetic watchlist row through the SharePoint UI and confirm zero rows. Native report/page binding is evidenced for the saved visuals; refresh/reconciliation, calendar ledger and delivery remain open.

### Native dedicated calendar flow — 2026-09-21

- [x] Add and validate a dedicated `funding-calendar-v1` SharePoint-only manual upsert contract and target-injected package locally.
- [x] Import exactly one current-user DEV flow: `CHHHS RIMS - Funding Calendar - Reviewed Upsert`, flow ID `00000000-0000-4000-8000-6a5e8e327422`, using the existing SharePoint connection and the personal `Funding Calendar` list.
- [x] Native Flow Checker readback: 0 errors and 0 warnings while enabled; the only inactive-flow warning appeared after the flow was restored Off.
- [x] Controlled native create run `08584116266950718806813049204CU16` succeeded; SharePoint readback showed `synthetic-calendar-20260921`, `2026-10-15`, the authoritative source URL, `Cancelled=No`, the initial policy key and `Needs Review`.
- [x] Controlled same-key update run `08584116266295302685959687164CU15` succeeded; SharePoint readback showed `2026-10-20`, `Cancelled=Yes`, policy key `synthetic-policy-20260921-v2` and `Confirmed` without creating a duplicate.
- [x] Restore the isolated flow Off. The synthetic calendar row was subsequently removed through the native SharePoint delete confirmation and the list returned to zero data rows.
- [~] Native report/page binding is evidenced for the isolated saved visuals; institutional-date and reminder/change ledger, subscription isolation and calendar/notification delivery remain open.

### Native delivery-ledger flow — 2026-09-21

- [x] Add and validate the SharePoint-only `funding-delivery-ledger-v1` schema, flow definition and package builder locally; optional date/error fields are null-safe.
- [x] Create exactly one personal DEV `Funding Delivery Ledger` list. Native field readback confirms the twelve visible ledger fields, `Status` default `Pending`, versioning enabled with a 50-major-version limit, and zero rows before testing.
- [x] Import exactly one `CHHHS RIMS - Funding Delivery Ledger - Reviewed Upsert` flow and update that same flow in place after the first controlled run exposed an empty optional `SentAt` conversion defect. Flow Checker read 0 errors and 0 warnings after the null-safe repair.
- [x] Controlled native create run `08584116256446744665855863737CU13` exposed the expected optional-date defect; no row was written by that failed run. The corrected same-key run `08584116253756053128213151733CU27` succeeded after the update package was imported. SharePoint readback showed one row with `Revision=v2`, `Channel=email`, `Status=Sent`, `ScheduledFor=2026-10-02` and `SentAt=2026-09-21`; the flow was restored Off.
- [x] Remove the synthetic ledger row through the SharePoint UI and confirm zero rows. Native report/page binding is evidenced for the saved visuals; true subscription isolation and actual calendar/reminder delivery remain open.

### Native report page shells and model binding — 2026-09-21

- [x] In the existing current-user My workspace report, add and save `Funding Opportunities` and `Funding Calendar & Watchlist` pages through the Power BI web editor; switch back to Reading view and read back both page names and their scope/status text.
- [x] In the existing current-user My workspace semantic model, use the Power Query SharePoint Online List connector and the existing organisational-account connection to add read-only native queries for `My Funding Watchlist`, `Funding Calendar`, `Funding Delivery Ledger` and `Grants Registry`. Model readback now shows tables 22–25 with 26, 29, 32 and 44 columns respectively; the Grants Registry preview evaluated with zero rows and the other three previews evaluated with one controlled synthetic row each.
- [x] Add and save a native table visual on `Funding Opportunities` bound to `Grants Registry.Funder`, `Deadline`, `Eligibility` and `OpportunityKey`; Reading-view readback shows those headers. The native Grants Registry preview currently has zero rows, so no opportunity row is claimed.
- [x] Add and save native table visuals on `Funding Calendar & Watchlist`: the calendar visual is bound to `Funding Calendar.CalculatedDate`, `DeadlineKey`, `ReviewStatus` and `SourceURL`, and the watchlist visual is bound to `My Funding Watchlist.Active`, `OpportunityKey`, `Scope` and `TargetKey`. Reading-view readback shows all eight headers, the synthetic calendar row and the synthetic watchlist row.
- [ ] Refresh/row reconciliation remains a separate gate. Native table bindings are evidenced, but the page status text still contains the older phrase that semantic-model binding is pending; a bounded current-user text-box correction was discarded because the rich-text editor did not select the complete content. Receipt: `private/ops/2026-09-22-powerbi-g08-status-text-edit-reverted.json`.
- [~] Complete subscription isolation, calendar revision ledger and actual reminder/change delivery after the semantic-model refresh route is available; current-user flow/page binding is already evidenced above.

### Native synthetic-row cleanup — 2026-09-22

- [x] Re-read the authenticated QLD Health flow inventory filtered by
  `Funding`: exactly one disabled flow was visible for each of the four
  canonical grant-flow identities. Receipt:
  `private/ops/2026-09-22-powerautomate-g08-flow-inventory.json`.

- [x] Through the authenticated SharePoint UI, select only the exact synthetic delivery-ledger, calendar and watchlist rows and confirm each native `Delete?` dialog. Each item was sent to the recycle bin; subsequent list readback showed only the list header row and no synthetic item.
- [~] Refresh the saved report cache and re-read the bound visuals after cleanup. A native model refresh and a bounded retry both remained at `Processing queries and validating semantic model` and were cancelled through the native confirmation dialog; no refresh success is claimed. This must not be confused with unattended refresh or notification acceptance.
- [~] Retry the native `Schema and data` refresh after all three grant test lists read zero rows. The second bounded observation reproduced `Processing queries and validating semantic model` and was cancelled through the native confirmation; no refresh success or row reconciliation is claimed.

### Local PBIP/native grant-surface parity — 2026-09-22

- [x] Add canonical local Power Query/model projections for `FundingCalendar`, `MyFundingWatchlist` and `FundingDeliveryLedger`, keeping them separate from `GrantsRegistry` opportunity identity.
- [x] Rebind the local Funding Calendar and My Funding Watchlist pages to their dedicated current-user tables, matching the native visual field contract; local visual bindings and geometry validate.
- [x] Replace the frozen source-only runtime baseline with an explicit reviewed parity baseline. This changes local authored definitions only and does not certify the native semantic model or refresh.
- [x] Add the local source-preserving `FundingCalendarChanges` projection and fail-closed revision-diff helper. It records explicit date/cancellation revisions without creating events or sending notifications; native list creation and delivery remain open.
- [ ] Reconcile the local PBIP against a successful native model refresh and row readback; a 2026-09-22 retry remained at `Processing queries and validating semantic model` for 100 seconds and was cancelled. Receipt: `private/ops/2026-09-22-powerbi-native-refresh-retry.json`.
- [x] After confirming the target list was absent from the authenticated personal DEV workspace, create the isolated `Funding Calendar Changes` SharePoint list and read back all 13 canonical fields. `ChangeKey` is required, unique and indexed; `ReviewStatus` defaults to `Needs Review`; both cancellation fields default to false; the list has zero items and no synthetic row was written.
- [x] Create one native current-user copy of the existing calendar upsert flow after three bounded legacy imports were rejected as `MalformedFlowAssetFlowDefinition`; rebind the copy to `Funding Calendar Changes`, correct the quoted field expressions, and save it with native Flow Checker `Errors (0)` and `Warnings (0)`. The flow remains Off and no synthetic row was written.
- [x] Execute controlled create/update change-ledger cases and read back exact SharePoint rows, then restore the flow Off. Create run `08584115988253175752159968677CU24` and same-key update run `08584115987296857629538066289CU13` succeeded; REST readback showed one item, stable `Id=1`, the expected revision/date/cancellation/URL/review changes and no duplicate. The exact synthetic row was deleted through the native SharePoint `Delete?` confirmation and the REST endpoint returned zero items.
- [x] Implement the local null-preserving design for the optional `PreviousDate` edge: create and update now branch explicitly, omitting the SharePoint date property when null and mapping it only when present. The flow validator and package builder require both branches; local tests and all gates pass.
- [ ] Import the revised branch design into the existing native flow identity and prove null-date create/update/readback. The prior native run `08584115961596220678423119580CU22` failed at `Create item` because the connector received an empty string for `PreviousDate`; keep this native limitation open until the revised flow is accepted. Reconcile the saved report/model and prove actual calendar/reminder delivery separately.
- [~] Retry native update through the authenticated Power Automate import route. On 2026-09-22 the null-preserving package uploaded and was recognised as an `Update` for the canonical flow; the QLD Health SharePoint connection was selected, but the wizard kept `Import` disabled. No import was submitted and the flow remained Off. Receipt: ignored `private/ops/2026-09-22-powerautomate-g08-null-package-attempt.json`.
- [~] Recheck the native code view for the null-preserving branch. The QLD Health designer exposed the canonical loop and tenant list identifiers but reported `Cannot edit in read-only editor`; the staged local definition was rejected, no Save was enabled, and reload restored the unchanged flow. No second flow or partial draft was created.
- [~] Recheck the normal designer insertion route. A temporary nested `PreviousDate` condition was staged, but the existing downstream SharePoint action was not exposed reliably for complete branch verification; reload discarded the draft. No save or tenant mutation occurred. Receipt: `private/ops/2026-09-22-powerautomate-g08-designer-insertion-reverted.json`.
- [x] Read back the current-user Power Automate inventory: exactly one publications flow is enabled/scheduled and exactly one disabled copy exists for each grant/DoRA upsert flow; no duplicate flow identity was created.
