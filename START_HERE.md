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
