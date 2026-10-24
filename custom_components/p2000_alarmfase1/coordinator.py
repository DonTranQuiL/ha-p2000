"""DataUpdateCoordinator for P2000 Scraper."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ScraperApiError

_LOGGER = logging.getLogger(__name__)


def _sort_key(call: dict) -> str:
    return call.get("absolute_time_str") or ""


def _call_key(call: dict) -> tuple:
    return (call.get("absolute_time_str"), call.get("message"))


def merge_history(
    fresh: list[dict], history: list[dict], size: int, max_age_minutes: int = 0
) -> list[dict]:
    """Merge newly scraped calls with the stored history (dedupe, newest first).

    Fresh calls win over stored copies. Calls older than ``max_age_minutes``
    are dropped (0 = no limit), but the newest call is always kept.
    """
    seen: set = set()
    merged: list[dict] = []
    for c in sorted([*fresh, *history], key=_sort_key, reverse=True):
        k = _call_key(c)
        if k in seen:
            continue
        seen.add(k)
        merged.append(c)
    if max_age_minutes:
        cutoff = (datetime.now() - timedelta(minutes=max_age_minutes)).strftime(
            "%Y-%m-%dT%H:%M"
        )
        recent = [c for c in merged if (c.get("absolute_time_str") or "9") >= cutoff]
        # Max age only limits *new* scrapes; the stored history is always kept
        # up to ``size`` so the map can show the last N messages.
        if len(recent) < size:
            recent = merged
        merged = recent
    return merged[:size]


class Alarmfase1DataUpdateCoordinator(DataUpdateCoordinator):
    """Fetch P2000 data for one or more regions.

    ``data`` is the latest call dict, plus ``calls`` (merged list, newest first)
    and ``regions``.
    """

    def __init__(
        self,
        hass,
        name,
        client,
        region_path,
        update_interval,
        cache=None,
        initial_data=None,
        extra_regions=None,
        max_calls: int = 25,
        max_age_minutes: int = 0,
        config_entry=None,
        geocoder=None,
        history_size: int = 10,
    ):
        self.client = client
        self.region_path = region_path
        self.regions = [
            region_path,
            *[r for r in (extra_regions or []) if r and r != region_path],
        ]
        self.max_calls = max_calls
        self.max_age_minutes = max_age_minutes
        self.cache = cache
        self.geocoder = geocoder
        self.history_size = max(1, min(50, int(history_size)))
        self.last_data = initial_data
        self._error_count = 0
        self._last_update_error = False
        self.last_update_success_timestamp = (
            datetime.now().isoformat() if initial_data else None
        )
        kwargs = {"config_entry": config_entry} if config_entry is not None else {}
        super().__init__(
            hass, _LOGGER, name=name, update_interval=update_interval, **kwargs
        )
        self.data = initial_data

    async def _async_update_data(self):
        results = await asyncio.gather(
            *(self.client.async_scrape_calls(r) for r in self.regions),
            return_exceptions=True,
        )
        calls: list[dict] = []
        errors = []
        for region, res in zip(self.regions, results):
            if isinstance(res, Exception):
                errors.append(f"{region}: {res}")
                continue
            calls.extend(res)

        if errors and len(errors) == len(self.regions):
            self._error_count += 1
            self._last_update_error = True
            _LOGGER.warning("Update failed, using last known data: %s", errors)
            if self.last_data:
                return self.last_data
            raise UpdateFailed(f"Error fetching P2000 data: {errors}")
        for err in errors:
            _LOGGER.warning("P2000 region failed: %s", err)

        fresh = sorted(calls, key=_sort_key, reverse=True)[: self.max_calls]
        if self.geocoder is not None:
            try:
                await self.geocoder.fill_missing(fresh)
            except Exception as err:
                _LOGGER.debug("Geocoding fallback failed: %s", err)
        unique = merge_history(
            fresh,
            (self.last_data or {}).get("calls") or [],
            self.history_size,
            self.max_age_minutes,
        )
        self._error_count = 0
        self._last_update_error = bool(errors)
        if not unique:
            return self.last_data
        data = {**unique[0], "calls": unique, "regions": self.regions}
        self.last_data = data
        self.last_update_success_timestamp = datetime.now().isoformat()
        if self.cache:
            await self.cache.save(data)
        return data

    @property
    def error_count(self) -> int:
        return self._error_count

    @property
    def last_update_error(self) -> bool:
        return self._last_update_error


__all__ = ["Alarmfase1DataUpdateCoordinator", "ScraperApiError"]
