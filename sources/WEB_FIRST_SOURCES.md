# Primary-source verification for web-first tracks

Checked 12 September 2026. These are external product references, not proof that the user's tenant permits a feature. Local source findings are separately recorded in docs/WEB_FIRST_FINDINGS.md.

## WEB_MODEL: Power BI Service semantic-model editing
https://learn.microsoft.com/en-us/power-bi/transform-model/service-edit-data-models

Import-model Power Query, owner/write/build and tenant settings; edits can autosave; field renaming can leave downstream visual references stale. Feature applicability must be checked in the actual tenant.

## COPY: Copying reports
https://learn.microsoft.com/en-us/power-bi/connect-data/service-datasets-copy-reports

A report copy still references the original semantic model; copying is not model isolation.

## EXPORT: Export visual data
https://learn.microsoft.com/en-us/power-bi/visuals/power-bi-visualization-export-data

Export limits and active filters can limit output; verify row counts and identity sets instead of assuming a complete bibliography.

## PDF: PDF export
https://learn.microsoft.com/en-us/power-bi/collaborate-share/end-user-pdf

Report-page PDF is a report rendering route; a full bibliographic deliverable needs its own completeness check.

## MONTHLY: Scheduled refresh
https://learn.microsoft.com/en-us/power-bi/connect-data/refresh-scheduled-refresh

The regular scheduled-refresh UI does not offer a monthly interval; use an approved monthly Power Automate orchestration where appropriate.

## DYNAMIC: Data refresh
https://learn.microsoft.com/en-us/power-bi/connect-data/refresh-data

Dynamic data sources can block refresh; fixed base URLs with RelativePath/Query can qualify for documented exceptions. Test the actual query/tenant; no guarantee inferred.

## PBIX: PBIX download
https://learn.microsoft.com/en-us/power-bi/create-reports/service-export-to-pbix

Report-only and full-model downloads have distinct limitations; do not promise a full PBIX for every service item.

## UTM: UTM Windows guide
https://docs.getutm.app/guides/windows/

Match ARM64 or AMD64 media to the host; official guest tools and valid licensing. This project does not adopt installer-check bypass advice.

## DESKTOP: Power BI Desktop requirements
https://learn.microsoft.com/en-us/power-bi/fundamentals/desktop-get-the-desktop

Windows-on-ARM cumulative update requirement, WebView2/display requirements and limited certified virtual-desktop environments. UTM needs an empirical compatibility check.

## APPS: Connected apps in ChatGPT
https://help.openai.com/en/articles/11487775-connected-apps-in-chatgpt

Availability, plugin installation, provider authorisation and write permissions are separate. The exact user plugin was not exposed in the originating session.
