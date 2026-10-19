"""The provider contract: how a timing platform plugs into the dashboard.

A provider fetches a raw payload and normalizes it into a `RaceSnapshot`
(schema in `normalizer.py`); nothing downstream knows which platform it came from.
See `docs/superpowers/specs/2026-10-18-provider-abstraction-design.md`.

Rules
-----
- `fetch(config, secrets)` does all I/O and returns an opaque raw payload. It honors
  `config["data_file"]` when the provider supports offline input. It may raise, and
  must never put secrets in an exception message.
- `normalize(raw)` is pure: no config, files or network.
- The snapshot keeps the Phase 1 invariants: `status == "FINISHED"` iff
  `elapsed_seconds` is set, every `in_overall` racer's distance has an Overall group,
  and every category membership matches a category group.
- A platform-level error may be returned as `snapshot["error"]` with empty `racers`
  and `groups`; anything else raises.
"""
from dataclasses import dataclass
from typing import Any, Callable, List, Mapping, Optional, TypedDict

from normalizer import RaceSnapshot


class RaceChoice(TypedDict):
    id: str
    name: str
    date: str
    sport: str


@dataclass(frozen=True)
class Provider:
    name: str  # value of the `source` option
    required_secrets: Mapping[str, str]  # config key -> env var, e.g. {"api_id": "WEBSCORER_API_ID"}
    requires_data_file: bool  # True when `data_file` is the provider's only input
    fetch: Callable[[dict, dict], Any]
    normalize: Callable[[Any], RaceSnapshot]
    list_races: Optional[Callable[[dict, dict], List[RaceChoice]]] = None
