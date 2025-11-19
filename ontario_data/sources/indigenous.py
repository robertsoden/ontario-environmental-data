"""Indigenous data source clients for Ontario.

Provides clients for:
- Water advisories (Indigenous Services Canada)
- First Nations reserve boundaries (Statistics Canada WFS)
"""

import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

import aiohttp
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from ontario_data.sources.base import BaseClient, DataSourceError

logger = logging.getLogger(__name__)


class WaterAdvisoriesClient(BaseClient):
    """Client for Indigenous Services Canada water advisories.

    Data source: Indigenous Services Canada
    URL: https://www.sac-isc.gc.ca/eng/1506514143353/1533317130660

    Note: Currently requires manual CSV download. Future versions may implement
    web scraping if an API becomes available.
    """

    SOURCE_URL = "https://www.sac-isc.gc.ca/eng/1506514143353/1533317130660"

    def __init__(self, rate_limit: int = 60):
        """Initialize water advisories client.

        Args:
            rate_limit: Requests per minute (default 60)
        """
        super().__init__(rate_limit=rate_limit)

    async def fetch_from_csv(
        self,
        csv_path: Union[str, Path],
        province: str = "ON",
    ) -> List[Dict]:
        """Fetch water advisories from a local CSV file.

        Args:
            csv_path: Path to the CSV file from ISC
            province: Province code to filter (default "ON" for Ontario)

        Returns:
            List of standardized water advisory dictionaries

        Example:
            >>> client = WaterAdvisoriesClient()
            >>> advisories = await client.fetch_from_csv("water_advisories.csv")
        """
        csv_path = Path(csv_path)

        if not csv_path.exists():
            raise FileNotFoundError(
                f"CSV file not found: {csv_path}\n" f"Download from: {self.SOURCE_URL}"
            )

        logger.info(f"Reading water advisories from {csv_path}")

        # Read CSV with flexible encoding
        try:
            df = pd.read_csv(csv_path, encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(csv_path, encoding="latin-1")

        logger.info(f"Loaded {len(df)} water advisory records")

        # Filter for specified province
        if "Province" in df.columns:
            df = df[df["Province"].str.upper() == province.upper()].copy()
            logger.info(f"Filtered to {len(df)} {province} records")

        # Remove records without valid coordinates
        df = df.dropna(subset=["Latitude", "Longitude"])

        # Convert coordinates to numeric
        df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
        df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")
        df = df.dropna(subset=["Latitude", "Longitude"])

        logger.info(f"{len(df)} records with valid coordinates")

        # Process into standardized format
        advisories = []
        for _, row in df.iterrows():
            advisory = self._transform_row(row)
            advisories.append(advisory)

        logger.info(f"Processed {len(advisories)} water advisories")

        return advisories

    def _transform_row(self, row: pd.Series) -> Dict:
        """Transform a CSV row into standardized format.

        Args:
            row: Pandas Series from CSV

        Returns:
            Standardized advisory dictionary
        """
        # Parse dates
        advisory_date = None
        if "Advisory Date" in row and pd.notna(row["Advisory Date"]):
            try:
                advisory_date = pd.to_datetime(row["Advisory Date"]).date()
            except Exception:
                pass

        lift_date = None
        if "Lift Date" in row and pd.notna(row["Lift Date"]):
            try:
                lift_date = pd.to_datetime(row["Lift Date"]).date()
            except Exception:
                pass

        # Calculate duration
        duration_days = None
        is_active = lift_date is None

        if advisory_date:
            if lift_date:
                duration_days = (lift_date - advisory_date).days
            else:
                duration_days = (datetime.now().date() - advisory_date).days

        return {
            "advisory_id": str(row.get("Advisory ID", "")),
            "community_name": str(row.get("Community", "")),
            "first_nation": str(row.get("First Nation", "")),
            "region": str(row.get("Region", "")),
            "province": str(row.get("Province", "ON")),
            "advisory_type": str(row.get("Advisory Type", "")),
            "advisory_date": advisory_date.isoformat() if advisory_date else None,
            "lift_date": lift_date.isoformat() if lift_date else None,
            "duration_days": duration_days,
            "is_active": is_active,
            "reason": str(row.get("Reason", "")),
            "water_system_name": str(row.get("Water System", "")),
            "population_affected": (
                int(row.get("Population", 0))
                if pd.notna(row.get("Population"))
                else None
            ),
            "latitude": float(row["Latitude"]),
            "longitude": float(row["Longitude"]),
            "data_source": "Indigenous Services Canada",
            "source_url": self.SOURCE_URL,
        }

    async def fetch(
        self,
        csv_path: Optional[Union[str, Path]] = None,
        province: str = "ON",
        **kwargs,
    ) -> List[Dict]:
        """Fetch water advisories (implements BaseClient.fetch).

        Args:
            csv_path: Optional path to CSV file. Required for now.
            province: Province code (default "ON")
            **kwargs: Additional arguments

        Returns:
            List of standardized water advisory dictionaries
        """
        if csv_path is None:
            raise ValueError(
                "csv_path is required. Download CSV from:\n"
                f"{self.SOURCE_URL}\n"
                "Future versions may support direct download."
            )

        return await self.fetch_from_csv(csv_path, province=province)

    def to_geodataframe(self, advisories: List[Dict]) -> gpd.GeoDataFrame:
        """Convert advisories to GeoDataFrame.

        Args:
            advisories: List of advisory dictionaries

        Returns:
            GeoDataFrame with Point geometries
        """
        if not advisories:
            return gpd.GeoDataFrame()

        df = pd.DataFrame(advisories)
        geometry = [
            Point(row["longitude"], row["latitude"]) for _, row in df.iterrows()
        ]
        gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")

        return gdf


class StatisticsCanadaWFSClient(BaseClient):
    """Client for Natural Resources Canada Aboriginal Lands REST API.

    Provides access to First Nations reserve boundaries via the NRCan
    Aboriginal Lands of Canada Legislative Boundaries service.

    Note: Previously used Statistics Canada WFS (now deprecated/unavailable).
    Updated to use NRCan ESRI REST API which provides Indian Reserve polygons.

    API URL: https://proxyinternet.nrcan-rncan.gc.ca/arcgis/rest/services/CLSS-SATC/CLSS_Administrative_Boundaries/MapServer
    """

    # NRCan ESRI REST endpoint for Aboriginal Lands
    REST_URL = "https://proxyinternet.nrcan-rncan.gc.ca/arcgis/rest/services/CLSS-SATC/CLSS_Administrative_Boundaries/MapServer/0/query"

    # Layer 0 contains Aboriginal Lands (including Indian Reserves)

    def __init__(self, rate_limit: int = 60):
        """Initialize Statistics Canada WFS client.

        Args:
            rate_limit: Requests per minute (default 60)
        """
        super().__init__(rate_limit=rate_limit)

    async def get_reserve_boundaries(
        self,
        province: Optional[str] = "ON",
        first_nations: Optional[List[str]] = None,
        max_features: int = 1000,
    ) -> gpd.GeoDataFrame:
        """Get First Nations reserve boundaries.

        Args:
            province: Province code (e.g., "ON" for Ontario, None for all)
            first_nations: Optional list of First Nation names to filter
            max_features: Maximum number of features to return

        Returns:
            GeoDataFrame with reserve boundaries

        Example:
            >>> client = StatisticsCanadaWFSClient()
            >>> reserves = await client.get_reserve_boundaries(
            ...     first_nations=["Curve Lake First Nation"]
            ... )
        """
        logger.info("Fetching First Nations reserve boundaries from NRCan")

        async with aiohttp.ClientSession() as session:
            await self._rate_limit_wait()

            # Build WHERE clause for ESRI REST query
            where_clauses = ["distributionType='IR'"]  # Filter for Indian Reserves only

            if province:
                where_clauses.append(f"jurisdiction='{province}'")

            if first_nations:
                # Build filter for First Nation names (search in adminAreaNameEng)
                name_filters = " OR ".join([
                    f"adminAreaNameEng LIKE '%{name}%'" for name in first_nations
                ])
                where_clauses.append(f"({name_filters})")

            where_clause = " AND ".join(where_clauses)

            # Build ESRI REST query parameters
            params = {
                "where": where_clause,
                "outFields": "*",
                "returnGeometry": "true",
                "f": "geojson",
                "resultRecordCount": max_features,
            }

            try:
                async with session.get(
                    self.REST_URL, params=params, timeout=60
                ) as response:
                    if response.status != 200:
                        logger.warning(f"WFS request failed: HTTP {response.status}")
                        raise DataSourceError(
                            f"WFS request failed: HTTP {response.status}"
                        )

                    content = await response.text()

                    # Parse GeoJSON response
                    gdf = gpd.read_file(io.StringIO(content))

                    if gdf.empty:
                        logger.warning("No reserve boundaries found matching criteria")
                        return gdf

                    # Ensure CRS
                    if gdf.crs is None:
                        gdf.set_crs("EPSG:4326", inplace=True)
                    elif gdf.crs != "EPSG:4326":
                        gdf = gdf.to_crs("EPSG:4326")

                    logger.info(f"Fetched {len(gdf)} reserve boundaries")
                    return gdf

            except Exception as e:
                logger.error(f"Error fetching reserve boundaries: {e}")
                raise DataSourceError(f"Failed to fetch reserve boundaries: {e}") from e

    async def fetch(
        self,
        province: Optional[str] = "ON",
        first_nations: Optional[List[str]] = None,
        **kwargs,
    ) -> List[Dict]:
        """Fetch reserve boundaries (implements BaseClient.fetch).

        Args:
            province: Province code (default "ON")
            first_nations: Optional list of First Nation names
            **kwargs: Additional arguments

        Returns:
            List of reserve boundary dictionaries with GeoJSON geometries
        """
        gdf = await self.get_reserve_boundaries(
            province=province, first_nations=first_nations
        )

        # Convert to list of dictionaries
        reserves = []
        for _, row in gdf.iterrows():
            reserve = {
                "reserve_name": row.get("adminAreaNameEng", ""),
                "reserve_id": row.get("adminAreaId", ""),
                "first_nation": row.get("adminAreaNameEng", ""),
                "province": row.get("jurisdiction", province),
                "distribution_type": row.get("distributionTypeEng", "Indian Reserve"),
                "accuracy": row.get("absoluteAccuracyEng", ""),
                "geometry": gpd.GeoSeries([row.geometry]).to_json(),
                "data_source": "Natural Resources Canada - Aboriginal Lands of Canada",
                "web_reference": row.get("webReference", ""),
            }
            reserves.append(reserve)

        return reserves

    def create_williams_treaty_data(self) -> gpd.GeoDataFrame:
        """Create Williams Treaty First Nations data with approximate locations.

        This is a fallback method providing known community locations.
        For production, use get_reserve_boundaries() to fetch official data.

        Returns:
            GeoDataFrame with Williams Treaty First Nations
        """
        williams_treaty_nations = [
            {
                "first_nation": "Alderville First Nation",
                "reserve_name": "Alderville 35",
                "treaty": "Williams Treaty (1923)",
                "treaty_date": "1923-10-31",
                "traditional_territory": "Rice Lake, Northumberland County",
                "population": 1100,
                "area_hectares": 1200.0,
                "website": "https://www.aldervillefirstnation.ca",
                "lat": 44.1194,
                "lon": -78.0753,
            },
            {
                "first_nation": "Curve Lake First Nation",
                "reserve_name": "Curve Lake 35",
                "treaty": "Williams Treaty (1923)",
                "treaty_date": "1923-10-31",
                "traditional_territory": "Kawartha Lakes region",
                "population": 2200,
                "area_hectares": 800.0,
                "website": "https://www.curvelakefirstnation.ca",
                "lat": 44.5319,
                "lon": -78.2289,
            },
            {
                "first_nation": "Hiawatha First Nation",
                "reserve_name": "Hiawatha 36",
                "treaty": "Williams Treaty (1923)",
                "treaty_date": "1923-10-31",
                "traditional_territory": "Rice Lake, near Peterborough",
                "population": 600,
                "area_hectares": 400.0,
                "website": "https://www.hiawathafirstnation.com",
                "lat": 44.2486,
                "lon": -78.1581,
            },
            {
                "first_nation": "Mississaugas of Scugog Island First Nation",
                "reserve_name": "Scugog Island 34",
                "treaty": "Williams Treaty (1923)",
                "treaty_date": "1923-10-31",
                "traditional_territory": "Scugog Island, Lake Scugog",
                "population": 275,
                "area_hectares": 324.0,
                "website": "https://www.scugogfirstnation.com",
                "lat": 44.1178,
                "lon": -78.9017,
            },
            {
                "first_nation": "Chippewas of Beausoleil First Nation",
                "reserve_name": "Chimnissing 1",
                "treaty": "Williams Treaty (1923)",
                "treaty_date": "1923-10-31",
                "traditional_territory": "Christian Island, Georgian Bay",
                "population": 1900,
                "area_hectares": 1360.0,
                "website": "https://www.chimnissing.ca",
                "lat": 44.8194,
                "lon": -80.0092,
            },
            {
                "first_nation": "Chippewas of Georgina Island First Nation",
                "reserve_name": "Georgina Island 33",
                "treaty": "Williams Treaty (1923)",
                "treaty_date": "1923-10-31",
                "traditional_territory": "Georgina Island, Lake Simcoe",
                "population": 750,
                "area_hectares": 505.0,
                "website": "https://www.georginaisland.com",
                "lat": 44.3392,
                "lon": -79.3483,
            },
            {
                "first_nation": "Chippewas of Rama First Nation",
                "reserve_name": "Rama 32",
                "treaty": "Williams Treaty (1923)",
                "treaty_date": "1923-10-31",
                "traditional_territory": "Lake Couchiching, Rama",
                "population": 950,
                "area_hectares": 932.0,
                "website": "https://www.ramafirstnation.ca",
                "lat": 44.6156,
                "lon": -79.3014,
            },
        ]

        df = pd.DataFrame(williams_treaty_nations)
        geometry = [Point(row["lon"], row["lat"]) for _, row in df.iterrows()]
        gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
        gdf = gdf.drop(columns=["lat", "lon"])

        gdf["province"] = "ON"
        gdf["data_source"] = "Approximate locations - verify with official sources"

        return gdf
