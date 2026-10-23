"""Parser and options-flow tests."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries, data_entry_flow
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.p2000_alarmfase1.api import (
    normalize_region_path,
    normalize_service,
    parse_calls,
)
from custom_components.p2000_alarmfase1.const import (
    CONF_EXTRA_REGIONS,
    CONF_INSTANCE_NAME,
    CONF_REGION_PATH,
    DOMAIN,
)

HTML = (Path(__file__).parent / "fixtures" / "kerkrade.html").read_text()


def test_parse_calls():
    calls = parse_calls(HTML, "limburg-zuid/kerkrade")
    assert len(calls) > 10
    c = calls[0]
    assert c["service_type"] == "Fire Department"
    assert c["latitude"] and c["longitude"]
    assert c["url"].startswith("https://www.alarmfase1.nl/")
    assert c["city"] == "Kerkrade"
    assert c["region_name"] == "Limburg Zuid"
    assert c["priority"] == "P2"


@pytest.mark.parametrize(
    ("raw", "exp"),
    [
        ("Brandweer", "Fire Department"),
        ("Politie", "Police"),
        ("Ambulance", "Ambulance"),
    ],
)
def test_normalize_service(raw, exp):
    assert normalize_service(raw) == exp


def test_normalize_service_heli():
    assert normalize_service("Ambulance", "Traumaheli naar Maastricht") == "Trauma Heli"


def test_normalize_region_path():
    assert (
        normalize_region_path("https://www.alarmfase1.nl/Brabant-Noord/gemert/")
        == "brabant-noord/gemert"
    )
    assert normalize_region_path(" /limburg-zuid/ ") == "limburg-zuid"


async def test_options_flow_loads_and_saves(hass):
    """Regression: cogwheel gave 500 because the handler set self.config_entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="P2000 Kerkrade",
        data={
            CONF_INSTANCE_NAME: "P2000 Kerkrade",
            CONF_REGION_PATH: "limburg-zuid/kerkrade",
        },
        options={},
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.p2000_alarmfase1.config_flow.validate_input",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.p2000_alarmfase1.async_setup_entry", return_value=True
        ),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_EXTRA_REGIONS: [
                    "brabant-noord/gemert",
                    "https://www.alarmfase1.nl/drenthe/",
                ],
                "scan_interval": 60,
                "max_calls": 20,
                "max_age_minutes": 120,
            },
        )
        assert result["step_id"] == "sensors"
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {}
        )
        assert result["step_id"] == "filters"
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {}
        )
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_EXTRA_REGIONS] == ["brabant-noord/gemert", "drenthe"]
    assert entry.options["scan_interval"] == 60


async def test_user_flow(hass):
    with (
        patch(
            "custom_components.p2000_alarmfase1.config_flow.validate_input",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.p2000_alarmfase1.async_setup_entry", return_value=True
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_INSTANCE_NAME: "Test", CONF_REGION_PATH: "/Limburg-Zuid/Kerkrade/"},
        )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_REGION_PATH] == "limburg-zuid/kerkrade"
