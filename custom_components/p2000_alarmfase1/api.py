"""API Client for scraping P2000 messages from alarmfase1.nl."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime

from aiohttp import ClientError, ClientSession
from bs4 import BeautifulSoup

from .const import (
    API_TIMEOUT,
    BASE_URL,
    DEFAULT_SERVICE_TYPE,
    SERVICE_HELI,
    SERVICE_KNRM,
    SERVICE_NAME_MAP,
)

_LOGGER = logging.getLogger(__name__)


class ScraperApiError(Exception):
    """Base error."""


class ScraperApiConnectionError(ScraperApiError):
    """Connection error."""


class ScraperApiParsingError(ScraperApiError):
    """Parsing error."""


class ScraperApiNoDataError(ScraperApiError):
    """Region not found."""


def normalize_region_path(path: str) -> str:
    """Accept 'limburg-zuid/kerkrade', '/limburg-zuid/' or a full URL."""
    path = (path or "").strip()
    if path.lower().startswith(("http://", "https://")):
        path = path.split("alarmfase1.nl", 1)[-1]
    return path.strip().strip("/").lower()


def normalize_service(raw: str | None, title: str = "") -> str:
    """Map the site's Dutch service attribute to a stable English type."""
    text = f"{raw or ''} {title}".lower()
    if "traumaheli" in text or "lifeliner" in text or "mmt" in text:
        return SERVICE_HELI
    if "knrm" in text or "reddingsbrigade" in text:
        return SERVICE_KNRM
    key = (raw or "").strip().lower()
    if key in SERVICE_NAME_MAP:
        return SERVICE_NAME_MAP[key]
    t = title.lower()
    if t.startswith(("a1", "a2", "b1", "b2")):
        return SERVICE_NAME_MAP["ambulance"]
    if t.startswith(("p1", "p2", "p3", "prio")):
        return SERVICE_NAME_MAP["brandweer"]
    if t.startswith("pol"):
        return SERVICE_NAME_MAP["politie"]
    return DEFAULT_SERVICE_TYPE


def _text(tag) -> str | None:
    return tag.get_text(strip=True) if tag else None


def parse_calls(html: str, region_path: str = "") -> list[dict]:
    """Parse all call blocks from a page."""
    soup = BeautifulSoup(html, "lxml")
    calls: list[dict] = []
    for div in soup.select("div.call"):
        title = _text(div.find("b", itemprop="name")) or "Geen titel"
        data: dict = {
            "priority_code": title,
            "title": title,
            "message": _text(div.find("pre")) or title,
            "region": region_path,
        }
        time_span = div.find(itemprop="startDate")
        data["raw_time_str"] = _text(time_span)
        iso = time_span.get("content") if time_span else None
        data["absolute_time_str"] = iso
        data["time"] = data["date"] = "Onbekend"
        if iso:
            try:
                dt = datetime.fromisoformat(iso)
                data["time"] = dt.strftime("%H:%M")
                data["date"] = dt.strftime("%Y-%m-%d")
            except ValueError:
                data["time"] = data["raw_time_str"] or "Onbekend"
        data["city"] = _text(div.find(itemprop="addressLocality")) or "Onbekend"
        data["postalcode"] = (
            _text(div.find(itemprop="postalCode")) or "Geen postcode beschikbaar"
        )
        data["address"] = _text(div.find(itemprop="streetAddress")) or "Onbekend"
        for key in ("latitude", "longitude"):
            try:
                data[key] = float(div.get(key))
            except (TypeError, ValueError):
                data[key] = None
        msg = data["message"].split()
        data["priority"] = (
            msg[0]
            if msg
            and re.match(
                r"^(A[012]|B[12]|P ?[123]|PRIO ?[123])$", msg[0], re.IGNORECASE
            )
            else None
        )
        loc = div.find(itemprop="location")
        data["region_name"] = _text(loc.find(itemprop="name")) if loc else None
        link = div.find("a", itemprop="url") or div.find("a", href=True)
        href = link["href"] if link else None
        if href and href.startswith("/"):
            href = BASE_URL.rstrip("/") + href
        if href and not re.match(r"^https?://", href.strip(), re.IGNORECASE):
            href = None
        data["url"] = href.strip() if href else None
        data["capcode"] = None  # not published by alarmfase1.nl anymore
        data["service_type"] = normalize_service(div.get("service"), title)
        calls.append(data)
    return calls


class Alarmfase1ApiClient:
    """Scraper API Client."""

    def __init__(self, session: ClientSession) -> None:
        self._session = session

    async def async_scrape_calls(self, region_path: str) -> list[dict]:
        """Return all calls on a region page (newest first)."""
        region_path = normalize_region_path(region_path)
        url = f"{BASE_URL}{region_path}/" if region_path else BASE_URL
        headers = {"User-Agent": "HomeAssistant P2000_Alarmfase1 Integration"}
        try:
            async with asyncio.timeout(API_TIMEOUT):
                response = await self._session.get(url, headers=headers)
                if response.status == 404:
                    raise ScraperApiNoDataError(f"Invalid region path (404): {url}")
                response.raise_for_status()
                html = await response.text()
        except ScraperApiNoDataError:
            raise
        except (ClientError, TimeoutError) as exc:
            raise ScraperApiConnectionError(f"Connection error with {url}") from exc
        try:
            return parse_calls(html, region_path)
        except Exception as exc:
            raise ScraperApiParsingError(f"Failed to parse HTML from {url}") from exc

    async def async_scrape_data(self, region_path: str) -> dict | None:
        """Backwards compatible: latest call only."""
        calls = await self.async_scrape_calls(region_path)
        return calls[0] if calls else None
