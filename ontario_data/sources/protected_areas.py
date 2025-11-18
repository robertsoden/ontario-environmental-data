"""Protected areas data source clients for Ontario.

Provides clients for:
- Ontario Provincial Parks (Ontario GeoHub)
- Conservation Areas (Conservation Ontario)
"""

import io
import logging
from typing import Dict, List, Optional

import aiohttp
import geopandas as gpd
import pandas as pd

from ontario_data.sources.base import BaseClient, DataSourceError

logger = logging.getLogger(__name__)


class OntarioGeoHubClient(BaseClient):
    """Client for Ontario GeoHub / Land Information Ontario (LIO).

    Provides access to Ontario government geospatial data including:
    - Provincial parks and conservation reserves
    - Conservation authority boundaries
    - Other environmental datasets

    Base URL: https://geohub.lio.gov.on.ca/
    """

    # Ontario Parks from LIO Topographic MapServer
    PARKS_URL = "https://ws.lioservices.lrc.gov.on.ca/arcgis1071a/rest/services/LIO_Cartographic/LIO_Topographic/MapServer/9/query"

    # Conservation Authorities from MOE MapServer
    CONSERVATION_AUTHORITIES_URL = "https://ws.lioservices.lrc.gov.on.ca/arcgis1071a/rest/services/MOE/Conservation_Authorities/MapServer/0/query"

    def __init__(self, rate_limit: int = 60):
        """Initialize Ontario GeoHub client.

        Args:
            rate_limit: Requests per minute (default 60)
        """
        super().__init__(rate_limit=rate_limit)

    async def get_provincial_parks(
        self,
        bounds: Optional[tuple] = None,
    ) -> gpd.GeoDataFrame:
        """Get Ontario provincial parks and conservation reserves.

        Args:
            bounds: Optional bounding box (swlat, swlng, nelat, nelng)

        Returns:
            GeoDataFrame with park boundaries

        Example:
            >>> client = OntarioGeoHubClient()
            >>> parks = await client.get_provincial_parks()
        """
        logger.info("Fetching Ontario provincial parks from GeoHub")

        async with aiohttp.ClientSession() as session:
            await self._rate_limit_wait()

            # Build query parameters
            params = {
                "where": "1=1",  # Get all features
                "outFields": "*",
                "f": "geojson",
            }

            # Add spatial filter if bounds provided
            if bounds:
                swlat, swlng, nelat, nelng = bounds
                params["geometry"] = f"{swlng},{swlat},{nelng},{nelat}"
                params["geometryType"] = "esriGeometryEnvelope"
                params["spatialRel"] = "esriSpatialRelIntersects"

            try:
                async with session.get(
                    self.PARKS_URL, params=params, timeout=300
                ) as response:
                    if response.status != 200:
                        logger.warning(f"Parks request failed: HTTP {response.status}")
                        raise DataSourceError(f"Parks request failed: HTTP {response.status}")

                    content = await response.text()
                    gdf = gpd.read_file(io.StringIO(content))

                    if gdf.empty:
                        logger.warning("No parks found")
                        return gdf

                    # Standardize column names
                    column_mapping = {
                        "PARK_NAME": "name",
                        "OFFICIAL_NAME": "official_name",
                        "ONT_PARK_ID": "park_id",
                        "REGULATION": "designation",
                        "AREA_HA": "hectares",
                        "MANAGEMENT_UNIT": "managing_authority",
                        "PARK_CLASS": "park_class",
                        "ZONE_CLASS": "zone_class",
                    }

                    rename_dict = {
                        old: new for old, new in column_mapping.items()
                        if old in gdf.columns
                    }
                    gdf = gdf.rename(columns=rename_dict)

                    # Set defaults for missing columns
                    if "name" not in gdf.columns:
                        name_candidates = [c for c in gdf.columns if "name" in c.lower()]
                        if name_candidates:
                            gdf = gdf.rename(columns={name_candidates[0]: "name"})

                    if "official_name" not in gdf.columns and "name" in gdf.columns:
                        gdf["official_name"] = gdf["name"]

                    if "designation" not in gdf.columns:
                        gdf["designation"] = "Provincial Park"

                    if "managing_authority" not in gdf.columns:
                        gdf["managing_authority"] = "Ontario Parks"

                    # Calculate area if missing
                    if "hectares" not in gdf.columns and "geometry" in gdf.columns:
                        gdf_projected = gdf.to_crs("EPSG:3347")  # Stats Canada Lambert
                        gdf["hectares"] = gdf_projected.geometry.area / 10000  # m² to ha

                    # Ensure CRS
                    if gdf.crs != "EPSG:4326":
                        gdf = gdf.to_crs("EPSG:4326")

                    # Clean data
                    gdf = gdf.dropna(subset=["geometry"])
                    gdf = gdf[gdf.geometry.is_valid]

                    logger.info(f"Fetched {len(gdf)} provincial parks")
                    return gdf

            except Exception as e:
                logger.error(f"Error fetching provincial parks: {e}")
                raise DataSourceError(f"Failed to fetch provincial parks: {e}")

    async def get_conservation_authorities(
        self,
        bounds: Optional[tuple] = None,
    ) -> gpd.GeoDataFrame:
        """Get Conservation Authority boundaries.

        Args:
            bounds: Optional bounding box (swlat, swlng, nelat, nelng)

        Returns:
            GeoDataFrame with conservation authority boundaries

        Example:
            >>> client = OntarioGeoHubClient()
            >>> authorities = await client.get_conservation_authorities()
        """
        logger.info("Fetching Conservation Authority boundaries from GeoHub")

        async with aiohttp.ClientSession() as session:
            await self._rate_limit_wait()

            params = {
                "where": "1=1",
                "outFields": "*",
                "f": "geojson",
            }

            if bounds:
                swlat, swlng, nelat, nelng = bounds
                params["geometry"] = f"{swlng},{swlat},{nelng},{nelat}"
                params["geometryType"] = "esriGeometryEnvelope"
                params["spatialRel"] = "esriSpatialRelIntersects"

            try:
                async with session.get(
                    self.CONSERVATION_AUTHORITIES_URL, params=params, timeout=300
                ) as response:
                    if response.status != 200:
                        logger.warning(f"Conservation authorities request failed: HTTP {response.status}")
                        raise DataSourceError(f"Request failed: HTTP {response.status}")

                    content = await response.text()
                    gdf = gpd.read_file(io.StringIO(content))

                    if gdf.empty:
                        logger.warning("No conservation authorities found")
                        return gdf

                    # Ensure CRS
                    if gdf.crs != "EPSG:4326":
                        gdf = gdf.to_crs("EPSG:4326")

                    logger.info(f"Fetched {len(gdf)} conservation authority boundaries")
                    return gdf

            except Exception as e:
                logger.error(f"Error fetching conservation authorities: {e}")
                raise DataSourceError(f"Failed to fetch conservation authorities: {e}")

    async def fetch(
        self,
        dataset: str = "parks",
        bounds: Optional[tuple] = None,
        **kwargs,
    ) -> List[Dict]:
        """Fetch data (implements BaseClient.fetch).

        Args:
            dataset: Dataset to fetch ("parks" or "conservation_authorities")
            bounds: Optional bounding box
            **kwargs: Additional arguments

        Returns:
            List of feature dictionaries
        """
        if dataset == "parks":
            gdf = await self.get_provincial_parks(bounds=bounds)
        elif dataset == "conservation_authorities":
            gdf = await self.get_conservation_authorities(bounds=bounds)
        else:
            raise ValueError(f"Unknown dataset: {dataset}")

        # Convert to list of dictionaries
        features = []
        for _, row in gdf.iterrows():
            feature = row.to_dict()
            # Convert geometry to GeoJSON
            feature["geometry"] = gpd.GeoSeries([row.geometry]).to_json()
            features.append(feature)

        return features
