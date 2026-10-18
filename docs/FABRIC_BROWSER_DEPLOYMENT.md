> HISTORICAL ONLY. Superseded by the user's ordinary Power BI plugin/web UI route. Do not execute this deployment plan. Read START_HERE.md.

# Browser-first Fabric deployment

This is the preferred deployment route when Power BI Desktop is unavailable.

## Intended topology

GitHub repository -> Microsoft Fabric Git integration -> semantic model + report -> scheduled refresh -> monthly distribution.

Only the two Fabric item folders under `powerbi/` need to be synchronised into the Fabric workspace. The semantic model is stored as Fabric TMDL under its `definition/` folder, and both items include `.platform` metadata:

- `CHHHS Research Publications.SemanticModel`
- `CHHHS Research Publications.Report`

The `.pbip` shortcut is useful for Desktop development but is not itself a Fabric workspace item. Conductor, tests, fixtures, audit files and documentation remain in Git and are not deployed as Fabric items.

## Browser steps

1. Create or open a Fabric-capacity workspace in `app.fabric.microsoft.com`.
2. Confirm the tenant/workspace setting permitting GitHub synchronisation is enabled.
3. Connect the workspace to the GitHub repository and the folder containing the two item directories above.
4. In Source control, review incoming changes and update the workspace from Git.
5. Open the semantic model settings and configure the two public web origins used by Power Query:
   - `https://eutils.ncbi.nlm.nih.gov`
   - `https://dora.health.qld.gov.au`
6. Set the `pNCBIEmail` model parameter to an operational contact address.
7. Run a controlled refresh and inspect `Source Reconciliation` before relying on counts.
8. Configure refresh. Power BI's ordinary schedule has no native monthly cadence; use Power Automate or a Fabric refresh pipeline for a true monthly trigger.
9. Configure report subscription/export only after a successful refresh and reconciliation review.

## Acceptance gates

Do not call the deployment production-ready until all are true:

- Fabric accepts both item definitions from Git.
- The semantic model refresh succeeds against both public sources.
- PubMed and DORA records appear in `Source Reconciliation`.
- DORA-only publications count in the headline publication total.
- An item present in both sources counts once.
- Ambiguous matches remain distinct and display `needs review`/ambiguous attribution state.
- No historical employment content appears anywhere in the report or semantic model.
- The monthly report uses the last complete Brisbane calendar month by publication date.

## Known external prerequisite

The connected ChatGPT GitHub integration can modify an existing repository but cannot create a new repository. Create an empty repository in GitHub first, then this project can be pushed into it or managed through your normal Git workflow.
