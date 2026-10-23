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
`1373e971013724dfaa268e215a45505bb89300cd` adds workflow checks; it does not
replace RIMS' stricter scanner flags. Canonical source tests use Python3.15.1
with an additional minimum Python3.11 compatibility lane. Renovate remains the
sole updater and never automatically promotes a candidate.

Weekly/manual development candidates use separate integrity locks and verified
wheels in an isolated Python3.14.8 tool environment. Actual RIMS tests still use
Python3.15.1; a frozen official manifest selects a newer published preview only
when available. Terminal outcomes and digests remain separate from promotion.
There are no third-party application Python dependencies to lock.

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
