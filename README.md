# RIMS public source edition

Sanitised development source for research-publication registers, exports and flow
support tools. Start with [setup and offline checks](START_HERE.md), then read
[scope](PUBLIC_SOURCE.md) and [security setup](SECURITY.md).

The deployed runtime uses Microsoft platforms. Local Python prepares artefacts and
checks source; it is not a hosted replacement. This edition includes example
identities, not working tenant configuration or native acceptance evidence.

- [Operator commands](docs/RIMS_OPERATOR_TOOLS.md)
- [Flow diagnostics and guarded recovery](docs/FLOW_MATURATION_TOOLS.md)
- [Architecture and historical implementation plans](conductor/index.md)

Historical plans describe the original private workspace. Private evidence,
generated outputs, native packages and live configuration are intentionally absent.

## Source CI and package qualification

CI preserves the strict RIMS full-history/current-source secret scans, privacy
guard and tenant-free public test runner, including its named private-workspace
exclusions and outbound-network denial. Shared immutable CareOps policy
`5cf006bce6c37c0c15db5d35055e302701a500ad` adds workflow checks; it does not
replace RIMS' stricter scanner flags. Canonical source tests use Python3.15.1
for every active application and tooling lane. Renovate remains the
sole updater and never automatically promotes a candidate.

Weekly/manual development candidates use separate integrity locks and verified
distributions in an isolated Python3.15.1 tool environment. PyYAML has a
hash-verified source-build exception for its missing Linux3.15 wheel; other tool
packages remain binary-only. A frozen official manifest selects newer previews
only within the3.15 line when available. Terminal outcomes and digests remain separate from promotion.
The workbook reader has three exact, hash-locked external dependencies.

The package workflow archives the clean, privacy-checked public source once,
then exercises its approved offline tests and operator help after unpacking.
The actual ZIP receives an SPDX file inventory. Main-only OIDC jobs download
the same bytes, verify all file/archive hashes and attest exact source/workflow
identity. Existing output revisions are preserved. The workflow grants no licence,
no release is published, and no native package or tenant acceptance is claimed.
Private configuration, source evidence and active native owners remain separate.

## Power BI PPU capability boundary — 22 October 2026

The deployment operator's current Premium Per User entitlement is verified.
Apply the [shared PPU qualification policy](https://github.com/edithatogo/careops/blob/main/docs/development-and-delivery.md#power-bi-premium-per-user-current-qualification-boundary)
to selected reporting/model work: evaluate XMLA and Power BI deployment pipelines
against exact workspace mode, role/Build rights and settings. Retain accepted
refresh/model evidence, report bindings, source revisions and recovery; the
existing private report/model and flow owners retain their objects.

PPU does not itself grant workspace roles, Fabric Git/Copilot capacity, access for
other readers, or Power Automate/Word/SharePoint generation entitlement. Report
Export-to-file REST is not supported on PPU alone; keep qualified alternative
outputs. No workspace conversion, sharing, schedule change or new reporting
dependency follows. Public source checks remain tenant-free and native operation
requires private deployment evidence.

## Stable CI helper environments

Stable source/security and package jobs verify Python 3.15.1 in
`.local/rims-ci` after checkout before invoking repository helpers. Existing
files, directories and symlinks are refused rather than replaced. The package
audit has a separate verified `.local/rims-audit` environment so audit tools do
not alter the unpacked operator runtime. Hash-locked workbook dependencies,
strict scanner flags, the public runner's five named exclusions and outbound
network denial, archive checks and main-only signatures remain mandatory.

The development canary uses a verified `.local/rims-canary-helper` interpreter,
separate `.local/rims-tool-canary` and `.local/rims-preview` candidates, and
explicit helper finalization after preview setup. If the helper is unavailable or
unverified, a shell-only failure receipt records setup blockage without running
ambient Python. Missing newer previews remain explicitly unavailable; a helper
pass does not establish preview qualification.
No helper setup grants native access, enables flows, sends email or establishes
production acceptance.

## Portable CareOps delivery contract

The [module profile](.careops/module.json) exposes this public edition's source
scope, shared interoperability standard and executable source/native task queue.
Package CI validates it through the existing immutable CareOps validator before
building an archive. The same profile travels inside the qualified source ZIP.

The public queue carries no private targets, operational records or native run
receipts. Existing native owners retain their objects, definitions and current
operations; source qualification does not establish their membership, access or
operational acceptance. Explicit email approval remains required for any send.
