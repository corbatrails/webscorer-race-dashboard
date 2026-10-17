"""Normalize a WebScorer race payload into a flat, provider-neutral RaceSnapshot.

This is the only module that reads the raw `Results` structure. Views in
`data_processing` are projections over `snapshot["racers"]`; see
`docs/superpowers/specs/2026-10-17-racer-snapshot-design.md` for the rationale.

Schema
------
RaceSnapshot
    error    str | None      API `Error` message; when set, `racers`/`groups` are empty.
    race     RaceMeta        name, date, sport, start_seconds (race start time of day).
    groups   list[GroupInfo] Overall/category groupings in API order, de-duplicated.
                             Drives page order and keeps empty groups visible.
    racers   list[Racer]     One entry per overall listing, plus category-only racers.

Racer
    bib, name, team          Strings. `name` falls back to `TeamName` when `Name` is
                             empty (and `team` is then ""), see #34.
    distance, category,      Distance of the grouping the racer was listed under;
    gender                   the racer's own Category and Gender ("" if missing).
    age                      int | None
    status                   FINISHED | IN_PROGRESS | DNS | DNF | DSQ
    time_display             The API `Time` string as reported.
    elapsed_seconds          float | None, FINISHED racers with a parseable time only.
    start_seconds            float | None, racer start as seconds since midnight of the
                             race-start day (next-day wave starts get +86400).
    finish_tod_seconds       start_seconds + elapsed_seconds, NOT wrapped at midnight.
    source_place             Overall `Place` string as sent by the API (reconciliation
                             only; views derive place themselves).
    in_overall               Listed in an Overall grouping (feeds totals/chart/demographics).
    category_groups          list[CategoryMembership], one per Category grouping listed in.

CategoryMembership: distance, category, gender (grouping values), source_place.
"""
import re
from typing import List, Optional, TypedDict

_NON_FINISH_STATUSES = {"DNS", "DNF", "DSQ"}
_NO_TIME_VALUES = {"-", ""}
_DAY_SECONDS = 86400
# A racer start more than this far before the race start is on the next day.
_NEXT_DAY_THRESHOLD_SECONDS = 12 * 3600


class RaceMeta(TypedDict):
    name: str
    date: str
    sport: str
    start_seconds: float


class GroupInfo(TypedDict):
    tier: str
    distance: str
    category: str
    gender: str


class CategoryMembership(TypedDict):
    distance: str
    category: str
    gender: str
    source_place: str


class Racer(TypedDict):
    bib: str
    name: str
    team: str
    distance: str
    category: str
    gender: str
    age: Optional[int]
    status: str
    time_display: str
    elapsed_seconds: Optional[float]
    start_seconds: Optional[float]
    finish_tod_seconds: Optional[float]
    source_place: str
    in_overall: bool
    category_groups: List[CategoryMembership]


class RaceSnapshot(TypedDict):
    error: Optional[str]
    race: RaceMeta
    groups: List[GroupInfo]
    racers: List[Racer]


def _classify_racer(racer):
    time_val = (racer.get("Time") or "").strip().upper()
    if time_val in _NON_FINISH_STATUSES:
        return time_val
    if time_val in _NO_TIME_VALUES:
        return "IN_PROGRESS"
    return "FINISHED"


def _classify_group(grouping):
    if grouping.get("Overall"):
        return "overall"
    if grouping.get("Category"):
        return "category"
    return None


def _match_value(value):
    if value is None:
        return ""
    return str(value).strip()


def _parse_time_seconds(time_str):
    parts = time_str.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return float(parts[0])


def _safe_seconds(time_str):
    try:
        return round(_parse_time_seconds(time_str), 3)
    except (ValueError, TypeError):
        return None


def _extract_race_start_seconds(start_time_str):
    """Extract seconds-since-midnight from RaceInfo StartTime string.
    Format: 'Thursday, August 13, 2026 2:08 PM (GMT-5)'
    """
    match = re.search(r'(\d{1,2}):(\d{2})\s*(AM|PM)', start_time_str, re.IGNORECASE)
    if not match:
        return 0
    hour = int(match.group(1))
    minute = int(match.group(2))
    ampm = match.group(3).upper()
    if ampm == "PM" and hour != 12:
        hour += 12
    elif ampm == "AM" and hour == 12:
        hour = 0
    return hour * 3600 + minute * 60


def _as_age_int(age):
    if isinstance(age, bool):
        return None
    if isinstance(age, int):
        return age
    if isinstance(age, float):
        return int(age)
    if isinstance(age, str) and age.strip().isdigit():
        return int(age.strip())
    return None


def _build_racer(raw, distance, race_start_seconds, in_overall):
    name = _match_value(raw.get("Name"))
    team = _match_value(raw.get("TeamName"))
    if not name and team:
        name, team = team, ""

    status = _classify_racer(raw)
    time_display = _match_value(raw.get("Time"))
    elapsed = _safe_seconds(time_display) if status == "FINISHED" else None

    start = None
    if raw.get("StartTime"):
        start = _safe_seconds(str(raw["StartTime"]))
        if start is not None and start < race_start_seconds - _NEXT_DAY_THRESHOLD_SECONDS:
            start += _DAY_SECONDS

    finish = None
    if start is not None and elapsed is not None:
        finish = round(start + elapsed, 3)

    return {
        "bib": _match_value(raw.get("Bib")),
        "name": name,
        "team": team,
        "distance": distance,
        "category": _match_value(raw.get("Category")),
        "gender": _match_value(raw.get("Gender")),
        "age": _as_age_int(raw.get("Age")),
        "status": status,
        "time_display": time_display,
        "elapsed_seconds": elapsed,
        "start_seconds": start,
        "finish_tod_seconds": finish,
        "source_place": _match_value(raw.get("Place")) if in_overall else "",
        "in_overall": in_overall,
        "category_groups": [],
    }


def _identity(distance, racer):
    if racer["bib"]:
        return (distance, "bib", racer["bib"])
    if racer["name"]:
        return (distance, "name", racer["name"])
    return None


def normalize_webscorer(api_response):
    """Turn a raw WebScorer race response into a RaceSnapshot."""
    if "Error" in api_response:
        return {
            "error": api_response["Error"],
            "race": {"name": "", "date": "", "sport": "", "start_seconds": 0},
            "groups": [],
            "racers": [],
        }

    info = api_response.get("RaceInfo", {})
    race_start = _extract_race_start_seconds(info.get("StartTime", "") or "")
    results = api_response.get("Results", [])

    groups = []
    seen_groups = set()
    racers = []
    by_identity = {}

    for group in results:
        grouping = group.get("Grouping", {})
        tier = _classify_group(grouping)
        if tier is None:
            continue
        descriptor = {
            "tier": tier,
            "distance": grouping.get("Distance") or "",
            "category": (grouping.get("Category") or "") if tier == "category" else "",
            "gender": (grouping.get("Gender") or "") if tier == "category" else "",
        }
        key = tuple(descriptor.values())
        if key not in seen_groups:
            seen_groups.add(key)
            groups.append(descriptor)

        if tier != "overall":
            continue
        for raw in group.get("Racers", []):
            racer = _build_racer(raw, descriptor["distance"], race_start, in_overall=True)
            racers.append(racer)
            identity = _identity(racer["distance"], racer)
            if identity is not None:
                by_identity.setdefault(identity, racer)

    for group in results:
        grouping = group.get("Grouping", {})
        if _classify_group(grouping) != "category":
            continue
        group_distance = grouping.get("Distance") or ""
        for raw in group.get("Racers", []):
            lookup_distance = group_distance or _match_value(raw.get("Distance"))
            membership = {
                "distance": group_distance,
                "category": grouping.get("Category") or "",
                "gender": grouping.get("Gender") or "",
                "source_place": _match_value(raw.get("Place")),
            }
            candidate = _build_racer(raw, lookup_distance, race_start, in_overall=False)
            identity = _identity(lookup_distance, candidate)
            racer = by_identity.get(identity) if identity is not None else None
            if racer is None:
                racer = candidate
                racers.append(racer)
                if identity is not None:
                    by_identity[identity] = racer
            racer["category_groups"].append(membership)

    return {
        "error": None,
        "race": {
            "name": info.get("Name", ""),
            "date": info.get("Date", ""),
            "sport": info.get("Sport", ""),
            "start_seconds": race_start,
        },
        "groups": groups,
        "racers": racers,
    }
