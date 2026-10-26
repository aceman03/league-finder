# league-finder

Personal tool that collects every bowling league listed on Bowlero / Lucky
Strike / AMF (www.bowlero.com) into one local database so they can be
searched and filtered properly. Not for redistribution.

## How it works

- **Centers:** the full center list is read from the public
  `/location-finder` page.
- **Leagues:** the site's league finder is a browser app, so a headless
  browser opens it once per area (one center's zip, 100-mile radius) and
  records the league data the page itself loads. Searches continue until
  every bowling center is covered (~360 centers).
- **Accuracy:** `Store.sync` applies each complete pass in one transaction:
  new leagues are added, changed ones updated, and ones no longer listed
  marked inactive. A failed or partial pass changes nothing; failures are
  logged in `scrape_runs`.
- **Politeness:** one page at a time with a pause between searches,
  robots.txt honored (`/join-league/` is never fetched), images and fonts
  skipped.

## Running

    pip install -e '.[dev]'
    playwright install chromium                         # once
    python -m league_finder.runner once                 # one full pass
    python -m league_finder.runner loop --every 12h     # keep refreshing
    pytest

Data lands in `leagues.db` (SQLite). Each league links to its sign-up page
on bowlero.com.
