# Saved-paper library metadata

The existing library's **Title** (`Title`, Text,255 UTF16 code units) and
**Description** (`_ExtendedDescription`, rich-text Note; REST property
`OData__ExtendedDescription`) describe a verified current paper copy. No new
columns, content types or duplicate publication registry are required.

Title is filled only when blank, using the canonical publication title and
article version. An existing human title is preserved. Description contains a
marked `RIMS archive metadata v1` block with canonical publication key, DOI,
source, article version, licence, original retrieval time, content SHA256, the
original qualified source URL and a link to authoritative register provenance.
Original URLs retain their qualified non-sensitive parameters: PMC's verified
MD5 parameter, PLOS's exact DOI/printable selector and the register's exact item
ID. Token-bearing, unknown or mismatched query parameters are refused.

The complete register manifest, saved receipt and original source remain
sources of truth. Properties do not establish scientific review, a new licence,
affiliation, permission or authority to issue. No raw metadata envelope or paper
content is copied into Description. Existing human Description content is retained
before the managed block; a changed or malformed managed block is refused for
reconciliation rather than silently overwritten.

## Operator update and recovery

After the existing archival and actual saved-byte verification step, inspect the
exact current file/item, parent, access and version history through the qualified
M365 route. The snapshot has `parent`, `manifest`, `file`, `item`, actual `sha256`
and `bytes`, exact `item_url` and authoritative `register_url`. Include explicit
Description in the exact library-item read and request minimal OData metadata for
its ETag: file navigation alone may omit that ETag. Keep all snapshots/plans and
native bindings in ignored `private/ops/` paths.

```sh
python3 scripts/prepare_paper_library_metadata.py private/ops/paper-before.json private/ops/paper-plan.json
node scripts/apply_paper_library_metadata.mjs private/ops/paper-target.json private/ops/paper-plan.json private/ops/paper-update
```

Use the existing qualified client/profile, with interactive fallback blocked;
authentication recovery is a separate established workload operation. Target
configuration supplies `site_url`, `library_id`, register `list_id` and the
accepted paper `folder`. The updater refuses output outside a new private/ops
folder. The preparer pins the exact snapshot bytes. No command creates a field,
uploads content, rewrites a register manifest, renames or moves a file, shares it,
enables a flow or starts source retrieval.

Only a fully linked current paper is eligible. The file/item association, parent
identity, saved link, SHA256, checkout, existing field types and precise ETags
must match before one conditional two-field update. The transport rejects another
send or a mutation outside that item, and disables redirects. An unchanged replay
performs zero writes and therefore creates no metadata version or trigger loop.
A partial/uncertain response requires fresh readback of that same operation before
another submission. Do not delete the journal or assume a failed verification
means the metadata update failed.

SharePoint may encode rich-text entities or rewrite same-origin hrefs to relative,
space-encoded URLs. Compare only those qualified representations; preserve the
actual link target and visible text. Native acceptance requires saved properties,
unchanged current PDF SHA/length/stable identity/path, the unchanged parent/link/
manifest and unrelated item fields, unchanged access shape, all prior version
identities, and retrieval of the preceding version's identical PDF bytes.

A normal metadata update advances the file ETag and version while keeping content
unchanged. The manifest's earlier `verified_file_etag` remains historical content
verification evidence; it is not relabelled as the current metadata ETag. No
receipt is rewritten just to conceal that expected version change. Saved-but-
unlinked recovery receipts and older paper versions are outside this operation.
If a metadata reversal is needed, retain the new history and apply only the two
recorded preimage properties using a fresh ETag after confirming no intervening
human edit. Do not restore a whole PDF or discard its history.

This is an operator-run metadata step, not an unattended local Python runtime or
a new per-paper business approval queue. Future selected archived copies use the
same guarded step after integrity verification; old copies and collector envelopes
are not blanket-retrofitted.

## Native paper catalogue

A separate non-default catalogue uses the existing Name, Title, Description and
Modified columns. It is scoped to the paper folder and catalogued PDF copies with
a nonblank Title, sorted by Title. It does not change the original five views or
default library view. Use the folder-scoped entry link from the native field guide;
a library-wide recursive query can exceed SharePoint's list-view threshold. The
qualified native query uses `FolderServerRelativeUrl` and the view's exact CAML.
This view counts file copies, not distinct publications or approved research.

For a selected batch, qualify actual rendered columns and source/provenance
links, preserved history/access and a zero-write replay. Keep earlier copies
and recovery receipts outside the write scope. Retain implementation/query
recovery evidence privately; source retrieval and paper analysis are not needed.

Reference: [Microsoft's folder-scoped CAML query property](https://learn.microsoft.com/en-us/dotnet/api/microsoft.sharepoint.client.camlquery.folderserverrelativeurl?view=sharepoint-csom).
