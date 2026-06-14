"""Constants for the P2000 Scraper integration."""

from typing import Final
from datetime import timedelta

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

DOMAIN: Final = "p2000_alarmfase1"
PLATFORMS: Final[list[str]] = ["sensor"]
MANUFACTURER: Final = "Malosaaa - alarmfase1.nl"

# Configuration Keys
CONF_REGION_PATH: Final = "region_path"
CONF_INSTANCE_NAME: Final = "instance_name"
CONF_SENSORS: Final = "sensors"
CONF_FILTERS: Final = "filters"

CONF_FILTER_AMBULANCE: Final = "filter_ambulance"
CONF_FILTER_FIRE: Final = "filter_fire"
CONF_FILTER_POLICE: Final = "filter_police"
CONF_FILTER_OTHER: Final = "filter_other"

CONF_SCAN_INTERVAL: Final = "scan_interval"

DEFAULT_SCAN_INTERVAL: Final = 120
MIN_SCAN_INTERVAL: Final = 30

# --- NEW CENTRAL API DETAILS ---
# Replace this IP with the actual IP/domain of your hosted FastAPI container
CENTRAL_API_BASE_URL: Final = "https://p2000-api.onrender.com/api/p2000/"
API_TIMEOUT: Final = 15

DEFAULT_UPDATE_INTERVAL: Final = timedelta(seconds=90)

SCRAPED_DATA_KEYS: Final[list[str]] = [
    "priority_code",
    "title",
    "message",
    "time",
    "date",
    "city",
    "address",
    "postalcode",
    "capcode",
    "latitude",
    "longitude",
    "service_type",
    "raw_time_str",
    "absolute_time_str",
]

DEFAULT_ENABLED_SENSORS: Final[list[str]] = [
    "priority_code",
    "title",
    "message",
    "time",
    "date",
    "city",
    "address",
    "postalcode",
    "capcode",
    "service_type",
    "latitude",
    "longitude",
]

SENSOR_SCHEMA = vol.Schema(
    {
        vol.Optional(
            key,
            default=(key in DEFAULT_ENABLED_SENSORS),
        ): cv.boolean
        for key in SCRAPED_DATA_KEYS
    }
)

FILTER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_FILTER_AMBULANCE, default=True): cv.boolean,
        vol.Optional(CONF_FILTER_FIRE, default=True): cv.boolean,
        vol.Optional(CONF_FILTER_POLICE, default=True): cv.boolean,
        vol.Optional(CONF_FILTER_OTHER, default=True): cv.boolean,
    }
)

SERVICE_TYPE_ICON_MAP: Final[dict[str, str]] = {
    "ambulance": "Ambulance",
    "fire-extinguisher": "Fire Department",
    "helicopter": "Trauma Heli",
    "life-ring": "KNRM / Water Rescue",
}

DEFAULT_SERVICE_TYPE: Final = "Other"

DIAG_CONFIG_ENTRY = "config_entry"
DIAG_OPTIONS = "options"
DIAG_COORDINATOR_DATA = "coordinator_data"