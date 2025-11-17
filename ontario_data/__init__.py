"""Ontario Environmental Data Library

A Python library for accessing Ontario-specific environmental and biodiversity data sources.

This library provides:
- API clients for biodiversity data (iNaturalist, eBird, GBIF)
- API clients for water quality data (PWQMN, DataStream)
- Data models for validation and processing
- Constants for Ontario regions and First Nations
"""

__version__ = "0.1.0"

from ontario_data.sources.base import BaseClient, DataSourceError

__all__ = ["BaseClient", "DataSourceError", "__version__"]
