import math


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
        categories.append({
            "name": name,
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
    pages = [{"type": "summary", "title": "Summary", "data": dashboard_data}]

    for category in dashboard_data.get("categories", []):
        racers = category["racers"]
        if len(racers) <= max_rows:
            pages.append({
                "type": "category",
                "title": category["name"],
                "racers": racers,
                "page_num": 1,
                "total_pages": 1,
            })
        else:
            total_pages = math.ceil(len(racers) / max_rows)
            for i in range(total_pages):
                start = i * max_rows
                end = start + max_rows
                pages.append({
                    "type": "category",
                    "title": category["name"],
                    "racers": racers[start:end],
                    "page_num": i + 1,
                    "total_pages": total_pages,
                })

    return pages
