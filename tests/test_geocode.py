"""Tests for the server-side geocoding fallback."""

from unittest.mock import AsyncMock

import pytest

from custom_components.p2000_alarmfase1 import geocode
from custom_components.p2000_alarmfase1.geocode import Geocoder, postcode


def test_postcode():
    assert postcode("6461aa") == "6461 AA"
    assert postcode("A1 Markt 6461 AB Kerkrade") == "6461 AB"
    assert postcode("Geen postcode beschikbaar") is None


@pytest.mark.asyncio
async def test_fill_missing_order(monkeypatch):
    monkeypatch.setattr(geocode, "MIN_INTERVAL", 0)
    g = Geocoder(session=None)
    seen = []

    async def fake(query):
        seen.append(query)
        if query.startswith("Markt"):
            return None
        return [50.86, 6.06]

    g.lookup = AsyncMock(side_effect=fake)
    calls = [
        {"latitude": 1.0, "longitude": 2.0},
        {"address": "Markt", "city": "Kerkrade", "postalcode": "6461 AA"},
        {
            "address": "Onbekend",
            "city": "Kerkrade",
            "postalcode": "Geen postcode beschikbaar",
            "message": "P 1 BR",
        },
        {"address": "Hoofdstraat 1", "city": "Heerlen"},
    ]
    await g.fill_missing(calls)
    assert calls[0]["approx"] is False and calls[0]["location_source"] == "scraped"
    assert calls[1]["location_source"] == "postcode" and calls[1]["approx"] is True
    assert calls[2]["latitude"] is None if "latitude" in calls[2] else True
    assert calls[2]["location_source"] is None
    assert calls[3]["location_source"] == "address"
    assert seen == [
        "Markt, Kerkrade, Nederland",
        "6461 AA, Nederland",
        "Hoofdstraat 1, Heerlen, Nederland",
    ]


@pytest.mark.asyncio
async def test_lookup_budget(monkeypatch):
    g = Geocoder(session=None)
    g.lookup = AsyncMock(return_value=None)
    calls = [{"address": f"Straat {i}", "city": "X"} for i in range(10)]
    await g.fill_missing(calls)
    assert g.lookup.await_count == geocode.MAX_LOOKUPS_PER_UPDATE
