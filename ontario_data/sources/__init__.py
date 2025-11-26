"""API clients for Ontario environmental data sources."""

from ontario_data.sources.base import BaseClient, DataSourceError
from ontario_data.sources.biodiversity import EBirdClient, INaturalistClient
from ontario_data.sources.community import (
    CommunityWellBeingClient,
    InfrastructureClient,
)
from ontario_data.sources.fire import CWFISClient
from ontario_data.sources.health import PublicHealthClient
from ontario_data.sources.indigenous import (
    StatisticsCanadaWFSClient,
    WaterAdvisoriesClient,
)
from ontario_data.sources.protected_areas import OntarioGeoHubClient

# Satellite client not imported - use separate satellite workflow
# from ontario_data.sources.satellite import SatelliteDataClient

__all__ = [
    "BaseClient",
    "DataSourceError",
    "EBirdClient",
    "INaturalistClient",
    "CommunityWellBeingClient",
    "CWFISClient",
    "InfrastructureClient",
    "OntarioGeoHubClient",
    "PublicHealthClient",
    "SatelliteDataClient",
    "StatisticsCanadaWFSClient",
    "WaterAdvisoriesClient",
]
