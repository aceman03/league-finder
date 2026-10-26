"""Normalized league record shared by every source.

Each source maps whatever its site exposes onto this shape so search and
filtering can work across Bowlero/Lucky Strike and LeaguePals uniformly.
Fields a source can't provide stay None.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class League:
    source: str  # e.g. "bowlero", "leaguepals"
    source_id: str  # stable id within the source (URL slug, numeric id, ...)
    name: str
    url: str

    center_name: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    day_of_week: str | None = None  # "Monday" ... "Sunday"
    start_time: str | None = None  # "18:30", local to the center
    season_start: str | None = None  # ISO date
    season_weeks: int | None = None
    team_size: int | None = None
    league_type: str | None = None  # "traditional", "short season", "youth", ...
    handicap: bool | None = None
    cost_per_week: float | None = None
    open_spots: bool | None = None
    description: str | None = None

    # Anything source-specific we don't normalize yet, kept for later use.
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.source}:{self.source_id}"

    def content_hash(self) -> str:
        """Hash of everything except identity, used to detect changes."""
        data = asdict(self)
        for k in ("source", "source_id"):
            data.pop(k)
        blob = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(blob.encode()).hexdigest()
