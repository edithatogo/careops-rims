# Optional source-qualified publication and organisation references

This bounded adapter lets another module display evidence references without
owning RIMS records or requiring RIMS to be installed. It prepares JSON from an
already accepted, permission-filtered canonical snapshot. It performs no source
acquisition, person matching, affiliation inference, tenant writes or API calls.
Local Python is preparation/demo tooling; a deployed adapter must use the existing
Microsoft runtime and its qualified authentication and access boundaries.

## Existing authoritative fields

| Input | Reference meaning |
| --- | --- |
| Publication `CanonicalKey` | Exact ID within `careops-rims/publications`; no trimming, remapping or title matching |
| Publication `Title` | Display label only; never identity or scientific judgement |
| `OrganisationKeys` | Existing semicolon-separated organisational assertions; no new association is inferred |
| `OrganisationReferenceVersion` | Must match the selected organisation reference before a navigable link is prepared |
| `OrganisationMatchMethod`, `OrganisationMatchConfidence` | Preserved assertion state, including review-required/unknown; reference resolution is not confirmation |
| Reference `OrganisationKey`, `OrganisationName`, `version` | Exact ID, label and revision within `careops-rims/organisations` |
| Accepted snapshot context | Provider/consumer versions, source revision, capture time, purpose, classification and evidence URL |

The existing organisation hierarchy and canonical publication fields remain
sources of truth. An unmatched organisation or mismatched reference version yields
`unresolved_reference`, with no invented link. No ROR/ORCID identity, parent-child
relationship, research ranking or reviewed business relationship is inferred.

## Contract and compatibility

`careops-rims.references/1` declares provider and consumer versions, correlation ID,
`evidence-navigation` purpose, classification, timezone-aware capture time, source
revision, evidence URL, references and an idempotency key. Each reference carries
its source namespace, kind, exact ID/revision, label, evidence URL and explicit
organisation-link state. A maximum of 50 references keeps this first adapter bounded.
No raw affiliation text, personnel details, paper binaries, access tokens or
source payloads enter the minimum projection.

The producer requires an explicit allowed source/ID set from the existing access
layer. That supplied scope is an assertion by the operator, **not authentication**.
Real adapters must authenticate the caller and enforce current permissions before
export and again before display, including cached references. The fictional
consumer accepts only public-classification packets for its exact consumer,
provider and contract version. It rejects unknown fields, unsafe evidence URLs,
duplicate identities and unsupported versions. Evidence URLs are HTTPS without
credentials, query strings or fragments; use an authorised stable landing link,
not a token-bearing download URL. A hash proves content integrity, not identity,
authority, permission, source freshness or business acceptance.

An unchanged packet is idempotent even when its attempt correlation ID changes.
Conflicting content at the same revision is refused atomically. A new source
revision requires explicit reconciliation; this demo does not invent ordering for
opaque revision labels or silently replace a consumer's selected evidence. There
is no automatic deletion/cascade or authoritative record merge. An outage retains
last-good references with a stale/unavailable notice. Current denied scope hides
cached references and their source context. A missing adapter leaves the consumer's
own case usable and unchanged.

## Run the fictional demonstration

From the repository root:

```sh
python3 scripts/module_reference_adapter.py examples/module-reference-demo/input.json /tmp/rims-references.json
python3 examples/module-reference-demo/run.py /tmp/rims-reference-demo.json
python3 -m unittest discover -s tests -p test_module_reference_adapter.py
```

Outputs use exclusive creation: choose a fresh path on a repeat run. The fixture
is wholly fictional, with deliberately non-resolving `example.invalid` evidence
links. It is not a tenant/source acceptance sample. The consumer uses only the
Python standard library, imports no RIMS or sibling module, and preserves its own
case throughout connected, absent, unavailable, denied and conflicting-input cases.
The demo result contains the packet and each consumer view for inspection.

This completes the selected local compatibility demonstration. No native adapter,
solution dependency, remote endpoint, subscription, schedule, permission grant or
cross-module deployment is claimed. A selected live consumer would need its own
existing authority, current source readback, explicit revision reconciliation and
supported Microsoft deployment; absence of that future integration does not block
standalone RIMS or the demonstrated consumer.
