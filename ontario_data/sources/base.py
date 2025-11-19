"""Base client for all Ontario data sources."""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List

import aiohttp

logger = logging.getLogger(__name__)


class DataSourceError(Exception):
    """Custom exception for data source errors."""

    pass


class BaseClient(ABC):
    """Abstract base client with common functionality for all data sources.

    Provides:
    - Rate limiting
    - Retry logic with exponential backoff
    - Error handling
    - Logging
    """

    def __init__(
        self,
        rate_limit: int = 60,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ):
        """Initialize base client.

        Args:
            rate_limit: Maximum requests per minute
            max_retries: Maximum retry attempts on failure
            base_delay: Base delay in seconds for exponential backoff
        """
        self.rate_limit = rate_limit
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.last_request = datetime.now()

    async def _rate_limit_wait(self):
        """Implement rate limiting to avoid overwhelming APIs."""
        now = datetime.now()
        time_since_last = (now - self.last_request).total_seconds()
        min_interval = 60.0 / self.rate_limit

        if time_since_last < min_interval:
            wait_time = min_interval - time_since_last
            logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)

        self.last_request = datetime.now()

    async def _retry_request(
        self,
        session: aiohttp.ClientSession,
        method: str,
        url: str,
        **kwargs,
    ) -> aiohttp.ClientResponse:
        """Make HTTP request with retry logic and exponential backoff.

        Args:
            session: aiohttp client session
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            **kwargs: Additional arguments for the request

        Returns:
            aiohttp.ClientResponse

        Raises:
            DataSourceError: If all retries fail
        """
        for attempt in range(self.max_retries):
            try:
                await self._rate_limit_wait()

                async with session.request(method, url, **kwargs) as response:
                    if response.status == 200:
                        return response
                    elif response.status == 429:  # Rate limited
                        retry_after = int(response.headers.get("Retry-After", 60))
                        logger.warning(f"Rate limited, waiting {retry_after}s")
                        await asyncio.sleep(retry_after)
                        continue
                    elif response.status >= 500:  # Server error
                        logger.warning(f"Server error {response.status}, retrying...")
                        delay = self.base_delay * (2**attempt)
                        await asyncio.sleep(delay)
                        continue
                    else:
                        raise DataSourceError(
                            f"HTTP {response.status}: {await response.text()}"
                        )

            except aiohttp.ClientError as e:
                logger.warning(
                    f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt == self.max_retries - 1:
                    raise DataSourceError(
                        f"Request failed after {self.max_retries} attempts: {e}"
                    ) from e
                delay = self.base_delay * (2**attempt)
                await asyncio.sleep(delay)

        raise DataSourceError(f"Request failed after {self.max_retries} attempts")

    @abstractmethod
    async def fetch(self, *args, **kwargs) -> List[Dict[str, Any]]:
        """Fetch data from the source.

        This method must be implemented by subclasses.

        Returns:
            List of data records
        """
        pass
