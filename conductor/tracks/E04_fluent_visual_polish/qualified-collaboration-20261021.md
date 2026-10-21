# Identifier-qualified collaboration summaries

The optional source extension adds four measures and five visuals to the existing
collaboration page. Researcher pairs require checksum-qualified, source-stated
ORCID keys; corroboration requires the same publication and ordered pair in at
least two retained providers. Names remain display labels. Counts do not establish
authenticated identity, employment or institutional agreements. Existing
institution summaries retain explicit provider/Ringgold identity boundaries.

Reusable source: `scripts/prepare_qualified_collaboration_measures.py` and
`scripts/prepare_qualified_collaboration_report.py`. Both produce candidates;
neither authenticates, deploys or changes a native object. Model preparation
retains the evidence partition and unrelated parts and refuses repeat insertion.
Report preparation requires the accepted layout and card template, preserves old
visual IDs, adds four cards plus a scope note, and adds relationship-kind filters
to three source charts. Existing filters require reconciliation rather than
replacement. Keep source/candidate/preimage separate and preserve original
bindings through native promotion and recovery.

The private implementation commits are
`7239a374697ec7e300ff5ba2f942cd8ab74d5c39` and
`0644a10b70794d6116e16912253b409106cf1766`. Their terminal source/artifact
manifest was independently hash-verified for this public port. The reported
selected native outcome retained all 210 earlier visual IDs and 227 earlier
parts byte-exact, with page height and three chart filters changed and five new
visuals: final 236 parts, 14 pages and 215 visuals. Four original bindings and 33
previous metrics were preserved. The selected source counts were 5,105 qualified
researcher pairs across 256 publications and one pair/publication corroborated
across providers. These are time-specific observations, not public fixtures or a
claim that another deployment has been qualified.

The declared remote visual schema was unavailable; full remote-schema validation
is not claimed. Native web rendering/readback supplied selected output evidence.
The public source tests separately cover corroboration, exclusions, preservation,
layout guards and replay refusal. Raw definitions, screenshots, source records,
authentication material and private operational receipts are excluded.

A publication → DoRA project → award chain remains unsupported. Fresh reads of
709 retained publication metadata records and 442 activity rows lacked explicit
qualified connecting identifiers. Do not substitute title/person similarity,
adjacent funding statements or another institution's project links. This factual
source gap is independent of the delivered collaboration extension. Existing
native object owners retain further integration and documentation publication.

## Public review correction: provider selection

The public candidate now establishes cross-source corroboration before applying
the selected-provider membership. Otherwise clicking one provider removes the
second provider before qualification and makes corroboration incorrectly zero.
The candidate clears only the provider column when establishing support, then
intersects the corroborated publication/pair keys with the selected-provider keys.
See Microsoft's [REMOVEFILTERS](https://learn.microsoft.com/en-us/dax/removefilters-function-dax)
and [INTERSECT lineage semantics](https://learn.microsoft.com/en-us/dax/intersect-function-dax).
The independent row-grain reference tests cover each provider, absent provider
and empty selection. Report output must also remain outside its source folder.

These are public source fixes, not a new native acceptance receipt. The native
owner must take a current preimage, update the two existing corroboration
expressions without duplicating measures, and recheck unfiltered counts plus
provider selection/reset in the existing report. Preserve the other measures,
report parts and bindings; restore the two expressions from the preimage on
failure. Do not rerun the append-only preparer against an already-extended model.
