"""Tests for the P2000 Scraper sensor platform."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.p2000_alarmfase1.const import DOMAIN, CONF_INSTANCE_NAME, CONF_FILTERS, CONF_FILTER_AMBULANCE
from custom_components.p2000_alarmfase1.sensor import P2000Sensor, P2000DiagnosticSensor


@pytest.fixture
def mock_coordinator():
    """Create a mock DataUpdateCoordinator filled with predictable testing data."""
    coordinator = MagicMock()
    
    config_entry = MagicMock()
    config_entry.data = {CONF_INSTANCE_NAME: "P2000 Test"}
    config_entry.options = {
        CONF_FILTERS: {CONF_FILTER_AMBULANCE: True}
    }
    
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
    
    # FIX: Explicitly set an entity_id so async_write_ha_state doesn't crash
    sensor.entity_id = "sensor.p2000_test_latest_message"

    # Manually trigger the internal logic that reads coordinator data
    sensor._handle_coordinator_update()

    # 1. Test state parsing
    assert sensor.state == "A1"

    # 2. Test dynamic icon assignment for Ambulances
    assert sensor.icon == "mdi:ambulance"

    # 3. Test that extra state attributes are populated correctly
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
    
    # FIX: Explicitly set an entity_id so async_write_ha_state doesn't crash
    sensor.entity_id = "sensor.p2000_test_latest_message"

    # Change the coordinator data to a service type that doesn't match our filter configuration
    mock_coordinator.config_entry.options = {
        CONF_FILTERS: {CONF_FILTER_AMBULANCE: False} # Turn off ambulance notifications
    }
    
    sensor._handle_coordinator_update()
    
    # Verify the internal filter logic returns False
    assert sensor._message_matches_filter is False


@pytest.mark.asyncio
async def test_p2000_diagnostic_sensors(hass: HomeAssistant, mock_coordinator):
    """Test that diagnostic sensors correctly display system health and localized dates."""
    status_sensor = P2000DiagnosticSensor(mock_coordinator, "status", "Status", "mdi:check-network")
    update_sensor = P2000DiagnosticSensor(mock_coordinator, "last_update", "Laatste Update", "mdi:clock")

    # 1. Test status sensor under normal conditions
    assert status_sensor.native_value == "OK"

    # 2. Test status sensor when an error is occurring
    mock_coordinator.last_update_error = "Connection Timeout"
    mock_coordinator.error_count = 3
    assert status_sensor.native_value == "Fout (3 mislukt)"

    # 3. FIX: Check string directly against UTC runner environment time values
    assert update_sensor.native_value == "18-05-2026 15:30:00"
