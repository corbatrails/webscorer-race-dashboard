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
            "error": api_response["Error"],
        }

    info = api_response.get("RaceInfo", {})
    results = api_response.get("Results", [])

    total_racers = 0
    total_finished = 0
    total_dns = 0
    total_dnf = 0
    total_dsq = 0

    # Collect groups by distance, preserving API order
    distance_order = []
    distance_buckets = {}

    for group in results:
        grouping = group.get("Grouping", {})
        racers = group.get("Racers", [])

        if grouping.get("Overall"):
            total_racers += len(racers)
            for racer in racers:
                status = _classify_racer(racer)
                if status == "DNS":
                    total_dns += 1
                elif status == "DNF":
                    total_dnf += 1
                elif status == "DSQ":
                    total_dsq += 1
                elif status == "FINISHED":
                    total_finished += 1

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
            "racers": racers,
            "leaders": racers[:3],
        })

    categories = []
    for dist in distance_order:
        bucket = distance_buckets[dist]
        categories.extend(bucket["overall"])
        categories.extend(bucket["category"])

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


def build_pages(dashboard_data, max_rows=18):
    """Build page list. Categories are sent whole; the frontend splits by viewport size."""
    pages = [{"type": "summary", "title": "Summary", "data": dashboard_data}]

    for category in dashboard_data.get("categories", []):
        pages.append({
            "type": "category",
            "title": category["name"],
            "racers": category["racers"],
        })

    return pages
