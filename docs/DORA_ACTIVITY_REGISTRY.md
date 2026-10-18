# DORA Activity Registry

The Queensland Open Data [Database of Research Activity (DoRA)](https://www.data.qld.gov.au/dataset/database-of-research-activity-dora) is a project/activity dataset, not the same entity as a DORA publication record. It is therefore stored as a separate RIMS registry and joined to publications or grants only through explicit reviewed relationships.

The current published datastore resource observed on 20 September 2026 exposed 19 source columns plus the datastore `_id` key and 442 rows. The collector discovers the latest active CSV datastore resource from CKAN `package_show`, pages through `datastore_search`, verifies the complete field set and count, and retains every source field unchanged. The source `_id` is the activity-row identity; `Project ID` is retained as source data but is not assumed unique. It does not convert a missing value into a claim or infer a publication from a project.

## Local implementation

- Collector: `scripts/dora_activity.py`
- RIMS export: `scripts/export_dora_activity.py`
- Machine-readable schema: `config/dora-activity-registry.schema.json`
- Tests: `tests/test_dora_activity.py`

Each receipt records the package/resource identity, resource hash and modification date, API route, observation timestamp, field set, row count, record hash and source-row identity hash. The raw activity records are written only to the caller-supplied ignored/private output directory; no live rows or contact details belong in Git, fixtures or third-party tools.

## RIMS target

The canonical target is a SharePoint list named `DORA Activity Registry`, separate from `Publication Registry`. It contains the seven provenance fields plus every current DoRA source column, including ethics/review references, project/contact fields, sponsor, dates, disease category, site structure, DORA authority and DORA consent. The schema is additive: a future source schema change must create a new version or fail closed; it must not silently drop a column.

The canonical local flow definition is `config/flows/dora-activity-registry-upsert.definition.json`, validated by `scripts/validate_dora_activity_flow_contract.py` and the source-only CI gate. `scripts/build_dora_activity_flow_package.py` is the only target-injection route and writes only to ignored `private/` output. It was imported into the isolated personal DEV SharePoint target after correcting SharePoint connector internal-name bindings. Two controlled manual runs proved create and same-key update, complete column/row-key readback, and cleanup back to zero rows; the flow was returned to Off. Native report integration, retained-history refresh, recurrence, notifications and unattended execution remain acceptance gates.

The current implementation proves local collection, preservation and export only. Creating or changing the tenant list, importing rows, and adding a report page require the existing isolated/native acceptance and readback gates. The source contains personal/contact fields, so any tenant implementation also requires the approved Queensland Health access and retention decision before unattended ingestion.
