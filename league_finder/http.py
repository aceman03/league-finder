"""Polite HTTP fetching: identifies itself, honors robots.txt, rate limits,
and retries transient failures with backoff."""

from __future__ import annotations

import logging
import time
import urllib.robotparser
from urllib.parse import urlsplit

import httpx

log = logging.getLogger(__name__)

USER_AGENT = "LeagueFinderBot/0.1 (+https://github.com/aceman03/league-finder)"


class RobotsDisallowed(Exception):
    pass


class Fetcher:
    def __init__(self, min_interval: float = 2.0, max_retries: int = 3, timeout: float = 30.0):
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            follow_redirects=True,
        )
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}

    def _allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        rp = self._robots.get(origin)
        if rp is None:
            rp = urllib.robotparser.RobotFileParser()
            try:
                resp = self.client.get(f"{origin}/robots.txt")
                rp.parse(resp.text.splitlines() if resp.status_code == 200 else [])
            except httpx.HTTPError:
                rp.parse([])
            self._robots[origin] = rp
        return rp.can_fetch(USER_AGENT, url)

    def _throttle(self, host: str) -> None:
        wait = self._last_request.get(host, 0) + self.min_interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last_request[host] = time.monotonic()

    def get(self, url: str, **kwargs) -> httpx.Response:
        if not self._allowed(url):
            raise RobotsDisallowed(url)
        host = urlsplit(url).netloc
        for attempt in range(self.max_retries + 1):
            self._throttle(host)
            try:
                resp = self.client.get(url, **kwargs)
                if resp.status_code < 500 and resp.status_code != 429:
                    resp.raise_for_status()
                    return resp
                log.warning("%s returned %s (attempt %d)", url, resp.status_code, attempt + 1)
            except httpx.TransportError as e:
                log.warning("%s failed: %s (attempt %d)", url, e, attempt + 1)
            time.sleep(2 ** (attempt + 1))
        resp = self.client.get(url, **kwargs)
        resp.raise_for_status()
        return resp

    def close(self) -> None:
        self.client.close()
