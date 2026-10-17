import re

_NON_FINISH_STATUSES = {"DNS", "DNF", "DSQ"}
_NO_TIME_VALUES = {"-", ""}


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


def _group_name(group, tier):
    if tier == "overall":
        return group.get("distance") or "Overall"
    parts = [group.get("category", "")]
    gender = group.get("gender")
    if gender:
        parts.append(gender)
    return " ".join(parts)


def _match_value(value):
    if value is None:
        return ""
    return str(value).strip()


def _result_match_key(distance, category, gender, bib):
    return (
        _match_value(distance),
        _match_value(category),
        _match_value(gender),
        _match_value(bib),
    )


def _place_sort_key(racer):
    place = _match_value(racer.get("Place"))
    if place.isdigit():
        return (0, int(place))
    return (1, 0)


def _add_category_places(results):
    category_places = {}

    for group in results:
        grouping = group.get("Grouping", {})
        if _classify_group(grouping) != "category":
            continue

        for racer in group.get("Racers", []):
            distance = grouping.get("Distance") or racer.get("Distance")
            category = grouping.get("Category") or racer.get("Category")
            gender = grouping.get("Gender") if grouping.get("Gender") is not None else racer.get("Gender")
            key = _result_match_key(distance, category, gender, racer.get("Bib"))
            category_places[key] = _match_value(racer.get("Place"))

    for group in results:
        grouping = group.get("Grouping", {})
        if _classify_group(grouping) != "overall":
            continue

        for racer in group.get("Racers", []):
            key = _result_match_key(
                racer.get("Distance"),
                racer.get("Category"),
                racer.get("Gender"),
                racer.get("Bib"),
            )
            if key in category_places:
                racer["CategoryPlace"] = category_places[key]


_NO_PLACE = "-"


def _rank_racers(racers):
    """Pair each racer with a derived place, in display order.

    Finishers come first, ordered by elapsed time (ties keep input order) and
    ranked with competition ranking (1, 2, 2, 4). Everyone else has no place
    (None) and follows in input order.
    """
    finishers = [r for r in racers if r["status"] == "FINISHED" and r["elapsed_seconds"] is not None]
    others = [r for r in racers if not (r["status"] == "FINISHED" and r["elapsed_seconds"] is not None)]
    finishers.sort(key=lambda r: r["elapsed_seconds"])

    ranked = []
    place = 0
    previous = None
    for index, racer in enumerate(finishers, start=1):
        if racer["elapsed_seconds"] != previous:
            place = index
            previous = racer["elapsed_seconds"]
        ranked.append((racer, place))
    return ranked + [(racer, None) for racer in others]


def _place_text(place):
    return str(place) if place is not None else _NO_PLACE


def _racer_row(racer, place, category_place=None):
    row = {
        "Place": _place_text(place),
        "Bib": racer["bib"],
        "Name": racer["name"],
        "Time": racer["time_display"],
        "TeamName": racer["team"],
        "Category": racer["category"],
        "Gender": racer["gender"],
    }
    if category_place is not None:
        row["CategoryPlace"] = category_place
    return row


def _membership_key(membership):
    return (membership["distance"], membership["category"], membership["gender"])


def _category_members(racers):
    """Group racers by category grouping, preserving snapshot order."""
    members = {}
    for racer in racers:
        for membership in racer["category_groups"]:
            members.setdefault(_membership_key(membership), []).append(racer)
    return members


def _category_place_of(racer, category_places):
    """Category place text for an overall row, or None if the racer has no category grouping."""
    memberships = racer["category_groups"]
    if not memberships:
        return None
    chosen = next(
        (m for m in memberships if m["category"] == racer["category"] and m["gender"] == racer["gender"]),
        memberships[0],
    )
    return _place_text(category_places[_membership_key(chosen)].get(id(racer)))


def process_race_data(snapshot, show_overall_results=True, show_category_results=True):
    if snapshot["error"]:
        return {
            "race_name": "",
            "race_date": "",
            "race_sport": "",
            "total_racers": 0,
            "total_finished": 0,
            "total_dns": 0,
            "total_dnf": 0,
            "total_dsq": 0,
            "categories": [],
            "distance_stats": [],
            "error": snapshot["error"],
        }

    race = snapshot["race"]
    racers = snapshot["racers"]
    overall_racers = [r for r in racers if r["in_overall"]]
    members = _category_members(racers)
    category_places = {
        key: {id(racer): place for racer, place in _rank_racers(group)}
        for key, group in members.items()
    }

    counts = {"FINISHED": 0, "DNS": 0, "DNF": 0, "DSQ": 0, "IN_PROGRESS": 0}
    distance_stats = []
    for group in snapshot["groups"]:
        if group["tier"] != "overall":
            continue
        in_group = [r for r in overall_racers if r["distance"] == group["distance"]]
        stat = {"name": group["distance"] or "Overall", "total": len(in_group), "finished": 0, "resolved": 0}
        for racer in in_group:
            counts[racer["status"]] += 1
            if racer["status"] == "FINISHED":
                stat["finished"] += 1
            if racer["status"] != "IN_PROGRESS":
                stat["resolved"] += 1
        distance_stats.append(stat)

    # Collect groups by distance, preserving API order
    distance_order = []
    distance_buckets = {}
    for group in snapshot["groups"]:
        tier = group["tier"]
        if tier == "overall" and not show_overall_results:
            continue
        if tier == "category" and not show_category_results:
            continue

        distance = group["distance"]
        if distance not in distance_buckets:
            distance_order.append(distance)
            distance_buckets[distance] = {"overall": [], "category": []}

        if tier == "overall":
            in_group = [r for r in overall_racers if r["distance"] == distance]
            rows = [
                _racer_row(racer, place, _category_place_of(racer, category_places))
                for racer, place in _rank_racers(in_group)
            ]
        else:
            key = (distance, group["category"], group["gender"])
            rows = [
                _racer_row(racer, place)
                for racer, place in _rank_racers(members.get(key, []))
            ]

        distance_buckets[distance][tier].append({
            "name": _group_name(group, tier),
            "tier": tier,
            "racers": rows,
            "leaders": rows[:3],
        })

    categories = []
    for dist in distance_order:
        bucket = distance_buckets[dist]
        categories.extend(bucket["overall"])
        categories.extend(bucket["category"])

    return {
        "race_name": race["name"],
        "race_date": race["date"],
        "race_sport": race["sport"],
        "total_racers": len(overall_racers),
        "total_finished": counts["FINISHED"],
        "total_dns": counts["DNS"],
        "total_dnf": counts["DNF"],
        "total_dsq": counts["DSQ"],
        "categories": categories,
        "distance_stats": distance_stats,
        "error": None,
    }


def _parse_time_seconds(time_str):
    parts = time_str.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return float(parts[0])


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


def build_finish_chart_data(api_response, bucket_minutes=15):
    if "Error" in api_response:
        return None

    results = api_response.get("Results", [])
    race_info = api_response.get("RaceInfo", {})

    start_time_str = race_info.get("StartTime", "")
    race_start_seconds = _extract_race_start_seconds(start_time_str)
    floor_hour = (race_start_seconds // 3600) * 3600

    distance_order = []
    finishers_by_distance = {}

    for group in results:
        grouping = group.get("Grouping", {})
        if not grouping.get("Overall"):
            continue
        distance = grouping.get("Distance", "")
        if distance not in finishers_by_distance:
            distance_order.append(distance)
            finishers_by_distance[distance] = []

        for racer in group.get("Racers", []):
            if _classify_racer(racer) != "FINISHED":
                continue
            start_str = racer.get("StartTime")
            if not start_str:
                continue
            start_secs = _parse_time_seconds(start_str)
            elapsed_secs = _parse_time_seconds(racer["Time"])
            finish_secs = start_secs + elapsed_secs
            finishers_by_distance[distance].append(finish_secs)

    all_finishes = [s for fins in finishers_by_distance.values() for s in fins]
    if not all_finishes:
        return None

    bucket_secs = bucket_minutes * 60
    last_finish = max(all_finishes)
    labels = []
    bucket_starts = []
    t = floor_hour
    while t <= last_finish:
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        labels.append(f"{h}:{m:02d}")
        bucket_starts.append(t)
        t += bucket_secs

    datasets = []
    for distance in distance_order:
        counts = [0] * len(bucket_starts)
        for finish_secs in finishers_by_distance[distance]:
            idx = int((finish_secs - floor_hour) // bucket_secs)
            if 0 <= idx < len(counts):
                counts[idx] += 1
        datasets.append({"label": distance, "data": counts})

    return {"labels": labels, "datasets": datasets}


_AGE_BUCKETS = [
    (0, 19, "<20"),
    (20, 29, "20-29"),
    (30, 39, "30-39"),
    (40, 49, "40-49"),
    (50, 59, "50-59"),
    (60, 69, "60-69"),
    (70, 999, "70+"),
]


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


def _build_age_stats(ages):
    labels = [label for _, _, label in _AGE_BUCKETS]
    if not ages:
        return {
            "average": None,
            "median": None,
            "min": None,
            "max": None,
            "labels": labels,
            "counts": [0] * len(labels),
        }

    counts = [0] * len(_AGE_BUCKETS)
    for age in ages:
        for i, (low, high, _) in enumerate(_AGE_BUCKETS):
            if low <= age <= high:
                counts[i] += 1
                break

    sorted_ages = sorted(ages)
    n = len(sorted_ages)
    if n % 2 == 1:
        median = sorted_ages[n // 2]
    else:
        median = (sorted_ages[n // 2 - 1] + sorted_ages[n // 2]) / 2

    return {
        "average": round(sum(ages) / len(ages), 1),
        "median": median,
        "min": min(ages),
        "max": max(ages),
        "labels": labels,
        "counts": counts,
    }


def _build_gender_stats(gender_counts):
    ordered = sorted(gender_counts.items(), key=lambda item: (-item[1], item[0]))
    return {
        "labels": [label for label, _ in ordered],
        "counts": [count for _, count in ordered],
    }


def _build_team_stats(solo_count, team_counts):
    ordered = sorted(team_counts.items(), key=lambda item: (-item[1], item[0]))
    top_teams = [{"name": name, "count": count} for name, count in ordered[:5]]
    return {
        "solo_count": solo_count,
        "team_count": sum(team_counts.values()),
        "top_teams": top_teams,
    }


def build_demographics_data(api_response):
    if "Error" in api_response:
        return None

    results = api_response.get("Results", [])

    total_registrants = 0
    ages = []
    gender_counts = {}
    distance_order = []
    distance_counts = {}
    solo_count = 0
    team_counts = {}

    for group in results:
        grouping = group.get("Grouping", {})
        if not grouping.get("Overall"):
            continue

        distance = grouping.get("Distance") or "Overall"
        if distance not in distance_counts:
            distance_order.append(distance)
            distance_counts[distance] = 0

        for racer in group.get("Racers", []):
            total_registrants += 1
            distance_counts[distance] += 1

            age = _as_age_int(racer.get("Age"))
            if age is not None:
                ages.append(age)

            gender = (racer.get("Gender") or "").strip() or "Unknown"
            gender_counts[gender] = gender_counts.get(gender, 0) + 1

            team = (racer.get("TeamName") or "").strip()
            if team:
                team_counts[team] = team_counts.get(team, 0) + 1
            else:
                solo_count += 1

    if total_registrants == 0:
        return None

    return {
        "total_registrants": total_registrants,
        "age": _build_age_stats(ages),
        "gender": _build_gender_stats(gender_counts),
        "distance": {
            "labels": distance_order,
            "counts": [distance_counts[d] for d in distance_order],
        },
        "teams": _build_team_stats(solo_count, team_counts),
    }


def build_pages(dashboard_data, demographics=None, max_rows=18):
    """Build page list. Categories are sent whole; the frontend splits by viewport size."""
    pages = [{"type": "summary", "title": "Summary", "data": dashboard_data}]

    if demographics:
        pages.append({"type": "demographics", "title": "Demographics", "data": demographics})

    for category in dashboard_data.get("categories", []):
        title = category["name"]
        if category["tier"] == "overall" and title != "Overall":
            title = f"Overall - {title}"
        pages.append({
            "type": "category",
            "title": title,
            "tier": category["tier"],
            "racers": category["racers"],
        })

    return pages
