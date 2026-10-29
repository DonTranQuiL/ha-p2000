"""The P2000 Scraper (alarmfase1.nl) integration."""

from __future__ import annotations

import logging
import os
from datetime import timedelta

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .api import Alarmfase1ApiClient
from .cache import PersistentCache
from .const import (
    CONF_EXTRA_REGIONS,
    CONF_HISTORY_SIZE,
    CONF_MAX_AGE,
    CONF_MAX_CALLS,
    CONF_REGION_PATH,
    CONF_SCAN_INTERVAL,
    DEFAULT_HISTORY_SIZE,
    DEFAULT_MAX_AGE,
    DEFAULT_MAX_CALLS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import Alarmfase1DataUpdateCoordinator
from .geocode import Geocoder

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
CARD_URL_BASE = f"/{DOMAIN}"
CARD_FILE = "p2000-map-card.js"
CARD_VERSION = "2.1.12"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the bundled map card and global services."""
    hass.data.setdefault(DOMAIN, {})
    www = os.path.join(os.path.dirname(__file__), "www")
    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_URL_BASE, www, True)]
        )
        from homeassistant.components.frontend import add_extra_js_url

        add_extra_js_url(hass, f"{CARD_URL_BASE}/{CARD_FILE}?v={CARD_VERSION}")
    except Exception as err:
        _LOGGER.warning("Could not register P2000 map card: %s", err)

    def _coordinators():
        return [
            c
            for c in hass.data.get(DOMAIN, {}).values()
            if isinstance(c, Alarmfase1DataUpdateCoordinator)
        ]

    async def handle_manual_refresh(call: ServiceCall) -> None:
        for c in _coordinators():
            await c.async_request_refresh()

    async def handle_clear_cache(call: ServiceCall) -> None:
        for c in _coordinators():
            if c.cache:
                await c.cache.clear()

    async def handle_clear_debug(call: ServiceCall) -> None:
        path = os.path.join(os.path.dirname(__file__), "p2000_debug.txt")
        await hass.async_add_executor_job(
            lambda: os.path.exists(path) and os.remove(path)
        )

    hass.services.async_register(DOMAIN, "manual_refresh", handle_manual_refresh)
    hass.services.async_register(DOMAIN, "clear_cache", handle_clear_cache)
    hass.services.async_register(DOMAIN, "clear_debug_file", handle_clear_debug)
    return True


def _geocoder(hass: HomeAssistant) -> Geocoder:
    """One shared, rate-limited Nominatim geocoder with a persistent cache."""
    data = hass.data.setdefault(DOMAIN, {})
    if "_geocoder" not in data:
        data["_geocoder"] = Geocoder(
            async_get_clientsession(hass), Store(hass, 1, f"{DOMAIN}_geocode_cache")
        )
    return data["_geocoder"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up P2000 Scraper from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    cache = PersistentCache(hass, f"{DOMAIN}_{entry.entry_id}")
    initial_data = await cache.load()
    opts = entry.options

    coordinator = Alarmfase1DataUpdateCoordinator(
        hass=hass,
        name=f"P2000 Coordinator {entry.title}",
        client=Alarmfase1ApiClient(async_get_clientsession(hass)),
        region_path=entry.data[CONF_REGION_PATH],
        update_interval=timedelta(
            seconds=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        ),
        cache=cache,
        initial_data=initial_data,
        extra_regions=opts.get(CONF_EXTRA_REGIONS, []),
        max_calls=int(opts.get(CONF_MAX_CALLS, DEFAULT_MAX_CALLS)),
        max_age_minutes=int(opts.get(CONF_MAX_AGE, DEFAULT_MAX_AGE)),
        history_size=int(opts.get(CONF_HISTORY_SIZE, DEFAULT_HISTORY_SIZE)),
        config_entry=entry,
        geocoder=_geocoder(hass),
    )
    coordinator.config_entry = entry

    if initial_data:
        coordinator.async_set_updated_data(initial_data)
        # refresh in background so new regions show up quickly
        entry.async_create_background_task(
            hass, coordinator.async_refresh(), f"{DOMAIN}_initial_refresh"
        )
    else:
        await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload on options change."""
    await hass.config_entries.async_reload(entry.entry_id)
