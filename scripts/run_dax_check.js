async (page) => {
  const daxQuery = `// Read-only acceptance after canonical model deployment and refresh.
// Run without report filters. A passing count is not identity-review acceptance.
EVALUATE
VAR AllKeys = DISTINCT(Publication[CanonicalKey])
VAR BridgedKeys = DISTINCT(PublicationFacility[CanonicalKey])
RETURN ROW(
    "CanonicalRows", COUNTROWS(Publication),
    "CanonicalKeys", COUNTROWS(AllKeys),
    "Headline", [Publications],
    "HeadlineMatchesKeys", [Publications] = COALESCE(COUNTROWS(AllKeys), 0),
    "DuplicateCanonicalKeys", COUNTROWS(Publication) - COUNTROWS(AllKeys),
    "UnassignedFacilityKeys", COUNTROWS(EXCEPT(AllKeys, BridgedKeys)),
    "OrphanFacilityKeys", COUNTROWS(EXCEPT(BridgedKeys, AllKeys)),
    "SourceCountBalance", [Publications] = [PubMed Publications] + [DORA Publications] - [Cross-source Matches],
    "UnresolvedReviewRecords", [Reconciliation Needs Review],
    "UnallocatedMonthRecords", [Publications Without Usable Month]
)

EVALUATE
ADDCOLUMNS(
    VALUES(Facility[FacilityKey]),
    "Measured", CALCULATE([Publications]),
    "ExpectedFromBridge", VAR Keys = CALCULATETABLE(VALUES(PublicationFacility[CanonicalKey]))
        RETURN COALESCE(CALCULATE(DISTINCTCOUNT(Publication[CanonicalKey]), TREATAS(Keys, Publication[CanonicalKey])), 0),
    "Passed", VAR Keys = CALCULATETABLE(VALUES(PublicationFacility[CanonicalKey]))
        RETURN CALCULATE([Publications]) = COALESCE(CALCULATE(DISTINCTCOUNT(Publication[CanonicalKey]), TREATAS(Keys, Publication[CanonicalKey])), 0)
)

EVALUATE
ROW("EmptyContextCount", CALCULATE([Publications], FILTER(ALL(Publication), FALSE())),
    "EmptyContextPassed", CALCULATE([Publications], FILTER(ALL(Publication), FALSE())) = 0)`;

  await page.evaluate((query) => {
    const iframe = document.querySelector('[data-testid="iframe-page-modeling"]');
    const win = iframe.contentWindow;
    win.monaco.editor.getModels()[0].setValue(query);
  }, daxQuery);

  await page.waitForTimeout(1000);
  const frame = page.locator('[data-testid="iframe-page-modeling"]').contentFrame();
  await frame.getByRole('button', { name: 'Run' }).click();
}
