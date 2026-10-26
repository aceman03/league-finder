"""SQLite store that keeps the league table in sync with each source.

After a complete scrape of a source:
- new leagues are inserted,
- changed leagues are updated (detected by content hash),
- leagues no longer listed are marked inactive (kept for history).
Every run is recorded in scrape_runs so staleness and failures are visible.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from .models import League

SCHEMA = """
CREATE TABLE IF NOT EXISTS leagues (
    key          TEXT PRIMARY KEY,
    source       TEXT NOT NULL,
    source_id    TEXT NOT NULL,
    data         TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    active       INTEGER NOT NULL DEFAULT 1,
    first_seen   TEXT NOT NULL,
    last_seen    TEXT NOT NULL,
    last_changed TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS leagues_source_active ON leagues(source, active);

CREATE TABLE IF NOT EXISTS scrape_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    status      TEXT NOT NULL,  -- running | ok | failed
    seen        INTEGER,
    added       INTEGER,
    updated     INTEGER,
    removed     INTEGER,
    error       TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class SyncResult:
    seen: int = 0
    added: int = 0
    updated: int = 0
    removed: int = 0


class Store:
    def __init__(self, path: str = "leagues.db"):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def start_run(self, source: str) -> int:
        cur = self.db.execute(
            "INSERT INTO scrape_runs (source, started_at, status) VALUES (?, ?, 'running')",
            (source, _now()),
        )
        self.db.commit()
        return cur.lastrowid

    def fail_run(self, run_id: int, error: str) -> None:
        self.db.execute(
            "UPDATE scrape_runs SET finished_at = ?, status = 'failed', error = ? WHERE id = ?",
            (_now(), error, run_id),
        )
        self.db.commit()

    def sync(self, run_id: int, source: str, leagues: Iterable[League]) -> SyncResult:
        """Apply a complete scrape of `source`. Runs in one transaction, so a
        crash part-way leaves the previous state untouched."""
        now = _now()
        result = SyncResult()
        seen_keys: set[str] = set()
        with self.db:
            for league in leagues:
                if league.source != source or league.key in seen_keys:
                    continue
                seen_keys.add(league.key)
                h = league.content_hash()
                row = self.db.execute(
                    "SELECT content_hash, active FROM leagues WHERE key = ?", (league.key,)
                ).fetchone()
                data = json.dumps(asdict(league), default=str)
                if row is None:
                    self.db.execute(
                        "INSERT INTO leagues VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)",
                        (league.key, source, league.source_id, data, h, now, now, now),
                    )
                    result.added += 1
                elif row["content_hash"] != h or not row["active"]:
                    self.db.execute(
                        "UPDATE leagues SET data = ?, content_hash = ?, active = 1,"
                        " last_seen = ?, last_changed = ? WHERE key = ?",
                        (data, h, now, now, league.key),
                    )
                    result.updated += 1
                else:
                    self.db.execute("UPDATE leagues SET last_seen = ? WHERE key = ?", (now, league.key))
            result.seen = len(seen_keys)

            stale = [
                r["key"]
                for r in self.db.execute(
                    "SELECT key FROM leagues WHERE source = ? AND active = 1", (source,)
                )
                if r["key"] not in seen_keys
            ]
            self.db.executemany(
                "UPDATE leagues SET active = 0, last_changed = ? WHERE key = ?",
                [(now, k) for k in stale],
            )
            result.removed = len(stale)

            self.db.execute(
                "UPDATE scrape_runs SET finished_at = ?, status = 'ok', seen = ?, added = ?,"
                " updated = ?, removed = ? WHERE id = ?",
                (now, result.seen, result.added, result.updated, result.removed, run_id),
            )
        return result

    def active_leagues(self, source: str | None = None) -> list[League]:
        sql = "SELECT data FROM leagues WHERE active = 1"
        params: tuple = ()
        if source:
            sql += " AND source = ?"
            params = (source,)
        return [League(**json.loads(r["data"])) for r in self.db.execute(sql, params)]

    def close(self) -> None:
        self.db.close()
