"""Bowlero / Lucky Strike / AMF (one site, www.bowlero.com).

The per-center /location/<slug>/leagues pages don't list leagues; the real
listings come from the league finder (/league-finder), a client-side app that
loads league data for the centers near the searched zip code. So:

1. Read the center list embedded in the public /location-finder page.
2. Open the league finder in a headless browser, searching one center's zip
   at a time, and record the league data the page itself loads. Each search
   covers every center within the radius; repeat until all centers are
   covered.

The browser loads the site like a normal visitor. It does not call the data
feed directly, and it skips /join-league/ prefetches (disallowed by
robots.txt).
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Iterator
from urllib.parse import parse_qs, urlencode, urlsplit

from ..models import League
from .base import Source

log = logging.getLogger(__name__)

BASE_URL = "https://www.bowlero.com"
LEAGUES_FEED = "/api/leagues"
SEARCH_RADIUS = 100  # miles; the largest the finder offers

_NEXT_PUSH = re.compile(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)')
_CENTERS = re.compile(r'"centers":\s*\[')
# Body is already decoded by httpx, so these no longer describe it.
_HOP_HEADERS = ("content-encoding", "content-length", "transfer-encoding")


class ScrapeError(Exception):
    pass


def parse_centers(html: str) -> list[dict]:
    """Extract the center list from the /location-finder page's embedded
    Next.js payload."""
    payload = "".join(json.loads(s) for s in _NEXT_PUSH.findall(html))
    m = _CENTERS.search(payload)
    if not m:
        raise ScrapeError("center list not found on location-finder page")
    centers, _ = json.JSONDecoder().raw_decode(payload, m.end() - 1)
    return centers


def feed_center_numbers(url: str) -> set[int]:
    """Center numbers a league-feed request asked for."""
    raw = parse_qs(urlsplit(url).query).get("centerNumbers", [""])[0]
    return {int(n) for n in raw.split(",") if n.strip().isdigit()}


def _time_of(dt: str | None) -> str | None:
    return dt[11:16] if dt and len(dt) >= 16 else None


def _date_of(dt: str | None) -> str | None:
    return dt[:10] if dt else None


def to_league(raw: dict, center: dict | None) -> League:
    center = center or {}
    location = center.get("location") or {}
    days = [d.get("description") or d.get("constantName") for d in raw.get("leagueDays") or []]
    return League(
        source="bowlero",
        source_id=raw["leagueId"],
        name=(raw.get("leagueName") or "").strip(),
        url=f"{BASE_URL}/join-league/{raw['leagueId']}",
        center_name=center.get("name"),
        address=center.get("streetAddress"),
        city=center.get("city"),
        state=center.get("state"),
        postal_code=center.get("zipCode"),
        latitude=location.get("lat"),
        longitude=location.get("lon"),
        day_of_week=", ".join(d for d in days if d) or None,
        start_time=_time_of(raw.get("startDateTime")),
        season_start=_date_of(raw.get("startDateTime")),
        season_weeks=raw.get("numberOfWeeks"),
        team_size=raw.get("playersPerTeam"),
        league_type=raw.get("leagueTypeDescription") or None,
        description=(raw.get("description") or "").strip() or None,
        extra={
            "center_number": raw.get("bowlingCenterNumber"),
            "brand": center.get("brand"),
            "center_slug": center.get("slug"),
            "subtype": raw.get("leagueSubTypeDescription") or None,
            "skill_levels": raw.get("leagueSkillLevels") or [],
            "frequency": raw.get("leagueFrequencyDescription") or None,
            "number_of_teams": raw.get("numberOfTeams"),
            "meeting_datetime": raw.get("meetingDateTime"),
            "start_datetime": raw.get("startDateTime"),
            "end_date": _date_of(raw.get("endDate")),
        },
    )


def parse_feed(body: dict, centers_by_number: dict[int, dict]) -> list[League]:
    leagues = []
    for record in body.get("records") or []:
        center = centers_by_number.get(record.get("centerNumber"))
        for raw in record.get("leagues") or []:
            if raw.get("leagueId"):
                leagues.append(to_league(raw, center))
    return leagues


class BowleroSource(Source):
    name = "bowlero"

    page_timeout_ms = 90_000
    feed_timeout_ms = 45_000

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self._cdn_cache: dict[str, tuple[int, dict, bytes]] = {}

    def centers(self) -> list[dict]:
        html = self.fetcher.get(f"{BASE_URL}/location-finder").text
        centers = [c for c in parse_centers(html) if c.get("centerType") == "BOWLING"]
        if not centers:
            raise ScrapeError("no bowling centers found")
        return centers

    def scrape(self) -> Iterator[League]:
        from playwright.sync_api import sync_playwright

        centers = self.centers()
        by_number = {c["centerNumber"]: c for c in centers}
        uncovered = sorted(by_number, key=lambda n: str(by_number[n].get("zipCode")))
        covered: set[int] = set()
        seen: set[str] = set()
        log.info("bowlero: %d bowling centers", len(centers))

        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                ctx = browser.new_context(locale="en-US")
                ctx.route("**/*", self._filter_requests)
                page = ctx.new_page()
                for number in uncovered:
                    if number in covered:
                        continue
                    center = by_number[number]
                    zip_code = center.get("zipCode")
                    asked, body = self._search(page, zip_code)
                    if number not in asked:
                        # The finder can't place some locations (e.g. Puerto Rico)
                        # and falls back to a default area, so the center is
                        # unreachable through the site's own search.
                        log.warning("bowlero: search %s didn't include center %s (%s)",
                                    zip_code, number, center.get("name"))
                    covered |= asked | {number}
                    for league in parse_feed(body, by_number):
                        if league.source_id not in seen:
                            seen.add(league.source_id)
                            yield league
                    log.info("bowlero: searched %s, %d/%d centers covered, %d leagues",
                             zip_code, len(covered & by_number.keys()), len(by_number), len(seen))
                    time.sleep(self.fetcher.min_interval)
            finally:
                browser.close()

    def _cdn_parens(self, route) -> None:
        # The site's CDN 404s on chunk URLs whose "(group)" path segments arrive
        # percent-encoded, which some proxies do; fetch them with literal parens.
        # Chunk names are content-hashed, so successful responses are cached.
        url = route.request.url
        fixed = url.replace("%28", "(").replace("%29", ")")
        if "(" not in fixed:
            route.continue_()
            return
        cached = self._cdn_cache.get(fixed)
        if cached is None:
            resp = self.fetcher.client.get(fixed)
            headers = {k: v for k, v in resp.headers.items() if k.lower() not in _HOP_HEADERS}
            cached = (resp.status_code, headers, resp.content)
            if resp.status_code == 200:
                self._cdn_cache[fixed] = cached
        status, headers, body = cached
        route.fulfill(status=status, headers=headers, body=body)

    def _filter_requests(self, route) -> None:
        req = route.request
        if "/join-league/" in req.url or req.resource_type in ("image", "media", "font"):
            route.abort()
        elif "cloudfront.net" in req.url:
            self._cdn_parens(route)
        else:
            route.continue_()

    def _search(self, page, zip_code: str, attempts: int = 2) -> tuple[set[int], dict]:
        qs = urlencode({"type": "league", "brand": "all", "radius": SEARCH_RADIUS, "search": zip_code})
        url = f"{BASE_URL}/league-finder?{qs}"
        for attempt in range(1, attempts + 1):
            try:
                with page.expect_response(
                    lambda r: urlsplit(r.url).path == LEAGUES_FEED and r.request.method == "GET",
                    timeout=self.feed_timeout_ms,
                ) as info:
                    # Don't wait for the full page load: the page keeps working
                    # after the feed arrives and Chromium may evict its body.
                    page.goto(url, wait_until="commit", timeout=self.page_timeout_ms)
                resp = info.value
                if resp.status != 200:
                    raise ScrapeError(f"league feed returned {resp.status}")
                return feed_center_numbers(resp.url), resp.json()
            except Exception as e:
                log.warning("bowlero: search %s failed (attempt %d): %s", zip_code, attempt, e)
                if attempt == attempts:
                    raise ScrapeError(f"league search for {zip_code} failed") from e
                time.sleep(5 * attempt)
        raise AssertionError("unreachable")
