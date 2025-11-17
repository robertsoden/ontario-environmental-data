"""Configuration for Ontario environmental data sources.

This module provides configuration dataclasses for managing API keys,
rate limits, and other settings for Ontario data sources.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class OntarioConfig:
    """Configuration for Ontario data sources.

    Attributes:
        ebird_api_key: API key for eBird API (optional, but required for eBird data)
        datastream_api_key: API key for DataStream water quality API (optional)
        inat_rate_limit: Rate limit for iNaturalist API in requests per minute (default: 60)
        cache_ttl_hours: Cache time-to-live in hours for cached data (default: 24)

    Examples:
        >>> config = OntarioConfig(ebird_api_key="your-api-key-here")
        >>> config.inat_rate_limit
        60

        >>> # Custom configuration
        >>> config = OntarioConfig(
        ...     ebird_api_key="key123",
        ...     inat_rate_limit=100,
        ...     cache_ttl_hours=12
        ... )
        >>> config.cache_ttl_hours
        12
    """

    ebird_api_key: Optional[str] = None
    datastream_api_key: Optional[str] = None
    inat_rate_limit: int = 60  # requests per minute
    cache_ttl_hours: int = 24
