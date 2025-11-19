"""Ontario Environmental Data Library

A Python library for accessing Ontario-specific environmental and biodiversity data sources.

This library provides:
- API clients for biodiversity data (iNaturalist, eBird)
- API clients for Indigenous data (water advisories, reserve boundaries)
- API clients for protected areas (provincial parks, conservation authorities)
- API clients for fire data (CWFIS fire perimeters)
- API clients for community data (well-being scores, infrastructure projects)
- API clients for satellite data (land cover, NDVI, DEM)
- Data models for validation and processing
- Constants for Ontario regions and First Nations
- Geometry utilities for spatial processing
- Configuration management
"""

__version__ = "0.2.0"

# Configuration
from ontario_data.config import OntarioConfig

# Constants
from ontario_data.constants.data_sources import DATA_SOURCE_URLS
from ontario_data.constants.regions import (
    ONTARIO_PLACE_ID,
    WILLIAMS_TREATY_FIRST_NATIONS,
)

# Data models
from ontario_data.models.biodiversity import BiodiversityObservation
from ontario_data.models.fire import FirePerimeter
from ontario_data.models.indigenous import ReserveBoundary, WaterAdvisory
from ontario_data.models.protected_areas import ProtectedArea

# Base classes
from ontario_data.sources.base import BaseClient, DataSourceError

# Biodiversity clients
from ontario_data.sources.biodiversity import EBirdClient, INaturalistClient

# Boundary data clients
from ontario_data.sources.boundaries import OntarioBoundariesClient

# Community data clients
from ontario_data.sources.community import (
    CommunityWellBeingClient,
    InfrastructureClient,
)

# Fire data clients
from ontario_data.sources.fire import CWFISClient

# Indigenous data clients
from ontario_data.sources.indigenous import (
    StatisticsCanadaWFSClient,
    WaterAdvisoriesClient,
)

# Protected areas clients
from ontario_data.sources.protected_areas import OntarioGeoHubClient

# Satellite data clients
from ontario_data.sources.satellite import SatelliteDataClient

# Data models
from ontario_data.models.biodiversity import BiodiversityObservation
from ontario_data.models.community import CommunityWellBeing, InfrastructureProject
from ontario_data.models.fire import FirePerimeter
from ontario_data.models.indigenous import ReserveBoundary, WaterAdvisory
from ontario_data.models.protected_areas import ProtectedArea

# Utilities
from ontario_data.utils import filter_by_bounds, get_bounds_from_aoi, point_in_bounds

__all__ = [
    # Version
    "__version__",
    # Configuration
    "OntarioConfig",
    # Constants
    "DATA_SOURCE_URLS",
    "ONTARIO_PLACE_ID",
    "WILLIAMS_TREATY_FIRST_NATIONS",
    # Base classes
    "BaseClient",
    "DataSourceError",
    # Biodiversity clients
    "EBirdClient",
    "INaturalistClient",
    # Boundary data clients
    "OntarioBoundariesClient",
    # Community data clients
    "CommunityWellBeingClient",
    "InfrastructureClient",
    # Fire data clients
    "CWFISClient",
    # Indigenous data clients
    "StatisticsCanadaWFSClient",
    "WaterAdvisoriesClient",
    # Protected areas clients
    "OntarioGeoHubClient",
    # Satellite data clients
    "SatelliteDataClient",
    # Data models
    "BiodiversityObservation",
    "CommunityWellBeing",
    "FirePerimeter",
    "InfrastructureProject",
    "ProtectedArea",
    "ReserveBoundary",
    "WaterAdvisory",
    # Utilities
    "filter_by_bounds",
    "get_bounds_from_aoi",
    "point_in_bounds",
]
