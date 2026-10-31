_NO_PLACE = "-"


def _group_name(group, tier):
    if tier == "overall":
        return group.get("distance") or "Overall"
    parts = [group.get("category", "")]
    gender = group.get("gender")
    if gender:
        parts.append(gender)
    return " ".join(parts)


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


def build_finish_chart_data(snapshot, bucket_minutes=15):
    if snapshot["error"]:
        return None

    floor_hour = (snapshot["race"]["start_seconds"] // 3600) * 3600

    distance_order = []
    finishers_by_distance = {}
    for group in snapshot["groups"]:
        if group["tier"] == "overall":
            distance_order.append(group["distance"])
            finishers_by_distance[group["distance"]] = []

    for racer in snapshot["racers"]:
        if racer["in_overall"] and racer["finish_tod_seconds"] is not None:
            finishers_by_distance[racer["distance"]].append(racer["finish_tod_seconds"])

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


def build_demographics_data(snapshot):
    if snapshot["error"]:
        return None

    overall_racers = [r for r in snapshot["racers"] if r["in_overall"]]
    if not overall_racers:
        return None

    distance_order = [g["distance"] or "Overall" for g in snapshot["groups"] if g["tier"] == "overall"]
    distance_counts = {name: 0 for name in distance_order}
    ages = []
    gender_counts = {}
    solo_count = 0
    team_counts = {}

    for racer in overall_racers:
        distance_counts[racer["distance"] or "Overall"] += 1

        if racer["age"] is not None:
            ages.append(racer["age"])

        gender = racer["gender"] or "Unknown"
        gender_counts[gender] = gender_counts.get(gender, 0) + 1

        if racer["team"]:
            team_counts[racer["team"]] = team_counts.get(racer["team"], 0) + 1
        else:
            solo_count += 1

    return {
        "total_registrants": len(overall_racers),
        "age": _build_age_stats(ages),
        "gender": _build_gender_stats(gender_counts),
        "distance": {
            "labels": distance_order,
            "counts": [distance_counts[d] for d in distance_order],
        },
        "teams": _build_team_stats(solo_count, team_counts),
    }


def _crossed_laps(racer, elapsed_limit):
    """Lap numbers crossed by `elapsed_limit` (all recorded crossings when it is None)."""
    return [
        c["lap_number"] for c in racer["lap_crossings"]
        if elapsed_limit is None or c["elapsed_seconds"] <= elapsed_limit
    ]


_LAP_TOTAL_KEYS = ("registered", "dns", "not_started", "on_course", "finished", "dnf", "dsq", "started")


def build_lap_overview_data(snapshot, observation_seconds):
    """Per-distance lap state for the Lap Overview page.

    `observation_seconds` is event-local time in seconds since midnight of the event
    date, on the same basis as `Racer.start_seconds`. Every overall racer lands in
    exactly one of DNS, Not Started, On Course (one lap cell), Finished, DNF or DSQ.
    """
    if snapshot["error"]:
        return None
    groups = [g for g in snapshot["groups"] if g["tier"] == "overall"]
    if not groups:
        return None

    overall_racers = [r for r in snapshot["racers"] if r["in_overall"]]
    distances = []
    for group in groups:
        lap_count = group["lap_count"]
        entry = {
            "name": group["distance"] or "Overall",
            "lap_count": lap_count,
            "registered": 0,
            "dns": 0,
            "not_started": 0,
            "started": 0,
            "on_course": 0,
            "on_course_by_lap": [0] * lap_count,
            "dnf_by_lap": [0] * lap_count,
            "dnf_without_crossing": 0,
            "finished": 0,
            "dnf": 0,
            "dsq": 0,
        }
        for racer in overall_racers:
            if racer["distance"] != group["distance"]:
                continue
            entry["registered"] += 1
            status = racer["status"]
            start = racer["start_seconds"]
            if status == "DNS":
                entry["dns"] += 1
                continue
            if status == "IN_PROGRESS" and start is not None and start > observation_seconds:
                entry["not_started"] += 1
                continue
            entry["started"] += 1
            elapsed_limit = observation_seconds - start if start is not None else None
            if status == "FINISHED":
                entry["finished"] += 1
            elif status == "DSQ":
                entry["dsq"] += 1
            elif status == "DNF":
                entry["dnf"] += 1
                crossed = _crossed_laps(racer, elapsed_limit)
                if crossed:
                    entry["dnf_by_lap"][max(crossed) - 1] += 1
                else:
                    entry["dnf_without_crossing"] += 1
            else:
                crossed = _crossed_laps(racer, elapsed_limit)
                lap = min((max(crossed) if crossed else 0) + 1, lap_count)
                entry["on_course_by_lap"][lap - 1] += 1
                entry["on_course"] += 1
        distances.append(entry)

    totals = {key: sum(d[key] for d in distances) for key in _LAP_TOTAL_KEYS}
    return {"totals": totals, "distances": distances}


def build_pages(dashboard_data, demographics=None, max_rows=18, lap_overview=None):
    """Build page list. Categories are sent whole; the frontend splits by viewport size."""
    pages = [{"type": "summary", "title": "Summary", "data": dashboard_data}]

    if lap_overview:
        pages.append({"type": "lap_overview", "title": "Lap Overview", "data": lap_overview})

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
