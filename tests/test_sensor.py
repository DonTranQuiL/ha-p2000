"""Tests for the P2000 Scraper sensor platform."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.p2000_alarmfase1.const import (
    DOMAIN,
    CONF_INSTANCE_NAME,
    CONF_FILTERS,
    CONF_FILTER_AMBULANCE,
    CONF_SENSORS,
)
from custom_components.p2000_alarmfase1.sensor import P2000Sensor, P2000DiagnosticSensor


@pytest.fixture
def mock_coordinator():
    """Create a mock DataUpdateCoordinator filled with predictable testing data."""
    coordinator = MagicMock()
    
    config_entry = MagicMock()
    config_entry.data = {CONF_INSTANCE_NAME: "P2000 Test"}
    
    # Foolproof option mock: intercept .get() calls to ensure keys are always enabled
    def mock_get(key, default=None):
        if key == CONF_FILTERS:
            return {CONF_FILTER_AMBULANCE: True}
        if key == CONF_SENSORS:
            # A custom dictionary type that returns True for any key lookups
            class DefaultTrueDict(dict):
                def get(self, k, d=None):
                    return True
            return DefaultTrueDict()
        return default

    config_entry.options.get.side_effect = mock_get
    
    coordinator.config_entry = config_entry
    coordinator.last_update_error = None
    coordinator.error_count = 0
    coordinator.last_update_success_timestamp = "2026-05-18T15:30:00+00:00"
    
    coordinator.data = {
        "priority_code": "A1",
        "service_type": "Ambulance",
        "message": "A1 AMBU 24134 Urgent medical call Kanariestraat",
        "region": "Limburg Zuid (Kerkrade)",
        "capcode": "000883210",
        "latitude": 50.865,
        "longitude": 6.062,
        "timestamp": datetime(2026, 5, 18, 15, 30, 0, tzinfo=dt_util.UTC),
    }
    
    return coordinator


@pytest.mark.asyncio
async def test_p2000_sensor_state_and_attributes(hass: HomeAssistant, mock_coordinator):
    """Test that the main P2000 sensor reads state, attributes, and icons correctly from the coordinator."""
    sensor = P2000Sensor(mock_coordinator)
    sensor.hass = hass
    
    sensor.entity_id = "sensor.p2000_test_latest_message"

    sensor._handle_coordinator_update()

    assert sensor.state == "A1"
    assert sensor.icon == "mdi:ambulance"

    attrs = sensor.extra_state_attributes
    assert attrs is not None
    assert attrs["service_type"] == "Ambulance"
    assert attrs["capcode"] == "000883210"
    assert attrs["latitude"] == 50.865
    assert attrs["matches_filter"] is True


@pytest.mark.asyncio
async def test_p2000_sensor_filtering(hass: HomeAssistant, mock_coordinator):
    """Test that messages not matching the user's filters are ignored or flagged."""
    sensor = P2000Sensor(mock_coordinator)
    sensor.hass = hass
    
    sensor.entity_id = "sensor.p2000_test_latest_message"

    # Override options explicitly for the filter testing branch
    mock_coordinator.config_entry.options = {
        CONF_FILTERS: {CONF_FILTER_AMBULANCE: False}
    }
    
    sensor._handle_coordinator_update()
    
    assert sensor._message_matches_filter is False


@pytest.mark.asyncio
async def test_p2000_diagnostic_sensors(hass: HomeAssistant, mock_coordinator):
    """Test that diagnostic sensors correctly display system health and localized dates."""
    status_sensor = P2000DiagnosticSensor(mock_coordinator, "status", "Status", "mdi:check-network")
    update_sensor = P2000DiagnosticSensor(mock_coordinator, "last_update", "Laatste Update", "mdi:clock")

    assert status_sensor.native_value == "OK"

    mock_coordinator.last_update_error = "Connection Timeout"
    mock_coordinator.error_count = 3
    assert status_sensor.native_value == "Fout (3 mislukt)"

    assert update_sensor.native_value == "18-05-2026 15:30:00"
