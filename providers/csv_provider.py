"""CSV provider: a spreadsheet export read from `data_file`. Format in README.md."""
import csv
import io
import re

MAX_REPORTED_ERRORS = 10

_REQUIRED_COLUMNS = ("bib", "name", "time")
_KNOWN_COLUMNS = _REQUIRED_COLUMNS + ("team", "distance", "category", "gender", "age", "start time")
_NON_FINISH_STATUSES = {"DNS", "DNF", "DSQ"}
_MAX_AGE = 120

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
    """Consume blank and `#` comment lines; return how many lines were consumed."""
    consumed = 0
    while True:
        position = stream.tell()
        line = stream.readline()
        if not line:
            return consumed
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            stream.seek(position)
            return consumed
        consumed += 1


def _read_header(reader, offset):
    for row in reader:
        if any(cell.strip() for cell in row):
            return {}, row, offset + reader.line_num
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
    offset = _skip_preamble(stream)
    reader = csv.reader(stream)
    meta, header_row, header_line = _read_header(reader, offset)
    index, errors = _column_index(header_row, header_line)
    if errors:
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
