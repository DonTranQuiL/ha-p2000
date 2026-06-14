"""API Client for fetching P2000 messages from the Centralized API."""

import logging
import async_timeout
from aiohttp import ClientSession

from .const import CENTRAL_API_BASE_URL, API_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class ScraperApiError(Exception):
    pass


class ScraperApiConnectionError(ScraperApiError):
    pass


class ScraperApiParsingError(ScraperApiError):
    pass


class ScraperApiNoDataError(ScraperApiError):
    pass


class Alarmfase1ApiClient:
    """API Client communicating with the centralized P2000 FastAPI."""

    def __init__(self, session: ClientSession):
        self._session = session
        self._base_url = CENTRAL_API_BASE_URL

    async def async_scrape_data(self, region_path: str) -> dict | None:
        clean_region = region_path.strip("/")
        url = f"{self._base_url}{clean_region}"

        try:
            async with async_timeout.timeout(API_TIMEOUT):
                response = await self._session.get(url)

                # The FastAPI server returns 404 for invalid/empty regions
                if response.status == 404:
                    raise ScraperApiNoDataError(
                        f"Invalid region path (404): {region_path}"
                    )

                # Raise an exception for any other HTTP errors (500, 502)
                response.raise_for_status()

                # Fetch the JSON payload directly
                data = await response.json()

                # If the API returned empty data for some reason, handle it
                if not data:
                    return None

                return data

        except ScraperApiNoDataError:
            raise
        except Exception as exc:
            _LOGGER.error("Error communicating with centralized P2000 API: %s", exc)
            raise ScraperApiConnectionError(f"Connection error with {url}") from exc
