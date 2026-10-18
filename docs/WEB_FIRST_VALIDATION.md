# Validation boundaries and commands

Three independent levels must stay separate:

1. **Local source/policy checks**: the baseline schema/definitions, Conductor structure, safe-route and isolation policies, and synthetic full-register rendering. These run here without a Power BI account.
2. **Native Power BI checks**: M compilation, DAX evaluation, correct active model, refresh results and rendered report pages. These must run in the actual web environment or gated Desktop fallback.
3. **Operational acceptance**: authoritative live receipts, actual source coverage, full exported key sets, owner acceptance, and separately approved publish/schedule/delivery actions.

The frozen runtime manifest deliberately preserves a known-defective baseline so unreviewed drift is detected. Passing it does not mean the M source is corrected. T11/T12 must change the source and update the manifest after review.

```
python -m unittest discover -s tests -v
python scripts/validate_project.py
python scripts/webfirst_contracts.py validate
python scripts/webfirst_contracts.py route --input config/capabilities.template.json
python scripts/webfirst_contracts.py evidence --input config/live-evidence.template.json --evidence-root private/ops
```

The final two commands should fail closed on the blank templates. Evidence validation checks presence, hashes, target IDs and correlation; it does not authenticate a plugin output or prove that a human did what a receipt claims. An authorised reviewer must verify the records against the actual service.

## Render the synthetic export demonstration

```
python scripts/export_publication_register.py tests/fixtures/webfirst-export-synthetic.json new-output-directory
```

The output is complete CSV plus print-ready HTML and a hash manifest, clearly labelled SYNTHETIC. It does not create a PDF, query PubMed, retrieve Power BI data or change the live report. The renderer refuses existing output directories and validates exact fields, count, unique keys, key-set fingerprint, source labels and date precision. It escapes HTML and neutralises CSV formula-like text.

For live exports, obtain the expected count and key set independently from the same successful native refresh and filter context, not by counting an already truncated export. Bind the live snapshot/run ID and coverage note. Rows with unclear dates remain in the full register; unallocated months cannot appear in a monthly selection.

Power BI plugin operations are invoked only in a session where the actual tools are exposed. The helper scripts do not enforce external permission controls or themselves control that plugin. The workflow requires that their checks be run and reviewed before mutations/releases.
