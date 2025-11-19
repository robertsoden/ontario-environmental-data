"""Ontario boundary data clients.

Provides clients for:
- Provincial boundaries (Statistics Canada)
- Municipal boundaries (Statistics Canada Census Subdivisions)
- Conservation Authority boundaries (Ontario GeoHub)
- Watershed boundaries (Ontario GeoHub)
"""

import io
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

import aiohttp
import geopandas as gpd

from ontario_data.sources.base import BaseClient, DataSourceError

logger = logging.getLogger(__name__)


class OntarioBoundariesClient(BaseClient):
    """Client for Ontario administrative and environmental boundaries.

    Provides access to:
    - Provincial boundaries
    - Municipal boundaries (from Census Subdivisions)
    - Conservation Authority boundaries
    - Watershed boundaries

    Data sources:
    - Statistics Canada (provincial, municipal)
    - Ontario GeoHub / Land Information Ontario (conservation authorities, watersheds)
    """

    # Ontario GeoHub REST API endpoints
    CONSERVATION_AUTHORITY_URL = "https://ws.lioservices.lrc.gov.on.ca/arcgis2/rest/services/LIO_OPEN_DATA/LIO_Open03/MapServer/11/query"
    GREAT_LAKES_WATERSHED_URL = "https://ws.lioservices.lrc.gov.on.ca/arcgis2/rest/services/MOE/GreatLakes_WS_Bnd/MapServer/1/query"

    # Census Subdivision shapefile (already downloaded for CWB)
    CSD_SHAPEFILE = "data/raw/lcsd000a21a_e.shp"

    # Provincial boundaries (manual download required)
    # Download from: https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/index2021-eng.cfm?year=21
    # Select: Provinces and territories, Shapefile format
    PROVINCIAL_SHAPEFILE = "data/raw/lpr_000b21a_e.shp"  # Cartographic version

    def __init__(self, rate_limit: int = 60):
        """Initialize boundaries client.

        Args:
            rate_limit: Requests per minute (default 60)
        """
        super().__init__(rate_limit=rate_limit)

    async def get_provincial_boundary(self, province: str = "ON") -> gpd.GeoDataFrame:
        """Get Ontario provincial boundary from local shapefile.

        Args:
            province: Province code (default "ON" for Ontario)

        Returns:
            GeoDataFrame with provincial boundary

        Example:
            >>> client = OntarioBoundariesClient()
            >>> ontario = await client.get_provincial_boundary("ON")
        """
        shapefile_path = Path(__file__).parent.parent.parent / self.PROVINCIAL_SHAPEFILE

        if not shapefile_path.exists():
            raise FileNotFoundError(
                f"Provincial boundaries shapefile not found: {shapefile_path}\n"
                "Download from: https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/index2021-eng.cfm?year=21\n"
                "Select: Provinces and territories (PRs), Cartographic boundary file, Shapefile format\n"
                "Extract and place lpr_000b21a_e.shp and related files in data/raw/"
            )

        logger.info(f"Reading provincial boundaries from {shapefile_path}")
        gdf = gpd.read_file(shapefile_path)

        # Filter to specified province
        if province and "PRUID" in gdf.columns:
            # Ontario's PRUID is "35"
            prov_code = "35" if province.upper() == "ON" else province
            gdf = gdf[gdf["PRUID"] == prov_code].copy()
            logger.info(f"Filtered to {len(gdf)} {province} boundary")

        # Ensure CRS
        if gdf.crs is None:
            gdf.set_crs("EPSG:4326", inplace=True)
        elif gdf.crs != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")

        return gdf

    async def get_municipalities(
        self, province: str = "ON", csd_types: Optional[List[str]] = None
    ) -> gpd.GeoDataFrame:
        """Get municipal boundaries from Census Subdivision shapefile.

        Args:
            province: Province code (default "ON" for Ontario)
            csd_types: Optional list of CSD types to filter (e.g., ["CY", "T", "TP"])
                      CY=City, T=Town, TP=Township, MU=Municipality, etc.

        Returns:
            GeoDataFrame with municipal boundaries

        Example:
            >>> client = OntarioBoundariesClient()
            >>> cities = await client.get_municipalities("ON", csd_types=["CY"])
        """
        shapefile_path = Path(__file__).parent.parent.parent / self.CSD_SHAPEFILE

        if not shapefile_path.exists():
            raise FileNotFoundError(
                f"Census subdivisions shapefile not found: {shapefile_path}\n"
                "This file is also used for Community Well-Being data.\n"
                "Download from: https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/files-fichiers/lcsd000a21a_e.zip"
            )

        logger.info(f"Reading municipal boundaries from {shapefile_path}")
        gdf = gpd.read_file(shapefile_path)

        # Filter to specified province
        if province and "PRUID" in gdf.columns:
            prov_code = "35" if province.upper() == "ON" else province
            gdf = gdf[gdf["PRUID"] == prov_code].copy()
            logger.info(f"Filtered to {len(gdf)} {province} census subdivisions")

        # Filter by CSD type if specified
        if csd_types and "CSDTYPE" in gdf.columns:
            gdf = gdf[gdf["CSDTYPE"].isin(csd_types)].copy()
            logger.info(f"Filtered to {len(gdf)} CSDs of types: {csd_types}")

        # Ensure CRS
        if gdf.crs is None:
            gdf.set_crs("EPSG:4326", inplace=True)
        elif gdf.crs != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")

        return gdf

    async def get_conservation_authorities(self) -> gpd.GeoDataFrame:
        """Get Conservation Authority boundaries from Ontario GeoHub.

        Returns:
            GeoDataFrame with conservation authority boundaries

        Example:
            >>> client = OntarioBoundariesClient()
            >>> authorities = await client.get_conservation_authorities()
        """
        logger.info("Fetching Conservation Authority boundaries from Ontario GeoHub")

        async with aiohttp.ClientSession() as session:
            await self._rate_limit_wait()

            # Query all conservation authorities
            params = {
                "where": "1=1",  # Get all features
                "outFields": "*",
                "returnGeometry": "true",
                "f": "geojson",
                "resultRecordCount": 100,  # Ontario has ~36 conservation authorities
            }

            try:
                async with session.get(
                    self.CONSERVATION_AUTHORITY_URL, params=params, timeout=60
                ) as response:
                    if response.status != 200:
                        logger.warning(f"REST request failed: HTTP {response.status}")
                        raise DataSourceError(
                            f"REST request failed: HTTP {response.status}"
                        )

                    content = await response.text()

                    # Parse GeoJSON response
                    gdf = gpd.read_file(io.StringIO(content))

                    if gdf.empty:
                        logger.warning("No conservation authority boundaries found")
                        return gdf

                    # Ensure CRS
                    if gdf.crs is None:
                        gdf.set_crs("EPSG:4326", inplace=True)
                    elif gdf.crs != "EPSG:4326":
                        gdf = gdf.to_crs("EPSG:4326")

                    logger.info(f"Fetched {len(gdf)} conservation authority boundaries")
                    return gdf

            except Exception as e:
                logger.error(f"Error fetching conservation authorities: {e}")
                raise DataSourceError(
                    f"Failed to fetch conservation authorities: {e}"
                ) from e

    async def get_watersheds(
        self, watershed_type: str = "great_lakes"
    ) -> gpd.GeoDataFrame:
        """Get watershed boundaries from Ontario GeoHub.

        Args:
            watershed_type: Type of watersheds to fetch
                           "great_lakes" - Great Lakes watersheds (5 major basins)

        Returns:
            GeoDataFrame with watershed boundaries

        Example:
            >>> client = OntarioBoundariesClient()
            >>> watersheds = await client.get_watersheds("great_lakes")
        """
        logger.info(
            f"Fetching {watershed_type} watershed boundaries from Ontario GeoHub"
        )

        # Select appropriate URL based on watershed type
        if watershed_type == "great_lakes":
            url = self.GREAT_LAKES_WATERSHED_URL
        else:
            raise ValueError(f"Unknown watershed type: {watershed_type}")

        async with aiohttp.ClientSession() as session:
            await self._rate_limit_wait()

            # Query all watersheds
            params = {
                "where": "1=1",  # Get all features
                "outFields": "*",
                "returnGeometry": "true",
                "f": "geojson",
                "resultRecordCount": 50,
            }

            try:
                async with session.get(url, params=params, timeout=60) as response:
                    if response.status != 200:
                        logger.warning(f"REST request failed: HTTP {response.status}")
                        raise DataSourceError(
                            f"REST request failed: HTTP {response.status}"
                        )

                    content = await response.text()

                    # Parse GeoJSON response
                    gdf = gpd.read_file(io.StringIO(content))

                    if gdf.empty:
                        logger.warning("No watershed boundaries found")
                        return gdf

                    # Ensure CRS
                    if gdf.crs is None:
                        gdf.set_crs("EPSG:4326", inplace=True)
                    elif gdf.crs != "EPSG:4326":
                        gdf = gdf.to_crs("EPSG:4326")

                    logger.info(f"Fetched {len(gdf)} watershed boundaries")
                    return gdf

            except Exception as e:
                logger.error(f"Error fetching watersheds: {e}")
                raise DataSourceError(f"Failed to fetch watersheds: {e}") from e

    async def fetch(
        self, boundary_type: str = "provincial", **kwargs
    ) -> Union[List[Dict], gpd.GeoDataFrame]:
        """Fetch boundary data (implements BaseClient.fetch).

        Args:
            boundary_type: Type of boundary to fetch:
                          "provincial", "municipal", "conservation_authorities", "watersheds"
            **kwargs: Additional arguments passed to specific methods

        Returns:
            GeoDataFrame with requested boundaries
        """
        if boundary_type == "provincial":
            return await self.get_provincial_boundary(**kwargs)
        elif boundary_type == "municipal":
            return await self.get_municipalities(**kwargs)
        elif boundary_type == "conservation_authorities":
            return await self.get_conservation_authorities()
        elif boundary_type == "watersheds":
            return await self.get_watersheds(**kwargs)
        else:
            raise ValueError(
                f"Unknown boundary_type: {boundary_type}. "
                f"Must be one of: provincial, municipal, conservation_authorities, watersheds"
            )
