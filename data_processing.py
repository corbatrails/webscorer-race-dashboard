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


def _group_name(grouping, tier):
    if tier == "overall":
        return grouping.get("Distance") or "Overall"
    parts = [grouping.get("Category", "")]
    gender = grouping.get("Gender")
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


def process_race_data(api_response, show_overall_results=True, show_category_results=True):
    if "Error" in api_response:
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
            "error": api_response["Error"],
        }

    info = api_response.get("RaceInfo", {})
    results = api_response.get("Results", [])
    _add_category_places(results)

    total_racers = 0
    total_finished = 0
    total_dns = 0
    total_dnf = 0
    total_dsq = 0

    # Collect groups by distance, preserving API order
    distance_order = []
    distance_buckets = {}
    distance_stats_map = {}

    for group in results:
        grouping = group.get("Grouping", {})
        racers = sorted(group.get("Racers", []), key=_place_sort_key)

        if grouping.get("Overall"):
            dist_name = grouping.get("Distance") or "Overall"
            if dist_name not in distance_stats_map:
                distance_stats_map[dist_name] = {
                    "name": dist_name,
                    "total": 0,
                    "finished": 0,
                    "resolved": 0,
                }
            distance_stats_map[dist_name]["total"] += len(racers)
            total_racers += len(racers)
            for racer in racers:
                status = _classify_racer(racer)
                if status == "DNS":
                    total_dns += 1
                    distance_stats_map[dist_name]["resolved"] += 1
                elif status == "DNF":
                    total_dnf += 1
                    distance_stats_map[dist_name]["resolved"] += 1
                elif status == "DSQ":
                    total_dsq += 1
                    distance_stats_map[dist_name]["resolved"] += 1
                elif status == "FINISHED":
                    total_finished += 1
                    distance_stats_map[dist_name]["finished"] += 1
                    distance_stats_map[dist_name]["resolved"] += 1

        tier = _classify_group(grouping)
        if tier is None:
            continue
        if tier == "overall" and not show_overall_results:
            continue
        if tier == "category" and not show_category_results:
            continue

        distance = grouping.get("Distance", "")
        if distance not in distance_buckets:
            distance_order.append(distance)
            distance_buckets[distance] = {"overall": [], "category": []}

        name = _group_name(grouping, tier)
        distance_buckets[distance][tier].append({
            "name": name,
            "tier": tier,
            "racers": racers,
            "leaders": racers[:3],
        })

    categories = []
    for dist in distance_order:
        bucket = distance_buckets[dist]
        categories.extend(bucket["overall"])
        categories.extend(bucket["category"])

    distance_stats = list(distance_stats_map.values())

    return {
        "race_name": info.get("Name", ""),
        "race_date": info.get("Date", ""),
        "race_sport": info.get("Sport", ""),
        "total_racers": total_racers,
        "total_finished": total_finished,
        "total_dns": total_dns,
        "total_dnf": total_dnf,
        "total_dsq": total_dsq,
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
