"""Test the KNMI Seismisch integration."""

from custom_components.p2000_alarmfase1.const import DOMAIN


async def test_domain_name():
    """A simple test to ensure pytest is running correctly."""
    assert DOMAIN == "p2000_alarmfase1"
