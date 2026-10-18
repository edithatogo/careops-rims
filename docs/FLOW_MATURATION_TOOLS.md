# Flow diagnostics, recovery and source compatibility

These tools run locally against recorded or downloaded inputs. They do not call
Microsoft services, activate flows, send messages or establish native acceptance.
Keep real receipts and generated recovery packets in ignored private storage.

## Recorded diagnostics

Run `python3 scripts/powerplatform_tooling.py summarize-flowagent --receipt private/receipt.json`.
The projection handles combined run and paginated-action envelopes, retains control
statuses and withholds business payloads, signed links and raw error messages.
Tool failures cannot establish successful native observations.

## Definition recovery preparation

Run `python3 scripts/prepare_archive_definition_recovery.py --help` for inputs.
The preparer binds a Stopped workflow to its recorded environment, exact ID and
ETag. It prepares an inert Compose canary or restoration of the exact original
clientdata, rejecting unrelated definition, binding or timestamp-string drift.
Only the existing native owner may apply a qualified conditional update and verify
saved readback. Packet generation alone proves no restoration; portable solution
ZIPs are never edited by this route.

## Committed-source compatibility

`read_qgip_committed_source.py` reuses `grants_qld_qgip_api.py` to validate a
downloaded commit before projecting review candidates. Tests preserve unknown
additive fields and nested values, and reject breaking required types or future
major formats without replacing last-good output. Candidates are not admissions.
This public edition uses example resource GUIDs, including the QGIP adapter's
catalogue identifiers. Configure and qualify authoritative resource IDs privately
before live acquisition. The compatibility tests use synthetic responses and need
no service credentials.

CI runs these four focused test modules alongside existing operator, monitoring
and privacy checks. It does not claim the excluded private workspace's full suite
or tenant behaviour.
