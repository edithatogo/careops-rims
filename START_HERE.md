# Start with the public source

Use Python 3.11 or newer. The public checks use the standard library; no Microsoft
sign-in, tenant, downloaded audit snapshots or private configuration is required.

```sh
git clone https://github.com/edithatogo/careops-rims.git
cd careops-rims
python3 -m venv .venv
. .venv/bin/activate
python3 scripts/check_public_source.py
python3 scripts/check_public_docs.py
python3 scripts/run_public_tests.py
python3 scripts/rims_operator.py --help
```

Install Gitleaks and enable the clone-local commit hook using [SECURITY.md](SECURITY.md).
Gitleaks is a separate executable required for commits; Python tests do not install it.

## Which commands need private inputs?

| Command | Inputs and effects |
| --- | --- |
| `run_public_tests.py`, `check_public_docs.py`, `check_public_source.py` | Offline source checks; no tenant credentials. |
| `rims_operator.py compare`, `summary`, `recover`, `monitor` | Local files or recorded evidence; no native monitoring runtime. Use `--help` for exact arguments. |
| `prepare_archive_definition_recovery.py` | Private native preimage, exact workflow/environment/ETag; prepares packets without applying them. |
| Acquisition commands with `--fetch`, deployment scripts and native CLI instructions | Qualified real targets and existing authorised authentication; example IDs cannot be deployed unchanged. |
| Private harness `--task all`, `validate_project.py`, full test discovery | Historical private-workspace checks requiring excluded evidence/configuration; use the public runner here. |

Keep real inputs and receipts in ignored `private/` paths. Never replace examples
with tenant identities in committed source. No setup command deploys, enables a
schedule, changes access or sends notifications.

The public runner prints every excluded private-workspace module and its reason,
then runs the remaining suite with outbound socket connections blocked. It exits
nonzero on failures. Passing source tests do not prove Power Query/DAX execution,
flow runtime behaviour, output fidelity or production acceptance.


## Portable monthly report preparation

The report source is standard-library-only and does not install or run a hosted
Python service. `scripts/reconcile_full_month_exports.py` checks complete paired
full/monthly page chains against independently supplied key sets and generation
context. `scripts/prepare_structured_monthly_report.py` maps those accepted inputs
into complete report fields, retaining source values, nulls and uncertainty.
Use each command's `--help`; keep real inputs, template bytes and outputs in
ignored `private/` paths. These commands do not establish native provenance.

`scripts/prepare_structured_report_flow.py` exposes `build(site, reporting_parent,
reference, default_input_path)` for an initially stopped, manual Power Automate
flow using standard SharePoint and built-in actions. The caller supplies its
qualified existing site, reporting folder and Embedded connection reference;
no tenant configuration is bundled here. Its report-specific scaffold is inline
and has no collector dependency. HTML generation includes the complete supplied
bibliography, safe source links and a source/manifest history. It is a printable,
downloadable report, not automatic editable Word-template generation.

Generation writes a new revision folder and verifies source/report bytes before
writing the completion manifest. Replay of unchanged content skips writes;
changed or edited output is refused before writes. Preserve edited files and
use a new explicit revision for regeneration. A partial revision folder blocks
silent overwrite: reconcile it and choose a new revision. Verify the selected
native invocation route delivers any optional input; do not assume management
manual-run requests populate the trigger body. An explicitly configured immutable
input path is available. Deployment, native output acceptance, supported solution
membership and activation remain separate qualified operations. The public tests
use fictional fixtures and perform no tenant operations.

## Optional module references

[The bounded reference adapter and fictional consumer](docs/OPTIONAL_MODULE_REFERENCES.md)
prepare source-qualified publication/organisation references from accepted canonical
fields. The standard-library consumer works without RIMS or a sibling module and
preserves its own case during absence, outage, denied access, replay and conflicting
revision attempts. This is an offline compatibility demonstration, not a deployed
integration or caller-authentication proof. Use the documented commands with
fictional inputs; real source snapshots and receipts remain private.

## Paper-library metadata

[The operator guide](docs/PAPER_LIBRARY_METADATA.md) describes preparing and applying
a guarded metadata-only update to an existing linked paper. The preparation CLI
uses private snapshots; the native CLI requires an already-qualified M365 session
and exact private targets. It preserves human fields, authoritative provenance,
file contents and existing versions, and refuses drift. Unchanged replay makes
no writes. Neither command installs a service or activates a flow or schedule.
