# league-finder

Collects bowling leagues from Bowlero / Lucky Strike and LeaguePals into one
database so they can be searched and filtered properly.

## How it stays accurate

- Each source (`league_finder/sources/`) does a full pass over its site and
  yields normalized `League` records.
- `Store.sync` applies a complete pass in one transaction: new leagues are
  added, changed ones updated, and ones no longer listed marked inactive.
- A failed or partial scrape changes nothing. The failure is logged in
  `scrape_runs` and the previous data stays live.
- The fetcher identifies itself, honors robots.txt, rate-limits per host and
  retries transient errors.

## Running

    pip install -e '.[dev]'
    python -m league_finder.runner once                 # all sources once
    python -m league_finder.runner once --source bowlero
    python -m league_finder.runner loop --every 6h      # keep refreshing
    pytest

## Status

The sync engine and fetcher are done. The site parsers in
`sources/bowlero.py` and `sources/leaguepals.py` are not written yet; see the
TODOs there.
