<#
.SYNOPSIS
    Deploys the "Publication Registry" SharePoint List schema for CHHHS research publications.

.DESCRIPTION
    Creates the list, adds all typed columns, configures indexing on key query fields
    to avoid the 5,000 item threshold, and establishes default views for staff triage.

.PARAMETER SiteUrl
    The absolute URL of the SharePoint Site or OneDrive (e.g. "https://<tenant>.sharepoint.com/sites/CHHHS-Research").

.EXAMPLE
    .\Deploy-SharePointList.ps1 -SiteUrl "https://example.sharepoint.com/sites/Research"
#>

[CmdletBinding()]
param(
    [string]$SiteUrl = $env:SHAREPOINT_SITE_URL,
    [switch]$DeviceLogin
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($SiteUrl)) { throw "-SiteUrl or SHAREPOINT_SITE_URL is required; no tenant default is embedded." }

Write-Host "=== CHHHS Publication Registry: SharePoint List Deployment ===" -ForegroundColor Cyan
Write-Host "Target Site: $SiteUrl"

Import-Module PnP.PowerShell -ErrorAction SilentlyContinue

if ($DeviceLogin) {
    Write-Host "Connecting using Device Login..." -ForegroundColor Yellow
    Connect-PnPOnline -Url $SiteUrl -DeviceLogin -ClientId '{{SHAREPOINT_CLIENT_ID}}'
} else {
    Write-Host "Connecting using Interactive Browser..." -ForegroundColor Yellow
    Connect-PnPOnline -Url $SiteUrl -Interactive -ClientId '{{SHAREPOINT_CLIENT_ID}}'
}

$ListName = "Publication Registry"
$ListDescription = "Official CHHHS Research Publication Register and Attribution Review Ledger."

# 1. Create List if not present and configure versioning
$list = Get-PnPList -Identity $ListName -ErrorAction SilentlyContinue
if (-not $list) {
    Write-Host "Creating list '$ListName'..." -ForegroundColor Green
    $list = New-PnPList -Title $ListName -Template GenericList -EnableVersioning
    Set-PnPList -Identity $ListName -Description $ListDescription -EnableVersioning $true -MajorVersions 500
} else {
    Write-Host "List '$ListName' already exists. Updating fields and ensuring versioning is enabled (500 versions)..." -ForegroundColor Yellow
    Set-PnPList -Identity $ListName -EnableVersioning $true -MajorVersions 500
}

# 2. Add Fields
function Add-RegistryField {
    param(
        [string]$DisplayName,
        [string]$InternalName,
        [string]$Type,
        [string[]]$Choices,
        [bool]$Required = $false,
        [bool]$Index = $false
    )

    $existing = Get-PnPField -List $ListName -Identity $InternalName -ErrorAction SilentlyContinue
    if (-not $existing) {
        Write-Host "  Adding field: $DisplayName ($InternalName) [$Type]" -ForegroundColor Gray
        switch ($Type) {
            "Text" {
                Add-PnPField -List $ListName -DisplayName $DisplayName -InternalName $InternalName -Type Text -AddToDefaultView
            }
            "Note" {
                Add-PnPField -List $ListName -DisplayName $DisplayName -InternalName $InternalName -Type Note -AddToDefaultView
            }
            "Number" {
                Add-PnPField -List $ListName -DisplayName $DisplayName -InternalName $InternalName -Type Number -AddToDefaultView
            }
            "DateTime" {
                Add-PnPField -List $ListName -DisplayName $DisplayName -InternalName $InternalName -Type DateTime -AddToDefaultView
            }
            "URL" {
                Add-PnPField -List $ListName -DisplayName $DisplayName -InternalName $InternalName -Type URL -AddToDefaultView
            }
            "Choice" {
                Add-PnPField -List $ListName -DisplayName $DisplayName -InternalName $InternalName -Type Choice -Choices $Choices -AddToDefaultView
            }
        }
    } else {
        Write-Host "  Field already exists: $InternalName" -ForegroundColor DarkGray
    }

    if ($Index) {
        Write-Host "    Ensuring column index on: $InternalName" -ForegroundColor Cyan
        Add-PnPIndexedColumn -List $ListName -Field $InternalName -ErrorAction SilentlyContinue
    }
}

Write-Host "Configuring schema fields..." -ForegroundColor Green

# Unique / Identifiers
Add-RegistryField -DisplayName "Source Key" -InternalName "SourceKey" -Type "Text" -Index $true
Add-RegistryField -DisplayName "Canonical Key" -InternalName "CanonicalKey" -Type "Text" -Index $true
Add-RegistryField -DisplayName "PMID" -InternalName "PMID" -Type "Text" -Index $true
Add-RegistryField -DisplayName "DOI" -InternalName "DOI" -Type "Text" -Index $true

# Bibliographic Information
Add-RegistryField -DisplayName "Authors" -InternalName "Authors" -Type "Note"
Add-RegistryField -DisplayName "Journal" -InternalName "Journal" -Type "Text"
Add-RegistryField -DisplayName "Publication Year" -InternalName "PublicationYear" -Type "Number" -Index $true
Add-RegistryField -DisplayName "Publication Month" -InternalName "PublicationMonth" -Type "Text" -Index $true
Add-RegistryField -DisplayName "Raw Date Parts" -InternalName "PublicationDateRaw" -Type "Text"
Add-RegistryField -DisplayName "Date Precision" -InternalName "PublicationDatePrecision" -Type "Choice" -Choices @("day", "month", "year", "range", "unknown", "rss_unverified")
Add-RegistryField -DisplayName "Source Set" -InternalName "SourceSet" -Type "Choice" -Choices @("PubMed", "DORA", "PubMed; DORA")
Add-RegistryField -DisplayName "PubMed Link" -InternalName "PubMedURL" -Type "URL"
Add-RegistryField -DisplayName "DORA Link" -InternalName "DORAURL" -Type "URL"

# Institutional Evidence
Add-RegistryField -DisplayName "Matched Facilities" -InternalName "MatchedFacilities" -Type "Note"
Add-RegistryField -DisplayName "CHHHS Authors" -InternalName "CHHHSAffiliatedAuthors" -Type "Note"
Add-RegistryField -DisplayName "Attribution Evidence" -InternalName "AttributionEvidence" -Type "Note"

# Curation & Observation State
Add-RegistryField -DisplayName "Review Status" -InternalName "ReviewStatus" -Type "Choice" -Choices @("Needs Review", "Included", "Excluded") -Index $true
Add-RegistryField -DisplayName "Review Notes" -InternalName "ReviewNotes" -Type "Note"
Add-RegistryField -DisplayName "First Observed" -InternalName "FirstObservedUTC" -Type "DateTime" -Index $true
Add-RegistryField -DisplayName "Last Observed" -InternalName "LastObservedUTC" -Type "DateTime"

# Extended Planned Enrichment Fields (Scopus, WoS, Dimensions, Crossref, OpenAlex, ARDC)
Add-RegistryField -DisplayName "Funder Names" -InternalName "FunderNames" -Type "Note"
Add-RegistryField -DisplayName "Grant / Award IDs" -InternalName "GrantIDs" -Type "Note"
Add-RegistryField -DisplayName "MeSH Headings" -InternalName "MeSHHeadings" -Type "Note"
Add-RegistryField -DisplayName "Author Keywords" -InternalName "AuthorKeywords" -Type "Note"
Add-RegistryField -DisplayName "Open Access Status" -InternalName "OpenAccessStatus" -Type "Choice" -Choices @("Gold", "Hybrid", "Green", "Bronze", "Closed", "Unknown")
Add-RegistryField -DisplayName "Open Access URL" -InternalName "OAUrl" -Type "URL"
Add-RegistryField -DisplayName "Raw Affiliations" -InternalName "AffiliationsRaw" -Type "Note"
Add-RegistryField -DisplayName "Institutional Hierarchy" -InternalName "AffiliationHierarchy" -Type "Note"
Add-RegistryField -DisplayName "Scopus Citations" -InternalName "CitationCount_Scopus" -Type "Number"
Add-RegistryField -DisplayName "Crossref Citations" -InternalName "CitationCount_Crossref" -Type "Number"
Add-RegistryField -DisplayName "OpenAlex Citations" -InternalName "CitationCount_OpenAlex" -Type "Number"
Add-RegistryField -DisplayName "Citation Metrics UTC" -InternalName "CitationMetricsObservedUTC" -Type "DateTime"

# Keyless Research Governance & Funding Enrichment Fields (Europe PMC, OpenAlex, Classifiers)
Add-RegistryField -DisplayName "PMCID" -InternalName "PMCID" -Type "Text" -Index $true
Add-RegistryField -DisplayName "Author ORCIDs" -InternalName "AuthorORCIDs" -Type "Note"
Add-RegistryField -DisplayName "Funding Type" -InternalName "FundingType" -Type "Choice" -Choices @("Commonwealth (NHMRC/MRFF)", "State / Qld Health", "Philanthropic / Foundation", "Commercial / Industry Trial", "University Partner", "Unfunded / Departmental", "Other External Funder") -Index $true
Add-RegistryField -DisplayName "Internal Funding" -InternalName "IsInternalFunding" -Type "Choice" -Choices @("Yes", "No")
Add-RegistryField -DisplayName "Clinical Trial ID" -InternalName "ClinicalTrialID" -Type "Text" -Index $true
Add-RegistryField -DisplayName "Indigenous Health Focus" -InternalName "IndigenousHealthFocus" -Type "Choice" -Choices @("Yes", "No") -Index $true
Add-RegistryField -DisplayName "Study Design" -InternalName "StudyDesign" -Type "Choice" -Choices @("Randomized Controlled Trial", "Systematic Review / Meta-Analysis", "Observational / Cohort Study", "Clinical Practice Guideline", "Case Report", "Other Biomedical / Translational") -Index $true
Add-RegistryField -DisplayName "Field of Research" -InternalName "FieldOfResearch" -Type "Text"
Add-RegistryField -DisplayName "Europe PMC Open Access" -InternalName "EuropePMC_OpenAccess" -Type "Text"
Add-RegistryField -DisplayName "Europe PMC Full Text URL" -InternalName "EuropePMC_FullTextURL" -Type "URL"
Add-RegistryField -DisplayName "Europe PMC Citations" -InternalName "EuropePMC_CitedByCount" -Type "Number"

# 3. Create Standard & Specialized Views
Write-Host "Configuring Views..." -ForegroundColor Green
$includedView = Get-PnPView -List $ListName -Identity "All Included Publications" -ErrorAction SilentlyContinue
if (-not $includedView) {
    Add-PnPView -List $ListName -Title "All Included Publications" `
        -Fields @("Title", "Authors", "Journal", "PublicationYear", "PublicationMonth", "MatchedFacilities", "ReviewStatus", "PMID", "DOI") `
        -Query "<Where><Eq><FieldRef Name='ReviewStatus'/><Value Type='Choice'>Included</Value></Eq></Where><OrderBy><FieldRef Name='PublicationYear' Ascending='FALSE'/><FieldRef Name='PublicationMonth' Ascending='FALSE'/></OrderBy>" `
        -SetAsDefault
}

$reviewView = Get-PnPView -List $ListName -Identity "Needs Review" -ErrorAction SilentlyContinue
if (-not $reviewView) {
    Add-PnPView -List $ListName -Title "Needs Review" `
        -Fields @("Title", "Authors", "Journal", "AttributionEvidence", "ReviewStatus", "FirstObservedUTC", "SourceSet") `
        -Query "<Where><Eq><FieldRef Name='ReviewStatus'/><Value Type='Choice'>Needs Review</Value></Eq></Where><OrderBy><FieldRef Name='FirstObservedUTC' Ascending='FALSE'/></OrderBy>"
}

$yearView = Get-PnPView -List $ListName -Identity "By Publication Year" -ErrorAction SilentlyContinue
if (-not $yearView) {
    Add-PnPView -List $ListName -Title "By Publication Year" `
        -Fields @("Title", "Authors", "Journal", "PublicationYear", "MatchedFacilities", "ReviewStatus", "DOI") `
        -Query "<GroupBy Collapse='TRUE'><FieldRef Name='PublicationYear'/></GroupBy><OrderBy><FieldRef Name='PublicationYear' Ascending='FALSE'/></OrderBy>"
}

$sourceView = Get-PnPView -List $ListName -Identity "By Primary Source" -ErrorAction SilentlyContinue
if (-not $sourceView) {
    Add-PnPView -List $ListName -Title "By Primary Source" `
        -Fields @("Title", "Authors", "Journal", "PublicationYear", "SourceSet", "PMID", "DOI", "ReviewStatus") `
        -Query "<GroupBy Collapse='TRUE'><FieldRef Name='SourceSet'/></GroupBy><OrderBy><FieldRef Name='PublicationYear' Ascending='FALSE'/></OrderBy>"
}

$facView = Get-PnPView -List $ListName -Identity "Matched Facilities" -ErrorAction SilentlyContinue
if (-not $facView) {
    Add-PnPView -List $ListName -Title "Matched Facilities" `
        -Fields @("Title", "Authors", "Journal", "PublicationYear", "MatchedFacilities", "AttributionEvidence", "ReviewStatus") `
        -Query "<Where><IsNotNull><FieldRef Name='MatchedFacilities'/></Where><OrderBy><FieldRef Name='PublicationYear' Ascending='FALSE'/></OrderBy>"
}

$pastMonthView = Get-PnPView -List $ListName -Identity "Past Month Publications" -ErrorAction SilentlyContinue
if (-not $pastMonthView) {
    Add-PnPView -List $ListName -Title "Past Month Publications" `
        -Fields @("Title", "Authors", "Journal", "PublicationYear", "PublicationMonth", "MatchedFacilities", "ReviewStatus", "CitationCount_OpenAlex", "OpenAccessStatus", "DOI") `
        -Query "<Where><Eq><FieldRef Name='ReviewStatus'/><Value Type='Choice'>Included</Value></Eq></Where><OrderBy><FieldRef Name='PublicationYear' Ascending='FALSE'/><FieldRef Name='PublicationMonth' Ascending='FALSE'/></OrderBy>"
}

Write-Host "Deployment completed successfully! List '$ListName' is ready with all 6 specialized views and versioning enabled." -ForegroundColor Green
