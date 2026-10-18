# Power Platform CI/CD boundary

The local toolchain includes Microsoft Power Platform CLI (`pac`), Azure CLI
with the Azure DevOps extension, PowerShell and GitHub CLI. The repository
harness runs a read-only tooling preflight on every full local check.

The canonical repository also runs the source-only workflow at
`.github/workflows/local-quality.yml` on pushes to `main`, pull requests and
manual dispatch. It executes the unit suite, project/web-first/Conductor
validators, visual checks and the read-only Power Platform preflight. It does
not authenticate to or mutate the tenant. The workflow pins the hosted runner
to `ubuntu-24.04` and uses the Node 24-compatible `actions/checkout@v5` and
`actions/setup-python@v6` actions for reproducible source-only evidence.

Microsoft Power Platform Build Tools 2.0 are the preferred Azure DevOps task
family when this project has a Dataverse-backed, solution-aware deployment
path. PAC-based tasks should be kept on one Build Tools major version within a
pipeline. Use `pac solution pack`, `unpack`, `check`, `version` and the relevant
Build Tools tasks for solution source, static analysis and controlled import.

The current publication implementation is PBIP/TMDL plus SharePoint and Power
BI artefacts, not a Dataverse solution. Therefore PAC/Build Tools are a
preflight and conditional ALM route here; they do not prove SharePoint list
writes, Power BI model/report authoring, refresh, rendering, flow execution or
delivery. Those remain separate native readback gates. No service principal,
connection, pipeline, environment, schedule or solution import is created by
the local harness.

When a solution-aware grant/flow component is introduced, add an isolated
solution project and use Build Tools 2.0 or the equivalent PAC-based GitHub
action. Keep connection references and environment variables outside source
history, validate the exact exported artefact, and require target readback
after import.

## Microsoft action and test-engine decisions

The [`microsoft/powerplatform-actions`](https://github.com/microsoft/powerplatform-actions)
repository is a suitable GitHub Actions equivalent for the conditional
Dataverse/solution path. It should be introduced only with an isolated
solution, pinned action tags or commit SHAs, GitHub environment secrets, and a
post-import readback gate. It is not a substitute for SharePoint list,
Power BI semantic-model/report, refresh, or Power Automate run acceptance.

The [`microsoft/PowerApps-TestEngine`](https://github.com/microsoft/PowerApps-TestEngine)
is not adopted. Microsoft marks it deprecated and the repository is scheduled
for removal on 1 November 2026; it is a canvas Power Apps UI test engine, not a
Power BI or SharePoint acceptance tool. If a future RIMS canvas app is added,
use Microsoft's current Power Platform Playwright samples in a separate,
isolated regression track after confirming their support status. Browser
readback of the existing Power BI/SharePoint surfaces remains the acceptance
route for this repository.

Neither decision authorises credentials, environment creation, solution import,
publishing, schedules, or tenant writes from the local harness.

Local baseline:

```text
python3 scripts/powerplatform_tooling.py check
python3 scripts/agent_harness.py check --task all
```
