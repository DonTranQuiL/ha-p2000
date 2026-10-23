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

        seen = set()
        unique = []
        for c in sorted(calls, key=_sort_key, reverse=True):
            k = (c.get("absolute_time_str"), c.get("message"))
            if k in seen:
                continue
            seen.add(k)
            unique.append(c)
        if self.max_age_minutes:
            cutoff = (
                datetime.now() - timedelta(minutes=self.max_age_minutes)
            ).strftime("%Y-%m-%dT%H:%M")
            unique = [
                c for c in unique if (c.get("absolute_time_str") or "9") >= cutoff
            ] or unique[:1]
        unique = unique[: self.max_calls]

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
