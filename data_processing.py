_NON_FINISH_STATUSES = {"DNS", "DNF", "DSQ"}
_NO_TIME_VALUES = {"-", ""}


def _classify_racer(racer):
    time_val = (racer.get("Time") or "").strip().upper()
    if time_val in _NON_FINISH_STATUSES:
        return time_val
    if time_val in _NO_TIME_VALUES:
        return "IN_PROGRESS"
    return "FINISHED"


def process_race_data(api_response):
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

    categories = []
    total_racers = 0
    total_finished = 0
    total_dns = 0
    total_dnf = 0
    total_dsq = 0

    for group in results:
        grouping = group.get("Grouping", {})
        racers = group.get("Racers", [])
        name = grouping.get("Category") or grouping.get("Distance") or grouping.get("Gender") or "Overall"

        # Count totals only from Overall groups (one per distance)
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

        categories.append({
            "name": name,
            "racers": racers,
            "leaders": racers[:3],
        })

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
