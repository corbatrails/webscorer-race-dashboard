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
