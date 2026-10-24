"""Server-side fallback geocoding for calls without coordinates (OSM Nominatim)."""

from __future__ import annotations

import asyncio
import logging
import re
import time

from aiohttp import ClientError, ClientSession

_LOGGER = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = (
    "HomeAssistant-P2000-Alarmfase1/2.1.8 (+https://github.com/DonTranQuiL/ha-p2000)"
)
MIN_INTERVAL = 1.1  # Nominatim usage policy: max 1 request per second
MAX_LOOKUPS_PER_UPDATE = 5
UNKNOWN = {"", "onbekend", "geen postcode beschikbaar", "none"}


def _clean(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return None if text.lower() in UNKNOWN else text


_PC = re.compile(r"\b([1-9]\d{3})\s?([A-Z]{2})\b")


def postcode(value) -> str | None:
    """Return a normalised Dutch postal code ('6461 AA') found in value."""
    m = _PC.search(str(value or "").upper())
    return f"{m.group(1)} {m.group(2)}" if m else None


class Geocoder:
    """Rate-limited, cached Nominatim lookups shared by all entries."""

    def __init__(self, session: ClientSession, store=None) -> None:
        self._session = session
        self._store = store
        self._cache: dict[str, list[float] | None] = {}
        self._loaded = store is None
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        try:
            data = await self._store.async_load()
            if isinstance(data, dict):
                self._cache.update(data)
        except Exception as err:
            _LOGGER.debug("Geocode cache load failed: %s", err)

    def cached(self, query: str) -> tuple[bool, list[float] | None]:
        key = query.lower()
        return (key in self._cache, self._cache.get(key))

    async def lookup(self, query: str) -> list[float] | None:
        """Return [lat, lon] for a query (cached; None if not found)."""
        await self._ensure_loaded()
        key = query.lower()
        if key in self._cache:
            return self._cache[key]
        async with self._lock:
            if key in self._cache:
                return self._cache[key]
            wait = MIN_INTERVAL - (time.monotonic() - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()
            params = {
                "q": query,
                "format": "jsonv2",
                "limit": "1",
                "countrycodes": "nl",
            }
            try:
                async with asyncio.timeout(10):
                    resp = await self._session.get(
                        NOMINATIM_URL,
                        params=params,
                        headers={"User-Agent": USER_AGENT, "Accept-Language": "nl"},
                    )
                    if resp.status != 200:
                        _LOGGER.debug("Nominatim %s for %s", resp.status, query)
                        return None  # transient: don't cache
                    rows = await resp.json(content_type=None)
            except (ClientError, TimeoutError, ValueError) as err:
                _LOGGER.debug("Nominatim error for %s: %s", query, err)
                return None
            result = None
            if rows:
                try:
                    result = [float(rows[0]["lat"]), float(rows[0]["lon"])]
                except (KeyError, TypeError, ValueError):
                    result = None
            self._cache[key] = result
            if self._store is not None:
                self._store.async_delay_save(lambda: dict(self._cache), 30)
            return result

    async def fill_missing(self, calls: list[dict]) -> None:
        """Give calls without coordinates a position (in place).

        Order: scraped lat/lon -> street address (+ town) -> Dutch postal code
        (e.g. ``6461 AA``). Geocoded positions get ``approx: True`` and
        ``location_source`` ("address" / "postcode"). Calls with none of these
        keep latitude/longitude None: list only, not on the map.
        """
        budget = MAX_LOOKUPS_PER_UPDATE
        await self._ensure_loaded()
        for call in calls:
            if call.get("latitude") is not None and call.get("longitude") is not None:
                call["approx"] = False
                call["location_source"] = "scraped"
                continue
            call["approx"] = False
            call["location_source"] = None
            town = _clean(call.get("city"))
            street = _clean(call.get("address"))
            candidates = []
            if street:
                candidates.append(
                    (
                        f"{street}, {town}, Nederland"
                        if town
                        else f"{street}, Nederland",
                        "address",
                    )
                )
            pc = postcode(call.get("postalcode")) or postcode(call.get("message"))
            if pc:
                candidates.append((f"{pc}, Nederland", "postcode"))
            for query, source in candidates:
                hit, value = self.cached(query)
                if not hit:
                    if budget <= 0:
                        continue
                    budget -= 1
                    value = await self.lookup(query)
                if value:
                    call["latitude"], call["longitude"] = value
                    call["approx"] = True
                    call["location_source"] = source
                    break
