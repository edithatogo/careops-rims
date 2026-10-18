let
    // Synthetic parser inputs only; never save this test query in the release model.
    Cases = #table(type table [Raw=nullable text, ExpectedPrecision=text, ExpectedDate=nullable date, ExpectedYear=nullable number], {
        {null,"unknown",null,null},
        {"","unknown",null,null},
        {"2024","year",null,2024},
        {"2024 Feb","month",#date(2024,2,1),2024},
        {"2024 Feb 29","day",#date(2024,2,29),2024},
        {"2023 Feb 29","unknown",null,2023},
        {"2024-02-29","day",#date(2024,2,29),2024},
        {"2024 Jan-Feb","range",null,2024},
        {"2024 13","unknown",null,2024},
        {"not a date","unknown",null,null}
    }),
    Parsed = Table.AddColumn(Cases,"Actual",each fnParsePubDate([Raw]),type record),
    Expanded = Table.ExpandRecordColumn(Parsed,"Actual",{"Precision","Date","Year"},{"ActualPrecision","ActualDate","ActualYear"}),
    Checked = Table.AddColumn(Expanded,"Passed",each [ExpectedPrecision]=[ActualPrecision] and [ExpectedDate]=[ActualDate] and [ExpectedYear]=[ActualYear],type logical)
in Checked
