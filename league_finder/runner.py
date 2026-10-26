"""Command line entry point.

    python -m league_finder.runner once [--source bowlero]
    python -m league_finder.runner loop --every 6h
"""

from __future__ import annotations

import argparse
import logging
import time

from .http import Fetcher
from .sources import SOURCES
from .store import Store

log = logging.getLogger("league_finder")


def run_source(name: str, store: Store, fetcher: Fetcher) -> None:
    source = SOURCES[name](fetcher)
    run_id = store.start_run(name)
    try:
        # Materialize the whole scrape before syncing: if anything raises
        # part-way, nothing is retired from the table.
        leagues = list(source.scrape())
    except Exception as e:
        log.exception("%s scrape failed", name)
        store.fail_run(run_id, f"{type(e).__name__}: {e}")
        return
    result = store.sync(run_id, name, leagues)
    log.info(
        "%s: %d seen, %d added, %d updated, %d removed",
        name, result.seen, result.added, result.updated, result.removed,
    )


def run_all(names: list[str], db_path: str) -> None:
    store, fetcher = Store(db_path), Fetcher()
    try:
        for name in names:
            run_source(name, store, fetcher)
    finally:
        fetcher.close()
        store.close()


def parse_interval(s: str) -> int:
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    return int(float(s[:-1]) * units[s[-1]]) if s[-1] in units else int(s)


def main() -> None:
    p = argparse.ArgumentParser(prog="league_finder")
    p.add_argument("mode", choices=["once", "loop"])
    p.add_argument("--source", choices=sorted(SOURCES), action="append")
    p.add_argument("--db", default="leagues.db")
    p.add_argument("--every", default="6h", help="loop interval, e.g. 30m, 6h, 1d")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    names = args.source or sorted(SOURCES)

    if args.mode == "once":
        run_all(names, args.db)
        return
    interval = parse_interval(args.every)
    while True:
        run_all(names, args.db)
        time.sleep(interval)


if __name__ == "__main__":
    main()
