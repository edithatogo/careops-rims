# Measures

## Publications

```dax
VAR MatchedKeys = VALUES(PublicationFacility[CanonicalKey])
VAR FacilityFiltered = ISFILTERED(Facility) || ISFILTERED(PublicationFacility)
RETURN COALESCE(IF(FacilityFiltered, CALCULATE(DISTINCTCOUNT(Publication[CanonicalKey]), KEEPFILTERS(TREATAS(MatchedKeys, Publication[CanonicalKey]))), DISTINCTCOUNT(Publication[CanonicalKey])), 0)
```

## PubMed Publications

```dax
CALCULATE([Publications], KEEPFILTERS(CONTAINSSTRING(Publication[SourceSet], "PubMed")))
```

## DORA Publications

```dax
CALCULATE([Publications], KEEPFILTERS(CONTAINSSTRING(Publication[SourceSet], "DORA")))
```

## Cross-source Matches

```dax
CALCULATE([Publications], KEEPFILTERS(Publication[SourceSet] = "PubMed; DORA"))
```

## DORA-only Publications

```dax
CALCULATE([Publications], KEEPFILTERS(Publication[SourceSet] = "DORA"))
```

## Reconciliation Needs Review

```dax
CALCULATE([Publications], KEEPFILTERS(CONTAINSSTRING(Publication[AttributionStatus], "needs review")))
```

## Open Access Publications

```dax
CALCULATE([Publications], KEEPFILTERS(Publication[EuropePMC_OpenAccess] = "Y" || Publication[OpenAccessStatus] IN {"Gold", "Green"} || NOT(ISBLANK(Publication[PMCID]))))
```

## Open Access Rate

```dax
DIVIDE([Open Access Publications], [Publications])
```

## Funded Publications

```dax
CALCULATE([Publications], KEEPFILTERS(Publication[FundingType] <> "Unfunded / Departmental" && Publication[FundingType] <> "" && NOT(ISBLANK(Publication[FundingType]))))
```

## Internal CHHHS Funded Publications

```dax
CALCULATE([Publications], KEEPFILTERS(Publication[IsInternalFunding] = "Yes"))
```

## First Nations Health Publications

```dax
CALCULATE([Publications], KEEPFILTERS(Publication[IndigenousHealthFocus] = "Yes"))
```

## Clinical Trials Count

```dax
CALCULATE([Publications], KEEPFILTERS(Publication[ClinicalTrialID] <> "" && NOT(ISBLANK(Publication[ClinicalTrialID]))))
```

## Archived Full-Text Papers

```dax
CALCULATE([Publications], KEEPFILTERS(Publication[PDFDownloadStatus] IN {"Downloaded", "Already Exists"}))
```

## Publications Last Complete Month

```dax
VAR StartDate = MAX(ReportingWindow[ReportMonthStart])
VAR EndDate = MAX(ReportingWindow[ReportMonthEndExclusive])
RETURN CALCULATE([Publications], REMOVEFILTERS('Date'), DATESBETWEEN('Date'[Date],StartDate,EndDate-1), KEEPFILTERS(Publication[PublicationDatePrecision] IN {"day", "month"}))
```

## Publications Previous Year Month

```dax
VAR StartDate = EDATE(MAX(ReportingWindow[ReportMonthStart]),-12)
VAR EndDate = EDATE(MAX(ReportingWindow[ReportMonthEndExclusive]),-12)
RETURN CALCULATE([Publications], REMOVEFILTERS('Date'), DATESBETWEEN('Date'[Date],StartDate,EndDate-1), KEEPFILTERS(Publication[PublicationDatePrecision] IN {"day", "month"}))
```

## Monthly Year-on-Year Change

```dax
DIVIDE([Publications Last Complete Month]-[Publications Previous Year Month], [Publications Previous Year Month])
```

## Publications Last 24 Complete Months

```dax
VAR StartDate = EDATE(MAX(ReportingWindow[ReportMonthEndExclusive]),-24)
VAR EndDate = MAX(ReportingWindow[ReportMonthEndExclusive])
RETURN CALCULATE([Publications], KEEPFILTERS(DATESBETWEEN('Date'[Date],StartDate,EndDate-1)))
```

## Publications Without Usable Month

```dax
CALCULATE([Publications], REMOVEFILTERS('Date'), KEEPFILTERS(NOT(Publication[PublicationDatePrecision] IN {"day", "month"})))
```

## Reporting Month

```dax
IF(ISFILTERED('Date'[YearMonth]), IF(HASONEVALUE('Date'[YearMonth]), SELECTEDVALUE('Date'[YearMonth]), "Select one month"), FORMAT(MAX(ReportingWindow[ReportMonthStart]), "MMMM yyyy"))
```

## Refresh Timestamp UTC

```dax
MAX(ReportingWindow[RefreshedAtUTC])
```

## Query Warnings

```dax
COUNTROWS(FILTER(SearchAudit, SearchAudit[Warnings] <> ""))
```

## Configured Facility Searches

```dax
COUNTROWS(Facility)
```

## Register Row Count

```dax
VAR N = [Publications] RETURN IF(N > 0, N, BLANK())
```

## Selected Month Publications

```dax
VAR HasSelection = ISFILTERED('Date'[YearMonth])
VAR ValidSelection = NOT(HasSelection) || HASONEVALUE('Date'[YearMonth])
VAR StartDate = IF(HasSelection, DATE(YEAR(MIN('Date'[Date])), MONTH(MIN('Date'[Date])), 1), MAX(ReportingWindow[ReportMonthStart]))
VAR EndDate = EDATE(StartDate, 1)
RETURN IF(ValidSelection, CALCULATE([Publications], REMOVEFILTERS('Date'), DATESBETWEEN('Date'[Date], StartDate, EndDate-1), KEEPFILTERS(Publication[PublicationDatePrecision] IN {"day", "month"})), BLANK())
```

## Monthly Register Row Count

```dax
VAR N = [Selected Month Publications] RETURN IF(N > 0, N, BLANK())
```
