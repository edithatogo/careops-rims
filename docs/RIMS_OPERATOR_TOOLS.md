# RIMS operator shortcuts

Run from the repository root with Python 3. These are operator-side commands;
the deployed runtime remains on Microsoft platforms. They do not run flows,
change their state, modify records, activate monitoring or send notifications.
Only `retrieve --execute` and `retrieve-bundle --execute` contact Microsoft: they download existing files
through the already configured M365 CLI account. It does not start authentication.
Keep receipts, comparison output and downloaded records in ignored `private/ops`.

## 1. Summarise a saved run

```sh
python3 scripts/rims_operator.py summary private/ops/run-receipt.json
```

Reports the saved outcome, run identifiers, integer record counts, output paths,
and errors/warnings with their JSON field locations. Supported inputs include
ordinary JSON receipts, Flow run `properties`, HTTP response `text` objects and
connector JSON file-content bodies (`body.$content`, base64). Unknown wrappers
are not parsed as executable text. No links are followed and no run is retried.
Missing counts or locations stay absent. HTTP 200 alone reports outcome UNKNOWN.
A Completed refresh's warning messages remain visible; this command does not
convert transport or run success into output acceptance.

## 2. Find the next recovery step

```sh
python3 scripts/rims_operator.py recover private/ops/run-receipt.json
```

Matches the retained service error to the established recovery recipes below.
These excerpts keep this operator guide usable without importing the wider
implementation branch and its operational records. Several matches can
be returned; a match is a troubleshooting lead, not a fresh diagnosis or authority
to retry. Preserve the last-good output and exact submitted run handle first.

| Known signal | Next bounded step | Maintained instructions |
|---|---|---|
| `DMTS_MonikerWithUnboundDataSources` | Restore and read back exact previously qualified item connections before refresh. | [Recovery recipe](#2-find-the-next-recovery-step) |
| `Premium_ASWL_Error` | Check partition source discovery and bindings; the accepted fix used a literal SharePoint site. | [Recovery recipe](#2-find-the-next-recovery-step) |
| Reserved `Typed` DAX variable warning | Repair that expression, inspect calculated outputs and the affected refresh messages. | [Recovery recipe](#2-find-the-next-recovery-step) |
| HTTP 412 / `PreconditionFailed` | Reconcile the current row and obtain its exact ETag; no wildcard overwrite. | [Recovery recipe](#2-find-the-next-recovery-step) |
| `AADSTS70043` / explicit token expiry | Recover the exact workload through the established client/account/resource mapping, then check the target once. | [Recovery recipe](#2-find-the-next-recovery-step) |
| `AADSTS53003` | Stop unchanged retries; preserve the policy denial and use an existing permitted route. | [Recovery recipe](#2-find-the-next-recovery-step) |
| No known match | Read the affected action error and reconcile uncertain effects before selecting a cause-specific repair. | [Delivery workflow](SOLO_AGENT_WORKFLOW.md) |

No recovery command changes credentials, bindings, source expressions or records.

## 3. Evaluate a monthly occurrence

This exposes the existing `prepare_register_export_monitoring.py` evaluator.
Policy is explicit month, day 1 at 09:00 Brisbane, completion deadline noon.
All observation times require timezone offsets; the current clock is never used
to choose an occurrence or claim an observation window.

For an already saved native M365 run-list **array**:

```sh
python3 scripts/rims_operator.py monitor \
  --month 2026-10 --history private/ops/monthly-native-history.json \
  --environment-id "$RIMS_ENVIRONMENT_ID" \
  --dataverse-flow-id "$RIMS_DATAVERSE_FLOW_ID" \
  --runtime-flow-id "$RIMS_RUNTIME_FLOW_ID" \
  --as-of 2026-10-01T12:05:00+10:00 \
  --observation-start 2026-10-01T08:55:00+10:00 \
  --observation-end 2026-10-01T12:05:00+10:00
```

Add `--history-complete --reads-verified` only when those facts have been proved
for the exact identity, selected occurrence, full pagination and observation window.
The command cannot establish those facts. Native history alone cannot prove
successful persisted export readback; a Succeeded run can therefore remain UNKNOWN.
Manual `testFlow` runs cannot establish a scheduled occurrence.

Alternatively use `--evidence private/ops/monthly-evidence.json` instead of
`--history` and its identity flags. Normalized evidence has this shape:

```json
{
  "runtime_flow_id": "exact-runtime-flow-id",
  "history_complete": false,
  "reads_verified": false,
  "runs": []
}
```

Normalized runs use the existing evaluator's `run_id`, `flow_id`, `trigger_kind`,
`scheduled_for`, `started_at`, `completed_at`, `status`, `health_run_id` and
`output_readback_verified` fields. Timestamps are offset-bearing ISO8601 strings
or null. Success requires actual correlated health/output evidence; do not fill
these fields merely to obtain a green decision. Preserve source evidence beside
the packet. Wrong periods, malformed identities or incomplete observations remain
UNKNOWN. A complete, qualified observation with no occurrence after noon is MISSED.

This is manual evidence evaluation, not an independent observer, scheduler or
qualification of unattended operation. Exit 0 means evaluation completed; inspect
`decision.status` before any dependent action. No native effects follow evaluation.

## 4. Compare two saved flow definitions

```sh
python3 scripts/rims_operator.py compare \
  private/ops/flow-before.json private/ops/flow-after.json
```

Accepts raw definitions with `triggers`/`actions`, `{definition: ...}`,
Flow API `properties.definition`, or a Dataverse workflow row with JSON `clientdata`.
Reports JSON-pointer paths and before/after values for triggers, actions, nested
graphs, parameters, connection references, state and identity when captured.
Object-key order is irrelevant; array order and every definition property remain
significant. Secret-named fields and secure parameters are redacted in displayed
differences, while changes are still detected. Keep all comparison output private;
arbitrary business inputs and other potentially sensitive fields are not classified.

No state is invented if absent in an export. No connector annotation is silently
ignored: a service-added authentication reference is reported as a difference.
Use an already qualified native comparator for a commissioning gate requiring a
specific normalization. This convenience compares saved inputs, not live objects.

## 5. Retrieve an exact accepted export revision

Use an existing accepted manifest and its exact run identity. Select a file from
`files[].name` (including native ARC/researcher exports), or the `csv_file` /
`index_file` roles in printable-register manifests. Connector Get-file JSON
manifest envelopes are supported. Names must match exactly and ambiguities fail.

```sh
python3 scripts/rims_operator.py retrieve \
  --manifest private/ops/accepted-export/manifest.json \
  --revision "$RIMS_EXPORT_RUN_ID" \
  --file researcher-name-summary.csv \
  --site "$RIMS_SITE_URL" --folder "$RIMS_EXPORT_FOLDER" \
  --reference private/ops/accepted-export/researcher-name-summary.csv \
  --destination private/ops/retrieved/researcher-name-summary.csv
```

The default prints the exact M365 read command and expected hash without executing.
Add `--execute` to download. Use the existing qualified site/account and decoded
folder from saved native file metadata; do not derive resource identity from a
similar display name. If the manifest already contains a file Path, `--folder`
is unnecessary. Never use `latest` in place of the manifest run identity.

When the manifest contains the file's `sha256`, no reference is needed. Otherwise
supply accepted saved bytes with `--reference`, or an independently retained hash
with `--sha256`. Existing manifests that explicitly did not compute hashes remain
unchanged; a same-sized file or matching name is insufficient to accept a revision.

The helper calls `m365 spo file get --asFile` once, using argument arrays rather
than a shell. On success it verifies SHA256 before creating the destination with
exclusive-create semantics. Existing files are never overwritten. Each execution
keeps its command/manifest hash, downloaded bytes, stderr and final result in a
new `retrieval-*` folder beside the destination. Failure, timeout or mismatched
bytes leave that attempt unverified and preserve the requested destination.
M365 itself may retry read requests according to its installed client behavior.

This retrieves current stored bytes **only if they equal the selected accepted
revision**. If the remote file was changed/deleted, it refuses acceptance rather
than restoring SharePoint history or substituting another revision. Use the
existing recovery procedure for that case. There is no upload, restore, permission
change, token copying or automatic sign-in fallback.

All commands emit JSON. Exit 0 means the operation completed (or a retrieval plan
was prepared); exit 2 means invalid input, read failure or unverified download.
For compare, inspect `equal`; for monitoring inspect `decision.status`; for an
executed retrieval require `VERIFIED_EXACT_EXPORT_REVISION`.

Focused verification:
`python3 -m unittest discover -s tests -p test_rims_operator.py -v`

## Further operator conveniences

These extend the same command and leave existing JSON defaults intact.

### 1. Readable text

```sh
python3 scripts/rims_operator.py summary private/ops/run-receipt.json --format text
python3 scripts/rims_operator.py recover private/ops/run-receipt.json --format text
```

Every subcommand accepts `--format json|text` after its command name. Summary
text labels missing fields as not recorded; it does not hide warnings or infer
success. JSON remains the default for scripts and full structured details.

### 2. List export contents

```sh
python3 scripts/rims_operator.py list-export private/ops/accepted-export/manifest.json --format text
```

Shows the saved run identity, each listed file, byte count, SHA256 and verification
metadata where recorded. JSON also retains native file identity, ETag and version.
Absent hashes remain absent. Listing reads only the manifest; it does not check
remote file state. Printable-register manifests expand their resolved
`part_name_pattern` / `part_count` into all HTML part names, alongside CSV/index.
Unresolved flow expressions, invalid counts and ambiguous file names are refused.

### 3. Drill into failed actions

```sh
python3 scripts/rims_operator.py failed-actions private/ops/run-receipt.json --format text
```

Supports native named action objects with `properties.status`, nested `actions`
maps, and the monthly failure receipt's `actions` rows (`action/status/code`).
Returns failed/timed-out/cancelled action names, saved error codes/details and
matching recovery leads. Parent scopes and failed children remain separate.
Succeeded and skipped actions are not presented as failures. A failed run alone
is not a failed-action record. Missing action details stay unknown, and signed
action-content links are never followed or included by this drilldown.

### 4. Compare two receipts

```sh
python3 scripts/rims_operator.py compare-runs \
  private/ops/run-before.json private/ops/run-after.json --format text
```

Highlights changes in reported outcome, recorded counts, warnings/errors and
output locations. Both sets of recorded identities remain attached. Missing fields
are distinguished from fields present in the other receipt; no zero count is
invented. A changed output path may simply reflect a new run folder. Comparison
does not claim a repair caused success or that two runs use the same generation.
Different receipt schemas may produce field-path differences: inspect the JSON.

### 5. Summarise several receipts

```sh
python3 scripts/rims_operator.py summaries \
  private/ops/run-one.json private/ops/run-two.json --format text
```

Produces one table with the explicit file, recorded run identity, outcome, counts,
output paths and number of problem fields. It keeps caller order and never selects
the newest run, merges counts or discards a failed receipt. An unreadable file
gets its own UNREADABLE row and error; it does not suppress other supplied files.
Zero problem fields means no problem evidence found in that receipt, not an
independently healthy run. Exit 0 means the table was produced; inspect its rows.

### 6. Retrieve a complete bundle

```sh
python3 scripts/rims_operator.py retrieve-bundle \
  --manifest private/ops/accepted-export/manifest.json \
  --revision "$RIMS_EXPORT_RUN_ID" \
  --site "$RIMS_SITE_URL" --folder "$RIMS_EXPORT_FOLDER" \
  --reference-directory private/ops/accepted-export \
  --destination private/ops/retrieved/export-bundle --format text
```

The default plans **every** manifest-listed file, including printable HTML parts.
Add `--execute` for read-only M365 downloads. All identity, path, destination and
expected-hash checks must pass for the entire bundle before the first download.
Hashes come from each manifest entry or accepted bytes with the same basename
under `--reference-directory`; a manifest hash must agree with supplied reference
bytes. Reference files are unnecessary for entries with a recorded SHA256.
Distinct remote files with colliding local basenames are refused before effects.
The selected manifest itself is not downloaded unless it is one of its listed files.

Each file is downloaded to a new private `bundle-retrieval-*` attempt directory,
checked against its expected SHA256, and recorded separately. Any download error,
nonzero CLI result, timeout or mismatch stops the operation without accepting a
partial bundle. Download failures leave the final destination absent. Only after
all files verify does the helper exclusively create the requested new directory
and link the verified files into it. An existing or competing destination, even
an empty directory, is preserved.

The final `.rims-bundle-receipt.json` is created last and must report
`VERIFIED_COMPLETE_EXPORT_BUNDLE` with every file VERIFIED. If local publication
is interrupted, the destination may be incomplete and lacks that completion
receipt; preserve the attempt and choose a new destination after reconciliation.
Do not treat the existence of a directory or some files as a complete bundle.
The reserved receipt name and ambiguous file names are rejected. This operation
does not restore SharePoint versions or upload any content.
