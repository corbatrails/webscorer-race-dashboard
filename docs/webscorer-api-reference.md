# WebScorer JSON API Reference

## Authentication

Every request requires two credentials as query parameters:
- `apiid=n` — JSON API ID (digits at end of your organizer page URL)
- `apipriv=p` — JSON API Token (8-character token, created on organizer page)

Found under: Organizers → My organizer settings → "Unique organizer URL" (for apiid) and "JSON API Token" section (for apipriv).

Requires active **PRO Results** subscription (separate from PRO timing).

## Endpoints

### List Posted Results
```
GET https://www.webscorer.com/json/mypostedraces?apiid=n&apipriv=p
```
Returns:
- `OrganizerInfo` — includes `OrganizerPage` (public URL)
- `ResultList` — array of result objects, each with:
  - `RaceId`, `Name`, `Date`, `Sport`, `DisplayURL`

### Race Results
```
GET https://www.webscorer.com/json/race?raceid=r&apiid=n&apipriv=p
```
Returns:
- `RaceInfo` — `RaceId`, `Name`, and other race metadata
- `Results` — array of grouping objects. Count depends on distances/categories/gender grouping.
  - Each object has `Grouping` and `Racers`
  - `Grouping` may include `Distance`, `Category`, `Gender`
  - `Overall: true` indicates grouping includes multiple categories
  - For lap races, `LapCount` is included
  - `Racers` — array of racer objects, each may include:
    - `Place`, `Bib`, `Name`, `Time`, `LapTimes`
    - Exact properties vary by race settings (mirrors webscorer results page)

### Taps Recorded
```
GET https://www.webscorer.com/json/fasttaps?raceid=r&apiid=n&apipriv=p
```
Returns raw chip/tap data for a race.

### Start Lists / Registration Lists
```
GET https://www.webscorer.com/json/mystartlists?apiid=n&apipriv=p
```
Returns:
- `OrganizerInfo`
- `StartLists` — array of objects, each with:
  - `RaceId`, `Name`, `Date`, `Sport`, `DisplayURL`, `Public` (bool), `Type` ("Start list" or "Registration")

Filter: append `&filt=S` for start lists only, `&filt=R` for registrations only.

### Start List / Registration Data
```
GET https://www.webscorer.com/json/startlist?raceid=r&apiid=n&apipriv=p
GET https://www.webscorer.com/json/registerlist?raceid=r&apiid=n&apipriv=p
```
Returns:
- `RaceInfo` — `RaceId`, `Name`, `Date`, `Sport`, `DisplayURL`, plus other properties
- `StartList` — array of racer objects, each may include:
  - `Bib`, `Name`, `Distance`, `Category`, etc.

### Series Results
```
GET https://www.webscorer.com/json/seriesresult?seriesid=r&apiid=n&apipriv=p
```
Returns:
- `SeriesInfo` — `SeriesId`, `Name`, `Date`, `Sport`, `DisplayURL`
- `Results` — grouped like race results, racers include `Place`, `Name`, `RacesCounted`, `TotalPoints`, `Races`

### GPS Tracking
```
GET https://www.webscorer.com/json/racerlocations?raceid=r&apiid=n&apipriv=p
```
Optional params: `&infoonly=1` (no location data), `&racer=Name` (specific racer)

## Error Handling
```json
{ "Error": "PRO Results subscription required to use this API has expired" }
```

## Encoding Notes
- `&` in URLs encoded as `\u0026`
- Single quotes encoded as `\u0027`
