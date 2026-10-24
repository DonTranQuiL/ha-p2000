"""Config flow for P2000 Scraper."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    Alarmfase1ApiClient,
    ScraperApiConnectionError,
    ScraperApiError,
    ScraperApiNoDataError,
    ScraperApiParsingError,
    normalize_region_path,
)
from .const import (
    CONF_EXTRA_REGIONS,
    CONF_FILTERS,
    CONF_HISTORY_SIZE,
    CONF_INSTANCE_NAME,
    CONF_MAX_AGE,
    CONF_MAX_CALLS,
    CONF_REGION_PATH,
    CONF_SCAN_INTERVAL,
    CONF_SENSORS,
    DEFAULT_HISTORY_SIZE,
    DEFAULT_MAX_AGE,
    DEFAULT_MAX_CALLS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    FILTER_SCHEMA,
    MIN_SCAN_INTERVAL,
    SENSOR_SCHEMA,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_INSTANCE_NAME): str,
        vol.Required(CONF_REGION_PATH): str,
    }
)


async def validate_input(hass, region_path: str) -> None:
    """Validate that the region page can be fetched and parsed."""
    client = Alarmfase1ApiClient(async_get_clientsession(hass))
    await client.async_scrape_calls(region_path)


def _error_key(exc: Exception) -> str:
    if isinstance(exc, ScraperApiNoDataError):
        return "invalid_region_path"
    if isinstance(exc, ScraperApiConnectionError):
        return "cannot_connect"
    if isinstance(exc, ScraperApiParsingError):
        return "parse_error"
    if isinstance(exc, ScraperApiError):
        return "unknown_api_error"
    return "unknown"


class P2000ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for P2000 Scraper."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            region = normalize_region_path(user_input[CONF_REGION_PATH])
            await self.async_set_unique_id(region)
            self._abort_if_unique_id_configured()
            try:
                await validate_input(self.hass, region)
            except Exception as exc:
                key = _error_key(exc)
                if key == "unknown":
                    _LOGGER.exception("Unexpected exception during validation")
                errors[CONF_REGION_PATH if key == "invalid_region_path" else "base"] = (
                    key
                )
            else:
                return self.async_create_entry(
                    title=user_input[CONF_INSTANCE_NAME],
                    data={**user_input, CONF_REGION_PATH: region},
                    options={},
                )
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow (HA provides self.config_entry itself)."""
        return P2000OptionsFlowHandler()


class P2000OptionsFlowHandler(config_entries.OptionsFlow):
    """Options: regions + interval -> sensors -> filters.

    NOTE: Do not assign self.config_entry; since HA 2025.12 that raises and
    produced the '500 Internal Server Error' on the cogwheel.
    """

    def __init__(self) -> None:
        self._options: dict[str, Any] = {}

    def _placeholders(self) -> dict[str, str]:
        return {
            "instance_name": self.config_entry.title,
            "region_path": self.config_entry.data.get(CONF_REGION_PATH, ""),
        }

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Regions and polling."""
        if not self._options:
            self._options = dict(self.config_entry.options)
        errors: dict[str, str] = {}
        if user_input is not None:
            regions: list[str] = []
            primary = self.config_entry.data.get(CONF_REGION_PATH)
            for raw in user_input.get(CONF_EXTRA_REGIONS, []) or []:
                for part in str(raw).replace(";", ",").split(","):
                    r = normalize_region_path(part)
                    if r and r != primary and r not in regions:
                        regions.append(r)
            old = set(self._options.get(CONF_EXTRA_REGIONS, []))
            for r in regions:
                if r in old:
                    continue
                try:
                    await validate_input(self.hass, r)
                except Exception as exc:
                    errors[CONF_EXTRA_REGIONS] = _error_key(exc)
                    _LOGGER.warning("Region %s rejected: %s", r, exc)
                    break
            interval = int(user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
            if interval < MIN_SCAN_INTERVAL:
                errors[CONF_SCAN_INTERVAL] = "interval_too_short"
            if not errors:
                self._options[CONF_EXTRA_REGIONS] = regions
                self._options[CONF_SCAN_INTERVAL] = interval
                self._options[CONF_MAX_CALLS] = int(
                    user_input.get(CONF_MAX_CALLS, DEFAULT_MAX_CALLS)
                )
                self._options[CONF_MAX_AGE] = int(
                    user_input.get(CONF_MAX_AGE, DEFAULT_MAX_AGE)
                )
                self._options[CONF_HISTORY_SIZE] = int(
                    user_input.get(CONF_HISTORY_SIZE, DEFAULT_HISTORY_SIZE)
                )
                return await self.async_step_sensors()

        o = self._options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_EXTRA_REGIONS, default=o.get(CONF_EXTRA_REGIONS, [])
                ): selector.TextSelector(selector.TextSelectorConfig(multiple=True)),
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=o.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL,
                        max=3600,
                        step=10,
                        unit_of_measurement="s",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_MAX_CALLS, default=o.get(CONF_MAX_CALLS, DEFAULT_MAX_CALLS)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=100, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Required(
                    CONF_HISTORY_SIZE,
                    default=o.get(CONF_HISTORY_SIZE, DEFAULT_HISTORY_SIZE),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=50, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Required(
                    CONF_MAX_AGE, default=o.get(CONF_MAX_AGE, DEFAULT_MAX_AGE)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=10080,
                        step=10,
                        unit_of_measurement="min",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders=self._placeholders(),
        )

    async def async_step_sensors(self, user_input: dict[str, Any] | None = None):
        """Attribute selection."""
        if user_input is not None:
            self._options[CONF_SENSORS] = user_input
            return await self.async_step_filters()
        schema = self.add_suggested_values_to_schema(
            SENSOR_SCHEMA, self._options.get(CONF_SENSORS) or {}
        )
        return self.async_show_form(
            step_id="sensors",
            data_schema=schema,
            description_placeholders=self._placeholders(),
        )

    async def async_step_filters(self, user_input: dict[str, Any] | None = None):
        """Service filters."""
        if user_input is not None:
            self._options[CONF_FILTERS] = user_input
            return self.async_create_entry(title="", data=self._options)
        schema = self.add_suggested_values_to_schema(
            FILTER_SCHEMA, self._options.get(CONF_FILTERS) or {}
        )
        return self.async_show_form(
            step_id="filters",
            data_schema=schema,
            description_placeholders=self._placeholders(),
        )
