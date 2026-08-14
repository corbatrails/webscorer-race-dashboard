from data_processing import process_race_data, build_pages


MOCK_API_RESPONSE = {
    "RaceInfo": {"RaceId": 100, "Name": "Morning 5K", "Date": "2026-08-07", "Sport": "Running"},
    "Results": [
        {
            "Grouping": {"Category": "Overall", "Overall": True},
            "Racers": [
                {"Place": 1, "Bib": "101", "Name": "Alice", "Time": "00:18:30"},
                {"Place": 2, "Bib": "102", "Name": "Bob", "Time": "00:19:15"},
                {"Place": 3, "Bib": "201", "Name": "Eve", "Time": "00:19:00"},
                {"Place": 4, "Bib": "103", "Name": "Charlie", "Time": "00:20:00"},
                {"Place": 5, "Bib": "104", "Name": "Dave", "Time": "00:21:45"},
                {"Place": 6, "Bib": "202", "Name": "Fran", "Time": "00:22:10"},
                {"Place": "", "Bib": "105", "Name": "Ed", "Time": "DNF"},
                {"Place": "", "Bib": "203", "Name": "Grace", "Time": "DNS"},
                {"Place": "", "Bib": "204", "Name": "Heidi", "Time": "DSQ"},
            ],
        },
        {
            "Grouping": {"Category": "Male 20-29"},
            "Racers": [
                {"Place": 1, "Bib": "101", "Name": "Alice", "Time": "00:18:30"},
                {"Place": 2, "Bib": "102", "Name": "Bob", "Time": "00:19:15"},
                {"Place": 3, "Bib": "103", "Name": "Charlie", "Time": "00:20:00"},
                {"Place": 4, "Bib": "104", "Name": "Dave", "Time": "00:21:45"},
                {"Place": "", "Bib": "105", "Name": "Ed", "Time": "DNF"},
            ],
        },
        {
            "Grouping": {"Category": "Female 20-29"},
            "Racers": [
                {"Place": 1, "Bib": "201", "Name": "Eve", "Time": "00:19:00"},
                {"Place": 2, "Bib": "202", "Name": "Fran", "Time": "00:22:10"},
                {"Place": "", "Bib": "203", "Name": "Grace", "Time": "DNS"},
                {"Place": "", "Bib": "204", "Name": "Heidi", "Time": "DSQ"},
            ],
        },
    ],
}


def test_process_race_data_basic():
    result = process_race_data(MOCK_API_RESPONSE)
    assert result["race_name"] == "Morning 5K"
    assert result["race_date"] == "2026-08-07"
    assert result["race_sport"] == "Running"
    assert result["total_racers"] == 9
    assert result["total_finished"] == 6
    assert result["total_dns"] == 1
    assert result["total_dnf"] == 1
    assert result["total_dsq"] == 1
    assert len(result["categories"]) == 3


def test_process_race_data_categories():
    result = process_race_data(MOCK_API_RESPONSE)
    cat0 = result["categories"][0]
    assert cat0["name"] == "Overall"
    assert len(cat0["racers"]) == 9

    cat1 = result["categories"][1]
    assert cat1["name"] == "Male 20-29"
    assert len(cat1["racers"]) == 5
    assert len(cat1["leaders"]) == 3
    assert cat1["leaders"][0]["Name"] == "Alice"

    cat2 = result["categories"][2]
    assert cat2["name"] == "Female 20-29"
    assert len(cat2["racers"]) == 4
    assert len(cat2["leaders"]) == 3


def test_process_race_data_empty_results():
    response = {
        "RaceInfo": {"RaceId": 100, "Name": "Morning 5K", "Date": "2026-08-07", "Sport": "Running"},
        "Results": [],
    }
    result = process_race_data(response)
    assert result["total_racers"] == 0
    assert result["total_finished"] == 0
    assert result["total_dns"] == 0
    assert result["total_dnf"] == 0
    assert result["total_dsq"] == 0
    assert result["categories"] == []


def test_process_race_data_api_error():
    response = {"Error": "PRO Results subscription required"}
    result = process_race_data(response)
    assert result["error"] == "PRO Results subscription required"


def test_build_pages_basic():
    data = process_race_data(MOCK_API_RESPONSE)
    pages = build_pages(data)
    assert pages[0]["type"] == "summary"
    assert pages[1]["type"] == "category"
    assert pages[1]["title"] == "Overall"
    assert len(pages[1]["racers"]) == 9
    assert pages[2]["type"] == "category"
    assert pages[2]["title"] == "Male 20-29"
    assert pages[3]["type"] == "category"
    assert pages[3]["title"] == "Female 20-29"
    assert len(pages) == 4


def test_build_pages_large_category_unsplit():
    many_racers = [{"Place": i, "Bib": str(i), "Name": f"Racer {i}", "Time": "00:20:00"} for i in range(1, 26)]
    response = {
        "RaceInfo": {"RaceId": 100, "Name": "Big Race", "Date": "2026-08-07", "Sport": "Running"},
        "Results": [{"Grouping": {"Category": "Open", "Overall": True}, "Racers": many_racers}],
    }
    data = process_race_data(response)
    pages = build_pages(data)
    # Summary + 1 category (frontend handles splitting)
    assert len(pages) == 2
    assert pages[1]["type"] == "category"
    assert len(pages[1]["racers"]) == 25


def test_build_pages_empty():
    data = process_race_data({"RaceInfo": {"Name": "Empty", "Date": "", "Sport": ""}, "Results": []})
    pages = build_pages(data)
    assert len(pages) == 1
    assert pages[0]["type"] == "summary"


def test_process_race_data_counts_only_overall_groups():
    """Totals come from Overall groups only, not summed across all groups."""
    result = process_race_data(MOCK_API_RESPONSE)
    assert result["total_racers"] == 9
    assert result["total_finished"] == 6
    assert len(result["categories"]) == 3


def test_process_race_data_multi_distance():
    response = {
        "RaceInfo": {"RaceId": 200, "Name": "Trail Race", "Date": "2026-08-13", "Sport": "Cycling"},
        "Results": [
            {
                "Grouping": {"Distance": "Long", "Overall": True},
                "Racers": [
                    {"Place": 1, "Bib": "1", "Name": "A", "Time": "01:00:00"},
                    {"Place": "", "Bib": "2", "Name": "B", "Time": "DNS"},
                ],
            },
            {
                "Grouping": {"Distance": "Long", "Gender": "Male"},
                "Racers": [
                    {"Place": 1, "Bib": "1", "Name": "A", "Time": "01:00:00"},
                ],
            },
            {
                "Grouping": {"Distance": "Short", "Overall": True},
                "Racers": [
                    {"Place": 1, "Bib": "3", "Name": "C", "Time": "00:30:00"},
                    {"Place": 2, "Bib": "4", "Name": "D", "Time": "00:35:00"},
                    {"Place": "", "Bib": "5", "Name": "E", "Time": "DNF"},
                ],
            },
        ],
    }
    result = process_race_data(response)
    # 2 from Long Overall + 3 from Short Overall = 5
    assert result["total_racers"] == 5
    assert result["total_finished"] == 3
    assert result["total_dns"] == 1
    assert result["total_dnf"] == 1
