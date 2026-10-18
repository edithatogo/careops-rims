// Deployment parameters are configured privately against the approved organisation
// OneDrive/SharePoint site and exact source-archive folder, ending in '/'.
let
    Files=SharePoint.Files(pRetainedSiteUrl,[ApiVersion=15]),
    Scoped=Table.SelectRows(Files,each [Folder Path]=pRetainedArchiveFolderUrl and [Extension]=".json"),
    History=fnReadCommittedHistory(Table.SelectColumns(Scoped,{"Name","Content"}))
in History
