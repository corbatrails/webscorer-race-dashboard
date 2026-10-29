"""CSV provider: a spreadsheet export read from `data_file`. Format in README.md."""
import csv
import io
import os
import re

from providers.base import Provider

MAX_REPORTED_ERRORS = 10

_REQUIRED_COLUMNS = ("bib", "name", "time")
_KNOWN_COLUMNS = _REQUIRED_COLUMNS + ("team", "distance", "category", "gender", "age", "start time")
_METADATA_KEYS = ("name", "date", "sport", "start")
_NON_FINISH_STATUSES = {"DNS", "DNF", "DSQ"}
_MAX_AGE = 120
_DAY_SECONDS = 86400
# A racer start more than this far before the race start is on the next day.
_NEXT_DAY_THRESHOLD_SECONDS = 12 * 3600

_HMS_RE = re.compile(r"^(\d+):([0-5]\d):([0-5]\d(?:\.\d+)?)$")
_MS_RE = re.compile(r"^(\d+):([0-5]\d(?:\.\d+)?)$")
_TOD_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)(?::([0-5]\d(?:\.\d+)?))?$")


class CsvFormatError(ValueError):
    pass


def _parse_elapsed(value):
    match = _HMS_RE.match(value)
    if match:
        return round(int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3)), 3)
    match = _MS_RE.match(value)
    if match:
        return round(int(match.group(1)) * 60 + float(match.group(2)), 3)
    raise ValueError(f"{value!r} is not a time (use H:MM:SS, M:SS, DNS, DNF, DSQ, or leave blank)")


def _parse_time_of_day(value):
    match = _TOD_RE.match(value)
    if not match:
        raise ValueError(f"{value!r} is not a 24-hour time of day (use H:MM or H:MM:SS)")
    seconds = int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3) or 0)
    return round(seconds, 3)


def _parse_age(value):
    if not value.isascii() or not value.isdigit() or int(value) > _MAX_AGE:
        raise ValueError(f"{value!r} is not a whole number from 0 to {_MAX_AGE}")
    return int(value)


def _normalize_header(cell):
    return " ".join(cell.replace("_", " ").lower().split())


def _skip_preamble(stream):
    """Consume blank and `#` comment lines; return (lines consumed, [(line number, comment)])."""
    consumed = 0
    comments = []
    while True:
        position = stream.tell()
        line = stream.readline()
        if not line:
            return consumed, comments
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            stream.seek(position)
            return consumed, comments
        consumed += 1
        if stripped:
            comments.append((consumed, stripped))


def _parse_metadata(comments, errors):
    meta = {}
    for line, comment in comments:
        key, separator, value = comment[1:].partition(":")
        key = key.strip().lower()
        if not separator or not key:
            errors.append(f"row {line}: comment must look like '# key: value'")
        elif key not in _METADATA_KEYS:
            errors.append(f"row {line}: unknown metadata key {key!r} (use {', '.join(_METADATA_KEYS)})")
        elif key == "start":
            try:
                meta[key] = _parse_time_of_day(value.strip())
            except ValueError as e:
                errors.append(f"row {line}, metadata 'start': {e}")
        else:
            meta[key] = value.strip()
    return meta


def _read_header(reader, offset):
    for row in reader:
        if any(cell.strip() for cell in row):
            return row, offset + reader.line_num
    raise CsvFormatError("no header row found (expected columns: bib, name, time)")


def _column_index(header_row, header_line):
    index = {}
    errors = []
    for position, cell in enumerate(header_row):
        name = _normalize_header(cell)
        if name not in _KNOWN_COLUMNS:
            continue
        if name in index:
            errors.append(f"row {header_line}, column '{name}': duplicate column")
        else:
            index[name] = position
    for name in _REQUIRED_COLUMNS:
        if name not in index:
            errors.append(f"row {header_line}: required column '{name}' is missing")
    return index, errors


def _cell(row, index, name):
    position = index.get(name)
    if position is None or position >= len(row):
        return ""
    return row[position].strip()


def _parse_row(row, index, line, errors):
    def check(column, parse, value):
        try:
            return parse(value)
        except ValueError as e:
            errors.append(f"row {line}, column '{column}': {e}")
            return None

    name = _cell(row, index, "name")
    if not name:
        errors.append(f"row {line}, column 'name': must not be blank")

    time_text = _cell(row, index, "time")
    upper = time_text.upper()
    elapsed = None
    if upper in _NON_FINISH_STATUSES:
        status, time_display = upper, time_text
    elif upper in ("", "-"):
        status, time_display = "IN_PROGRESS", "-"
    else:
        status, time_display = "FINISHED", time_text
        elapsed = check("time", _parse_elapsed, time_text)

    age_text = _cell(row, index, "age")
    age = check("age", _parse_age, age_text) if age_text else None

    start_text = _cell(row, index, "start time")
    start = check("start time", _parse_time_of_day, start_text) if start_text else None

    finish = round(start + elapsed, 3) if start is not None and elapsed is not None else None
    return {
        "bib": _cell(row, index, "bib"),
        "name": name,
        "team": _cell(row, index, "team"),
        "distance": _cell(row, index, "distance"),
        "category": _cell(row, index, "category"),
        "gender": _cell(row, index, "gender"),
        "age": age,
        "status": status,
        "time_display": time_display,
        "elapsed_seconds": elapsed,
        "start_seconds": start,
        "finish_tod_seconds": finish,
        "source_place": "",
        "in_overall": True,
        "category_groups": [],
    }


def _raise_errors(errors):
    shown = errors[:MAX_REPORTED_ERRORS]
    message = "; ".join(shown)
    if len(errors) > len(shown):
        message += f"; and {len(errors) - len(shown)} more"
    raise CsvFormatError(message)


def _parse_rows(text):
    """Return (meta, racers) for the CSV text, or raise CsvFormatError listing every problem."""
    if text.startswith("\ufeff"):
        text = text[1:]
    stream = io.StringIO(text, newline="")
    offset, comments = _skip_preamble(stream)
    errors = []
    meta = _parse_metadata(comments, errors)
    reader = csv.reader(stream)
    header_row, header_line = _read_header(reader, offset)
    index, header_errors = _column_index(header_row, header_line)
    errors.extend(header_errors)
    if header_errors:
        _raise_errors(errors)

    racers = []
    first_row_for_bib = {}
    while True:
        previous = reader.line_num
        try:
            row = next(reader)
        except StopIteration:
            break
        if not any(cell.strip() for cell in row):
            continue
        line = offset + previous + 1
        racer = _parse_row(row, index, line, errors)
        if racer["bib"]:
            key = (racer["distance"], racer["bib"])
            if key in first_row_for_bib:
                errors.append(
                    f"row {line}, column 'bib': duplicate bib {racer['bib']!r} in distance "
                    f"{racer['distance']!r} (first on row {first_row_for_bib[key]})"
                )
            else:
                first_row_for_bib[key] = line
        racers.append(racer)

    if errors:
        _raise_errors(errors)
    if not racers:
        raise CsvFormatError("no racer rows found")
    return meta, racers


def _race_start_seconds(meta, racers):
    if "start" in meta:
        return meta["start"]
    starts = [r["start_seconds"] for r in racers if r["start_seconds"] is not None]
    return min(starts) if starts else 0


def _derive_groups(racers):
    overall = []
    categories = []
    for racer in racers:
        distance = racer["distance"]
        group = {"tier": "overall", "distance": distance, "category": "", "gender": ""}
        if group not in overall:
            overall.append(group)
        if racer["category"]:
            group = {"tier": "category", "distance": distance, "category": racer["category"], "gender": ""}
            if group not in categories:
                categories.append(group)
            racer["category_groups"].append(
                {"distance": distance, "category": racer["category"], "gender": "", "source_place": ""}
            )
    return overall + categories


def normalize(raw):
    """Turn `{"name": file stem, "text": file text}` into a RaceSnapshot."""
    meta, racers = _parse_rows(raw["text"])
    race_start = _race_start_seconds(meta, racers)
    for racer in racers:
        start = racer["start_seconds"]
        if start is not None and start < race_start - _NEXT_DAY_THRESHOLD_SECONDS:
            racer["start_seconds"] = start + _DAY_SECONDS
            if racer["finish_tod_seconds"] is not None:
                racer["finish_tod_seconds"] += _DAY_SECONDS
    return {
        "error": None,
        "race": {
            "name": meta.get("name") or raw["name"],
            "date": meta.get("date", ""),
            "sport": meta.get("sport", ""),
            "start_seconds": race_start,
        },
        "groups": _derive_groups(racers),
        "racers": racers,
    }


def fetch(config, secrets):
    path = config["data_file"]
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    return {"name": os.path.splitext(os.path.basename(path))[0], "text": text}


PROVIDER = Provider(
    name="csv",
    required_secrets={},
    requires_data_file=True,
    fetch=fetch,
    normalize=normalize,
    list_races=None,
)
