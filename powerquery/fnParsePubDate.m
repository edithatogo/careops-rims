(raw as nullable text) as record =>
let
    TextValue = if raw = null then "" else Text.Trim(raw),
    Parts = List.Select(Text.SplitAny(TextValue, " /-"), each _ <> ""),
    YearToken = if List.Count(Parts) > 0 then Parts{0} else "",
    YearValue = if Text.Length(YearToken) = 4 then (try Number.FromText(YearToken, "en-US") otherwise null) else null,
    ValidYear = if YearValue = null then false else YearValue >= 1500 and YearValue <= 9999 and Number.RoundDown(YearValue) = YearValue,
    MonthToken = if List.Count(Parts) > 1 then Text.Lower(Parts{1}) else "",
    Months = [jan=1,feb=2,mar=3,apr=4,may=5,jun=6,jul=7,aug=8,sep=9,oct=10,nov=11,dec=12],
    MonthValue = if Record.HasFields(Months, MonthToken) then Record.Field(Months, MonthToken) else (try Number.FromText(MonthToken, "en-US") otherwise null),
    ValidMonth = if MonthValue = null then false else MonthValue >= 1 and MonthValue <= 12 and Number.RoundDown(MonthValue) = MonthValue,
    NumericParts = List.AllTrue(List.Transform(Parts, each Text.Length(_) > 0 and Text.Select(_, {"0".."9"}) = _)),
    IsRange = Text.Contains(TextValue, "-") and not NumericParts,
    DayValue = if List.Count(Parts) = 3 then (try Number.FromText(Parts{2}, "en-US") otherwise null) else 1,
    ValidDay = if DayValue = null then false else DayValue >= 1 and Number.RoundDown(DayValue) = DayValue,
    Candidate = if ValidYear and ValidMonth and ValidDay and not IsRange and List.Count(Parts) <= 3 then (try #date(YearValue, MonthValue, DayValue) otherwise null) else null,
    Precision = if not ValidYear then "unknown" else if List.Count(Parts) = 1 then "year" else if IsRange then "range" else if Candidate = null then "unknown" else if List.Count(Parts) = 3 then "day" else "month"
in
    [Date = Candidate, Precision = Precision, Year = if ValidYear then YearValue else null, Raw = TextValue]
