# Start with the public source

Use Python 3.15.1 in an explicitly selected repository-local environment. Install the hash-locked workbook reader before running the full public suite. No Microsoft
sign-in, tenant, downloaded audit snapshots or private configuration is required.

```sh
git clone https://github.com/edithatogo/careops-rims.git
cd careops-rims
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes --only-binary=:all: -r requirements-runtime.lock
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

## Source-supported relationship preparation

The portable relationship tools project explicit OpenAlex, PubMed and study
reference evidence without authenticating people or inferring missing project or
award links. `scripts/source_relationship_evidence.py` retains available raw hashes, source
versions, review state and identifier ambiguity. PubMed rows reconstructed from
accepted metadata retain their batch/version identity but have no per-payload
raw hash; an empty RawSHA256 is explicitly unavailable provenance, not a verified
payload fingerprint. The generated report explains this limitation. Valid ORCID syntax is not proof
of account ownership; identical display names are never an identity crosswalk.
Grant references with source-scoped agency labels are distinct from reconciled
award-register identities. Missing publication/project/award links stay unknown.

`scripts/prepare_source_relationship_model.py` prepares an additive evidence table
from a supplied fresh semantic-model definition and the maintained M functions in
`config/`. It preserves existing source/review/unknown parts and refuses a repeated
application. `scripts/prepare_source_relationship_report.py` appends two pages to
an existing exported report with the required relationship and freshness baseline;
it preserves prior parts and requires an exclusive new output directory. Supporting
overview and relationship-page helpers are included, with fictional safety tests.
Use `--help` for input/output arguments. Keep native definitions, retained evidence,
bindings and generated outputs in ignored private directories.

These are local source-preparation tools, not an import/deployment command. The
existing native owner retains model/report binding, exact saved readback, refresh,
rendering, interaction, replay and same-object recovery. Save source revision and
artifact hashes in the private ALM manifest. A successful source suite does not
establish native behaviour, a complete funding chain or permission to share data.

Provider modification time, acquisition/observation time and model processing time
answer different questions. The latest timestamp among imported rows does not prove
complete coverage or a successful scheduled run. A missing qualified timestamp stays
unknown; refreshing retained bytes does not make their source current.

Source-stated author and institution identifiers describe publication co-occurrence.
Institution pairs do not establish partnerships or current employment, and distinct
identifier-pair totals do not count publications, employees or collaboration quality.
Preserve conflicting identifiers and unresolved mentions. Relationship evidence can
have different grains; do not sum them into one register total. Clear report
selections before comparing unfiltered counts. Enrichment snapshots remain immutable,
operator-qualified inputs; a new source generation requires its own reconciliation
and does not change collector schedules or human review states.

## Exact award identifier crosswalks

The crosswalk tools extend the existing source-relationship evidence rather than
merging award-register records. `scripts/award_identifier_crosswalks.py` requires
an independently evidenced funder namespace and the exact original award string.
`scripts/crossref_award_crosswalks.py` projects explicit publication/award edges
from a complete retained Crossref/ARDC packet, checks file hashes and lengths,
deduplicates assertions and keeps ambiguous canonical publication matches
unadmitted. Same-number grants from other funders and unproved prefix variants
remain unresolved. These assertions do not establish reviewed funding, identity
authentication or a DORA publication/project/award chain.

The two `prepare_*award*_model.py` adapters append those derivations to a supplied
fresh model preimage, preserving unrelated parts and refusing repeated application.
`prepare_award_crosswalk_report.py` extends the existing source-link page with
three visuals while retaining existing visual bytes. Supply qualified private
archive URLs, retained source packets and native preimages locally; this public
repository includes only reusable source and fictional tests. Use a new output
path and preserve human edits, source versions and previous outputs.

The M functions retain provenance supplied by the manifest; they do not themselves
recompute raw SHA256s. Independently verify retained packet bytes before native
use. Public Python preparation tests do not prove native M/DAX execution, report
rendering, solution membership or deployment parity. Existing native owners retain
model/report updates and their private ALM manifests.

## Explicit clinical-study award chains

`qualify_protocol_award_metadata.py` extracts explicit trial, protocol/version and
NHMRC application identifiers from a qualified protocol cover. It rejects missing
or conflicting identity fields and excludes adjacent MRFF numbers and later-page
co-mentions. `protocol_study_award_evidence.py` checks the retained packet hashes,
cover extraction, study identity, namespace authority and exact grant URI, then
combines explicit publication/study references into typed chain evidence.
Retain the original PDF, extracted cover, source envelopes and qualification
manifest privately. The caller must verify that the extracted page belongs to
the retained PDF; the projector does not perform PDF extraction itself.

Routine study-record updates preserve the historical qualification snapshot and
record the current study-register hash separately. References lacking a unique
canonical publication mapping stay unadmitted. A clinical-study chain is distinct
from a DORA project chain and conveys no reviewed funding or protocol approval.

`prepare_protocol_study_award_model.py` prepares the additive model change from
the accepted crosswalk preimage; `prepare_protocol_study_award_report.py` appends
four visuals to its existing page. The latter clarifies only the known maintained
chain-status wording and refuses human-modified wording. Use exclusive output
paths and retain source preimages, human edits and original identities. These
portable preparation checks do not establish native deployment or rendering.

## Grant-registry related publications

`registry_publication_crosswalks.py` projects typed RIF-CS `relatedInfo` publication
references through exact repository Handles and explicitly equivalent DOI fields.
It checks retained JSON/XML bytes and provenance, grant/funder namespaces and the
resolved repository item. DSpace requires one explicit DOI identity; a Figshare
`IsPublishedIn` relation is retained as source metadata and cannot supply identity.
Unmapped and identity-unknown references stay retained. `grant_related_publication`
does not establish fundedBy, a DORA project link or reviewed funding.

The registry model adapter reuses the existing bound study-site/library check;
the report adapter adds four visuals without replacing existing visual bytes and
refuses target-name collisions. Both require the accepted clinical-study preimage
and preserve the existing funding/clinical-chain measures. Actual source packets,
native exports and identities remain private. The M projector relies on prior
independent retained-byte/hash verification; portable tests and generated artifacts
do not establish native runtime, deployment or operator acceptance.

## Historical government award references

`government_award_crosswalks.py` reads a complete retained packet, verifies its
file hashes and workbook source contract, and matches exact Crossref award values
to the official NHMRC workbook's `APP ID`. Its relation is
`publication_government_award_reference`, targeting `nhmrc:` source keys. These
are historical references, not current award status, reviewed funding, ARDC
identities or DORA project edges. Prefix stripping and unsupported aliases are
refused. Ambiguous workbook IDs and conflicting duplicate evidence are refused.

`prepare_government_award_model.py` appends this evidence to the accepted registry
model contract using the bound study site's Documents library. The report adapter
adds four scoped visuals without overwriting existing visuals; repeat preparation
requires reconciliation. Keep original sources, human edits and native receipts.
Local fixtures do not establish native refresh, rendering or operational acceptance.

The workbook reader uses openpyxl with defusedxml XML protection and et-xmlfile.
Exact versions and distribution hashes are in `requirements-runtime.lock`, including
the qualified defusedxml preview. To update, regenerate with
`uv pip compile requirements-runtime.txt --no-config --generate-hashes --python-version 3.15.1 --output-file requirements-runtime.lock`
and qualify Python 3.15.1. CI audits this lock and
retains an external-dependency CycloneDX inventory beside the source package.
The source SPDX inventory covers the ZIP's actual project files; dependencies
are installed separately and are not vendored or covered by its file inventory.

The upstream workbook file entry must independently bind its `sha256` and integer
`bytes` to the retained workbook. Recomputing the outer packet hash cannot replace
that binding. Legacy source manifests containing only names and URLs require a separately
retained original-download receipt through `source_retention`. It must bind the
original manifest hash/length, same run and unique workbook hash/length with exact
CLI capture verified. Qualify a new immutable packet including that existing receipt,
retaining the original manifest and download/readback evidence. Do not invent hashes
from an unverified replacement or rewrite the previously accepted source snapshot.
The M function requires the same upstream digest/length references; independent
raw-byte SHA verification remains a prerequisite before native refresh.

Both `project_packet` and the model preparer require `trusted_upstream_sha256`
from an independently qualified record outside the input packet. Pin the original
source manifest digest when it contains byte bindings, or the original-download
receipt digest for the hashless route. The preparer embeds this explicit pin in
the M invocation. Never populate it automatically from the supplied outer manifest;
a receipt's self-declared capture flag alone is not an external trust anchor.


## Raw-backed archive compiler

`prepare_query_projection_archive.py --help` prepares a raw archive extension or
complete typed-page persistence fragment from independently qualified private
inputs. `prepare_pubmed_raw_source_capture.py --help` prepares retained raw-response
capture from an accepted private model preimage. Neither command applies its
candidate to a tenant. Keep every input, definition, payload and receipt under
ignored private paths; use the existing native-object owner for integration.

The archive extension preserves the existing trigger, connections and original
actions, adds exact raw-header/chunk/readback checks, and distinguishes retained
raw observations from accepted typed generations. Unknown nested fields and
original bytes remain retained. A text prefix protects timestamp transport from
connector date coercion; it is required and removed before exact comparison.
Existing-file conflicts, missing pages and generation drift are refused; rejected
typed projections never gain a commit marker. Verify the full selected native
run, stored bytes, marker and replay before reader adoption. Local tests and
prepared action graphs do not prove those operations or qualify a current reader.

The older fixed-baseline first-commit bootstrap remains historical. Its guards
now fail actions instead of returning diagnostic text, require explicit absence
before writing, bind readback to that same commit file, and preserve existing
local packages. This is a single-writer preflight, not an atomic concurrent-create
guarantee. It does not replace the qualified current raw-aware native publisher.


The two retained-native capture helpers require `main(token_provider=...)` through
an existing qualified VS Code wrapper. There is no built-in Azure CLI sign-in,
token acquisition, cached-client fallback or token-file transfer. The supplied
provider must independently validate the exact account, tenant and resource;
the callback itself is not authentication or target-access proof. Reuse existing
native capture routes until that wrapper is qualified; the offline compiler and
receipt validators remain usable without authentication.
