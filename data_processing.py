def process_race_data(api_response):
    if "Error" in api_response:
        return {
            "race_name": "",
            "race_date": "",
            "race_sport": "",
            "total_finished": 0,
            "categories": [],
            "error": api_response["Error"],
        }

    info = api_response.get("RaceInfo", {})
    results = api_response.get("Results", [])

    categories = []
    total_finished = 0

    for group in results:
        grouping = group.get("Grouping", {})
        racers = group.get("Racers", [])
        name = grouping.get("Category") or grouping.get("Distance") or grouping.get("Gender") or "Overall"

        total_finished += len(racers)
        gender = racers[0].get("Gender", "") if racers else ""
        categories.append({
            "name": name,
            "gender": gender,
            "racers": racers,
            "leaders": racers[:3],
        })

    return {
        "race_name": info.get("Name", ""),
        "race_date": info.get("Date", ""),
        "race_sport": info.get("Sport", ""),
        "total_finished": total_finished,
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
            "gender": category.get("gender", ""),
            "racers": category["racers"],
        })

    return pages
