"""Persistent call history."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant

from custom_components.p2000_alarmfase1.cache import PersistentCache
from custom_components.p2000_alarmfase1.coordinator import (
    Alarmfase1DataUpdateCoordinator,
    merge_history,
)


def _call(minutes_ago: int, msg: str) -> dict:
    t = (datetime.now() - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M")
    return {"absolute_time_str": t, "message": msg, "title": msg}


def test_merge_dedupe_size_and_age():
    a, b, c = _call(1, "a"), _call(5, "b"), _call(3000, "old")
    merged = merge_history([a, b], [b, c], size=10, max_age_minutes=1440)
    # max age does not trim the persistent history (dedupe still applies)
    assert [x["message"] for x in merged] == ["a", "b", "old"]
    assert len(merge_history([a, b], [c], size=1)) == 1
    assert [x["message"] for x in merge_history([], [c], 10, 0)] == ["old"]
    # always keep the newest one even if everything is too old
    assert merge_history([], [c], 10, 60) == [c]


def _coord(hass, client, cache, initial=None, size=10):
    return Alarmfase1DataUpdateCoordinator(
        hass,
        name="t",
        client=client,
        region_path="limburg-zuid/kerkrade",
        update_interval=timedelta(seconds=60),
        cache=cache,
        initial_data=initial,
        history_size=size,
        max_age_minutes=0,
    )


async def test_history_survives_page_drop_and_restart(hass: HomeAssistant):
    cache = PersistentCache(hass, "p2000_test_history")
    client = AsyncMock()
    client.async_scrape_calls.return_value = [_call(10, "first"), _call(20, "second")]
    coord = _coord(hass, client, cache, size=3)
    await coord._async_update_data()

    # site page dropped the old messages, only a new one is visible
    client.async_scrape_calls.return_value = [_call(1, "new")]
    data = await coord._async_update_data()
    assert [c["message"] for c in data["calls"]] == ["new", "first", "second"]

    # restart: history comes back from storage and keeps merging (size limit 3)
    stored = await cache.load()
    client.async_scrape_calls.return_value = [_call(0, "newest")]
    coord2 = _coord(hass, client, cache, initial=stored, size=3)
    data = await coord2._async_update_data()
    assert [c["message"] for c in data["calls"]] == ["newest", "new", "first"]
    assert data["message"] == "newest"
