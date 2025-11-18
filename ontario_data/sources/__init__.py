"""API clients for Ontario environmental data sources."""

from ontario_data.sources.base import BaseClient, DataSourceError
from ontario_data.sources.biodiversity import EBirdClient, INaturalistClient
from ontario_data.sources.fire import CWFISClient
from ontario_data.sources.indigenous import (
    StatisticsCanadaWFSClient,
    WaterAdvisoriesClient,
)
from ontario_data.sources.protected_areas import OntarioGeoHubClient

__all__ = [
    "BaseClient",
    "DataSourceError",
    "EBirdClient",
    "INaturalistClient",
    "CWFISClient",
    "OntarioGeoHubClient",
    "StatisticsCanadaWFSClient",
    "WaterAdvisoriesClient",
]
