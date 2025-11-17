"""Ontario Environmental Data Library

A Python library for accessing Ontario-specific environmental and biodiversity data sources.

This library provides:
- API clients for biodiversity data (iNaturalist, eBird, GBIF)
- API clients for water quality data (PWQMN, DataStream)
- Data models for validation and processing
- Constants for Ontario regions and First Nations
- Geometry utilities for spatial processing
- Configuration management
"""

__version__ = "0.1.0"

from ontario_data.config import OntarioConfig
from ontario_data.sources.base import BaseClient, DataSourceError
from ontario_data.utils import filter_by_bounds, get_bounds_from_aoi, point_in_bounds

__all__ = [
    "BaseClient",
    "DataSourceError",
    "OntarioConfig",
    "get_bounds_from_aoi",
    "point_in_bounds",
    "filter_by_bounds",
    "__version__",
]
