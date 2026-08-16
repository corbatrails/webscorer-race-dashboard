from data_processing import _classify_racer, _classify_group, _group_name, process_race_data, build_pages, build_finish_chart_data


def test_classify_group_overall():
    assert _classify_group({"Distance": "Long", "Overall": True}) == "overall"
    assert _classify_group({"Category": "Overall", "Overall": True}) == "overall"


def test_classify_group_category():
    assert _classify_group({"Category": "Masters Men", "Gender": "Male"}) == "category"
    assert _classify_group({"Category": "Male 20-29"}) == "category"


def test_classify_group_skipped():
    assert _classify_group({"Distance": "Long", "Gender": "Male"}) is None
    assert _classify_group({"Gender": "Female"}) is None


def test_group_name_overall():
    assert _group_name({"Distance": "Long Course (88 miles)", "Overall": True}, "overall") == "Long Course (88 miles)"
    assert _group_name({"Category": "Overall", "Overall": True}, "overall") == "Overall"


def test_group_name_category_with_gender():
    g = {"Distance": "Long", "Category": "Adult Long Course (age 18-44)", "Gender": "Male"}
    assert _group_name(g, "category") == "Adult Long Course (age 18-44) Male"


def test_group_name_category_without_gender():
    assert _group_name({"Category": "Male 20-29"}, "category") == "Male 20-29"


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
                {"Place": "-", "Bib": "106", "Name": "Ivan", "Time": "-"},
                {"Place": "-", "Bib": "205", "Name": "Judy", "Time": "-"},
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
    assert result["total_racers"] == 11
    assert result["total_finished"] == 6
    assert result["total_dns"] == 1
    assert result["total_dnf"] == 1
    assert result["total_dsq"] == 1
    assert len(result["categories"]) == 3


def test_process_race_data_categories():
    result = process_race_data(MOCK_API_RESPONSE)
    cat0 = result["categories"][0]
    assert cat0["name"] == "Overall"
    assert len(cat0["racers"]) == 11

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
    assert len(pages[1]["racers"]) == 11
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
    assert result["total_racers"] == 11
    assert result["total_finished"] == 6
    assert len(result["categories"]) == 3


def test_classify_racer():
    assert _classify_racer({"Time": "00:18:30"}) == "FINISHED"
    assert _classify_racer({"Time": "DNS"}) == "DNS"
    assert _classify_racer({"Time": "DNF"}) == "DNF"
    assert _classify_racer({"Time": "DSQ"}) == "DSQ"
    assert _classify_racer({"Time": "-"}) == "IN_PROGRESS"
    assert _classify_racer({"Time": ""}) == "IN_PROGRESS"
    assert _classify_racer({}) == "IN_PROGRESS"


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
    # Totals unchanged (from Overall groups)
    assert result["total_racers"] == 5
    assert result["total_finished"] == 3
    assert result["total_dns"] == 1
    assert result["total_dnf"] == 1
    # Distance+Gender group skipped; only 2 Overall groups remain
    assert len(result["categories"]) == 2
    assert result["categories"][0]["name"] == "Long"
    assert result["categories"][1]["name"] == "Short"


def test_process_race_data_multi_distance_with_categories():
    response = {
        "RaceInfo": {"RaceId": 300, "Name": "Big Race", "Date": "2026-08-14", "Sport": "Cycling"},
        "Results": [
            {
                "Grouping": {"Distance": "Long", "Overall": True},
                "Racers": [
                    {"Place": 1, "Bib": "1", "Name": "A", "Time": "01:00:00"},
                    {"Place": 2, "Bib": "2", "Name": "B", "Time": "01:10:00"},
                ],
            },
            {
                "Grouping": {"Distance": "Long", "Gender": "Male"},
                "Racers": [
                    {"Place": 1, "Bib": "1", "Name": "A", "Time": "01:00:00"},
                ],
            },
            {
                "Grouping": {"Distance": "Long", "Category": "Masters", "Gender": "Male"},
                "Racers": [
                    {"Place": 1, "Bib": "1", "Name": "A", "Time": "01:00:00"},
                ],
            },
            {
                "Grouping": {"Distance": "Short", "Overall": True},
                "Racers": [
                    {"Place": 1, "Bib": "3", "Name": "C", "Time": "00:30:00"},
                ],
            },
            {
                "Grouping": {"Distance": "Short", "Category": "Adult", "Gender": "Female"},
                "Racers": [
                    {"Place": 1, "Bib": "4", "Name": "D", "Time": "00:35:00"},
                ],
            },
        ],
    }
    result = process_race_data(response)
    # Ordered: Long Overall, Long categories, Short Overall, Short categories
    assert len(result["categories"]) == 4
    assert result["categories"][0]["name"] == "Long"
    assert result["categories"][1]["name"] == "Masters Male"
    assert result["categories"][2]["name"] == "Short"
    assert result["categories"][3]["name"] == "Adult Female"


def test_process_race_data_filter_overall_off():
    response = {
        "RaceInfo": {"RaceId": 300, "Name": "Race", "Date": "", "Sport": ""},
        "Results": [
            {
                "Grouping": {"Distance": "Long", "Overall": True},
                "Racers": [{"Place": 1, "Bib": "1", "Name": "A", "Time": "01:00:00"}],
            },
            {
                "Grouping": {"Distance": "Long", "Category": "Masters", "Gender": "Male"},
                "Racers": [{"Place": 1, "Bib": "1", "Name": "A", "Time": "01:00:00"}],
            },
        ],
    }
    result = process_race_data(response, show_overall_results=False)
    assert len(result["categories"]) == 1
    assert result["categories"][0]["name"] == "Masters Male"
    # Totals still counted from Overall groups
    assert result["total_racers"] == 1


CHART_API_RESPONSE = {
    "RaceInfo": {
        "Name": "Test Race",
        "StartTime": "Saturday, August 9, 2026 2:00 PM (GMT-5)",
    },
    "Results": [
        {
            "Grouping": {"Distance": "Short (5K)", "Overall": True},
            "Racers": [
                {"Name": "Alice", "Time": "-", "StartTime": "14:00:00.0", "Distance": "Short (5K)"},
                {"Name": "Bob", "Time": "DNS", "StartTime": "14:00:00.0", "Distance": "Short (5K)"},
            ],
        },
    ],
}


def test_build_finish_chart_no_finishers():
    result = build_finish_chart_data(CHART_API_RESPONSE)
    assert result is None


CHART_API_FINISHERS = {
    "RaceInfo": {
        "Name": "Test Race",
        "StartTime": "Saturday, August 9, 2026 2:00 PM (GMT-5)",
    },
    "Results": [
        {
            "Grouping": {"Distance": "Short (5K)", "Overall": True},
            "Racers": [
                {"Name": "A", "Time": "0:20:00.0", "StartTime": "14:00:00.0", "Distance": "Short (5K)"},
                {"Name": "B", "Time": "0:25:00.0", "StartTime": "14:00:00.0", "Distance": "Short (5K)"},
                {"Name": "C", "Time": "0:40:00.0", "StartTime": "14:00:00.0", "Distance": "Short (5K)"},
            ],
        },
        {
            "Grouping": {"Distance": "Long (10K)", "Overall": True},
            "Racers": [
                {"Name": "D", "Time": "0:50:00.0", "StartTime": "14:00:00.0", "Distance": "Long (10K)"},
                {"Name": "E", "Time": "1:05:00.0", "StartTime": "14:00:00.0", "Distance": "Long (10K)"},
            ],
        },
    ],
}


def test_build_finish_chart_basic():
    result = build_finish_chart_data(CHART_API_FINISHERS, bucket_minutes=15)
    assert result is not None
    # Start hour floor is 14:00, finishers at 14:20, 14:25, 14:40, 14:50, 15:05
    # Buckets: 14:00, 14:15, 14:30, 14:45, 15:00
    assert result["labels"] == ["14:00", "14:15", "14:30", "14:45", "15:00"]
    assert len(result["datasets"]) == 2
    # Short: 0 in 14:00, 2 in 14:15 (14:20/14:25), 1 in 14:30 (14:40), 0 in 14:45, 0 in 15:00
    short_ds = next(ds for ds in result["datasets"] if ds["label"] == "Short (5K)")
    assert short_ds["data"] == [0, 2, 1, 0, 0]
    # Long: 0, 0, 0, 1 in 14:45 (14:50), 1 in 15:00 (15:05)
    long_ds = next(ds for ds in result["datasets"] if ds["label"] == "Long (10K)")
    assert long_ds["data"] == [0, 0, 0, 1, 1]


def test_build_finish_chart_missing_start_time():
    response = {
        "RaceInfo": {"Name": "Test", "StartTime": "Saturday, August 9, 2026 2:00 PM (GMT-5)"},
        "Results": [
            {
                "Grouping": {"Distance": "5K", "Overall": True},
                "Racers": [
                    {"Name": "A", "Time": "0:20:00.0", "StartTime": "14:00:00.0", "Distance": "5K"},
                    {"Name": "B", "Time": "0:25:00.0", "StartTime": None, "Distance": "5K"},
                ],
            },
        ],
    }
    result = build_finish_chart_data(response, bucket_minutes=15)
    assert result is not None
    assert result["labels"] == ["14:00", "14:15"]
    assert result["datasets"][0]["data"] == [0, 1]


def test_build_finish_chart_skips_category_groups():
    response = {
        "RaceInfo": {"Name": "Test", "StartTime": "Saturday, August 9, 2026 2:00 PM (GMT-5)"},
        "Results": [
            {
                "Grouping": {"Distance": "5K", "Overall": True},
                "Racers": [
                    {"Name": "A", "Time": "0:20:00.0", "StartTime": "14:00:00.0", "Distance": "5K"},
                ],
            },
            {
                "Grouping": {"Distance": "5K", "Category": "Male"},
                "Racers": [
                    {"Name": "A", "Time": "0:20:00.0", "StartTime": "14:00:00.0", "Distance": "5K"},
                ],
            },
        ],
    }
    result = build_finish_chart_data(response, bucket_minutes=15)
    # Only 1 finisher counted (from Overall), not 2
    total = sum(result["datasets"][0]["data"])
    assert total == 1


def test_process_race_data_filter_category_off():
    response = {
        "RaceInfo": {"RaceId": 300, "Name": "Race", "Date": "", "Sport": ""},
        "Results": [
            {
                "Grouping": {"Distance": "Long", "Overall": True},
                "Racers": [{"Place": 1, "Bib": "1", "Name": "A", "Time": "01:00:00"}],
            },
            {
                "Grouping": {"Distance": "Long", "Category": "Masters", "Gender": "Male"},
                "Racers": [{"Place": 1, "Bib": "1", "Name": "A", "Time": "01:00:00"}],
            },
        ],
    }
    result = process_race_data(response, show_category_results=False)
    assert len(result["categories"]) == 1
    assert result["categories"][0]["name"] == "Long"
