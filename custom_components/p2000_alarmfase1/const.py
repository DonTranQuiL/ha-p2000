"""Constants for the P2000 Scraper integration."""

from datetime import timedelta
from typing import Final

import homeassistant.helpers.config_validation as cv
import voluptuous as vol

DOMAIN: Final = "p2000_alarmfase1"
PLATFORMS: Final[list[str]] = ["sensor"]
MANUFACTURER: Final = "Malosaaa - alarmfase1.nl"

# Configuration Keys
CONF_REGION_PATH: Final = "region_path"
CONF_INSTANCE_NAME: Final = "instance_name"  # User-defined name for the device/instance
CONF_SENSORS: Final = "sensors"
CONF_FILTERS: Final = "filters"

CONF_FILTER_AMBULANCE: Final = "filter_ambulance"
CONF_FILTER_FIRE: Final = "filter_fire"
CONF_FILTER_POLICE: Final = "filter_police"
CONF_FILTER_OTHER: Final = "filter_other"  # KNRM, Traumaheli, etc.

CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_EXTRA_REGIONS: Final = "extra_regions"
CONF_MAX_CALLS: Final = "max_calls"
CONF_MAX_AGE: Final = "max_age_minutes"

DEFAULT_MAX_CALLS: Final = 25
DEFAULT_MAX_AGE: Final = 180  # minutes, 0 = no limit

# Normalised service types (site uses Dutch values in the `service` attribute)
SERVICE_AMBULANCE: Final = "Ambulance"
SERVICE_FIRE: Final = "Fire Department"
SERVICE_POLICE: Final = "Police"
SERVICE_HELI: Final = "Trauma Heli"
SERVICE_KNRM: Final = "KNRM / Water Rescue"
SERVICE_NAME_MAP: Final[dict[str, str]] = {
    "ambulance": SERVICE_AMBULANCE,
    "brandweer": SERVICE_FIRE,
    "politie": SERVICE_POLICE,
    "knrm": SERVICE_KNRM,
    "traumaheli": SERVICE_HELI,
    "lifeliner": SERVICE_HELI,
}

DEFAULT_SCAN_INTERVAL: Final = 120  # seconds
MIN_SCAN_INTERVAL: Final = 30  # seconds

# API Details
BASE_URL: Final = "https://www.alarmfase1.nl/"
API_TIMEOUT: Final = 20

# Update Interval
DEFAULT_UPDATE_INTERVAL: Final = timedelta(seconds=90)

# Data Keys from scraping (used for sensor selection and attributes)
# These should match the keys returned by the api.py parser
SCRAPED_DATA_KEYS: Final[list[str]] = [
    "priority_code",  # Main sensor state
    "title",
    "message",
    "time",
    "date",
    "city",
    "address",
    "postalcode",
    "capcode",  # <-- FIX ADDED
    "latitude",
    "longitude",
    "service_type",
    "raw_time_str",
    "absolute_time_str",
    "region",
    "url",
    "priority",
    "region_name",
]

# Default sensor selection (enabled by default)
DEFAULT_ENABLED_SENSORS: Final[list[str]] = [
    "priority_code",
    "title",
    "message",
    "time",
    "date",
    "city",
    "address",
    "postalcode",
    "capcode",  # <-- FIX ADDED
    "service_type",
    "latitude",
    "longitude",
    "priority",
    "region",
    "region_name",
    "url",
]

# Sensor configuration schema used in config flow options
SENSOR_SCHEMA = vol.Schema(
    {
        vol.Optional(
            key,
            default=(key in DEFAULT_ENABLED_SENSORS),
        ): cv.boolean
        for key in SCRAPED_DATA_KEYS
    }
)

# Filter configuration schema used in config flow options
FILTER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_FILTER_AMBULANCE, default=True): cv.boolean,
        vol.Optional(CONF_FILTER_FIRE, default=True): cv.boolean,
        vol.Optional(CONF_FILTER_POLICE, default=True): cv.boolean,
        vol.Optional(CONF_FILTER_OTHER, default=True): cv.boolean,
    }
)

# Mapping from icon fragments to service types
SERVICE_TYPE_ICON_MAP: Final[dict[str, str]] = {
    "ambulance": "Ambulance",
    "fire-extinguisher": "Fire Department",
    "helicopter": "Trauma Heli",
    "life-ring": "KNRM / Water Rescue",
}

DEFAULT_SERVICE_TYPE: Final = "Other"

# Diagnostics
DIAG_CONFIG_ENTRY = "config_entry"
DIAG_OPTIONS = "options"
DIAG_COORDINATOR_DATA = "coordinator_data"
