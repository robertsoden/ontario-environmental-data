"""Public health data source clients for Ontario.

Provides clients for:
- Public Health Unit (PHU) boundaries (Ontario GeoHub)
- Health indicators from OCHPP (Ontario Community Health Profiles Partnership)
"""

import io
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

import aiohttp
import geopandas as gpd
import pandas as pd

from ontario_data.sources.base import BaseClient, DataSourceError

logger = logging.getLogger(__name__)


class PublicHealthClient(BaseClient):
    """Client for Ontario public health data.

    Provides access to:
    - Public Health Unit boundaries from Ontario GeoHub
    - Health indicators from OCHPP Excel data files

    Base URLs:
    - PHU Boundaries: https://geohub.lio.gov.on.ca/
    - OCHPP Data: https://www.ontariohealthprofiles.ca/
    """

    # Ontario GeoHub ArcGIS REST endpoint for PHU boundaries
    PHU_BOUNDARIES_URL = (
        "https://services9.arcgis.com/a03W7iZ8T3s5vB7p/arcgis/rest/services/"
        "MOH_PHU_BOUNDARY/FeatureServer/0/query"
    )

    # Alternative LIO endpoint (backup)
    PHU_BOUNDARIES_LIO_URL = (
        "https://ws.lioservices.lrc.gov.on.ca/arcgis2/rest/services/"
        "LIO_OPEN_DATA/LIO_Open01/MapServer/34/query"
    )

    def __init__(self, rate_limit: int = 60):
        """Initialize Public Health client.

        Args:
            rate_limit: Requests per minute (default 60)
        """
        super().__init__(rate_limit=rate_limit)

    async def get_phu_boundaries(
        self,
        bounds: Optional[tuple] = None,
    ) -> gpd.GeoDataFrame:
        """Get Ontario Public Health Unit boundaries.

        Fetches the 34 PHU boundaries from Ontario GeoHub.

        Args:
            bounds: Optional bounding box (swlat, swlng, nelat, nelng)

        Returns:
            GeoDataFrame with PHU boundary polygons

        Example:
            >>> client = PublicHealthClient()
            >>> phu_gdf = await client.get_phu_boundaries()
            >>> print(f"Found {len(phu_gdf)} Public Health Units")
        """
        logger.info("Fetching Public Health Unit boundaries from Ontario GeoHub")

        async with aiohttp.ClientSession() as session:
            await self._rate_limit_wait()

            params = {
                "where": "1=1",
                "outFields": "*",
                "f": "geojson",
                "returnGeometry": "true",
            }

            # Add spatial filter if bounds provided
            if bounds:
                swlat, swlng, nelat, nelng = bounds
                params["geometry"] = f"{swlng},{swlat},{nelng},{nelat}"
                params["geometryType"] = "esriGeometryEnvelope"
                params["spatialRel"] = "esriSpatialRelIntersects"
                logger.info(f"Using bbox filter: {bounds}")

            # Try primary endpoint first
            try:
                gdf = await self._fetch_phu_from_url(
                    session, self.PHU_BOUNDARIES_URL, params
                )
                if not gdf.empty:
                    return gdf
            except DataSourceError as e:
                logger.warning(f"Primary PHU endpoint failed: {e}")

            # Try backup LIO endpoint
            logger.info("Trying backup LIO endpoint for PHU boundaries")
            try:
                gdf = await self._fetch_phu_from_url(
                    session, self.PHU_BOUNDARIES_LIO_URL, params
                )
                return gdf
            except DataSourceError as e:
                logger.error(f"Backup PHU endpoint also failed: {e}")
                raise

    async def _fetch_phu_from_url(
        self,
        session: aiohttp.ClientSession,
        url: str,
        params: Dict,
    ) -> gpd.GeoDataFrame:
        """Fetch PHU boundaries from a specific URL.

        Args:
            session: aiohttp session
            url: ArcGIS REST endpoint URL
            params: Query parameters

        Returns:
            GeoDataFrame with PHU boundaries
        """
        try:
            async with session.get(url, params=params, timeout=300) as response:
                if response.status != 200:
                    raise DataSourceError(f"PHU request failed: HTTP {response.status}")

                content = await response.text()

                # Check for HTML error page
                if content.strip().startswith("<") or "html" in content[:100].lower():
                    raise DataSourceError("Server returned HTML instead of GeoJSON")

                gdf = gpd.read_file(io.StringIO(content))

                if gdf.empty:
                    logger.warning("No PHU boundaries found")
                    return gdf

                # Standardize column names
                column_mapping = {
                    # Primary endpoint (MOH_PHU_BOUNDARY)
                    "PHU_ID": "phu_id",
                    "NAME_ENG": "name",
                    "NAME_FR": "name_fr",
                    "AREA_SQ_KM": "area_sq_km",
                    "HEALTH_UNIT_ID": "phu_id",
                    # LIO endpoint variations
                    "PHU_NAME_ENG": "name",
                    "PHU_NAME_FR": "name_fr",
                    "OFFICIAL_NAME": "name",
                    "LEGAL_NAME": "name",
                    "MOH_OFFICE_NAME": "office_name",
                }

                rename_dict = {
                    old: new
                    for old, new in column_mapping.items()
                    if old in gdf.columns
                }
                gdf = gdf.rename(columns=rename_dict)

                # Ensure name column exists
                if "name" not in gdf.columns:
                    name_candidates = [c for c in gdf.columns if "name" in c.lower()]
                    if name_candidates:
                        gdf = gdf.rename(columns={name_candidates[0]: "name"})

                # Calculate area if missing
                if "area_sq_km" not in gdf.columns and "geometry" in gdf.columns:
                    gdf_projected = gdf.to_crs("EPSG:3347")
                    gdf["area_sq_km"] = gdf_projected.geometry.area / 1_000_000

                # Ensure CRS is WGS84
                if gdf.crs != "EPSG:4326":
                    gdf = gdf.to_crs("EPSG:4326")

                # Clean data
                gdf = gdf.dropna(subset=["geometry"])
                gdf = gdf[gdf.geometry.is_valid]

                logger.info(f"Fetched {len(gdf)} Public Health Unit boundaries")
                return gdf

        except DataSourceError:
            raise
        except Exception as e:
            logger.error(f"Error fetching PHU boundaries: {e}")
            raise DataSourceError(f"Failed to fetch PHU boundaries: {e}") from e

    async def load_health_indicators_from_excel(
        self,
        excel_path: Union[str, Path],
        indicator_columns: Optional[List[str]] = None,
        sheet_name: Union[str, int] = 0,
    ) -> pd.DataFrame:
        """Load health indicator data from OCHPP Excel file.

        OCHPP provides health indicator data in Excel format. This method
        loads and standardizes the data for joining with PHU boundaries.

        Args:
            excel_path: Path to OCHPP Excel file
            indicator_columns: Specific columns to extract (None for all)
            sheet_name: Sheet name or index to read (default 0)

        Returns:
            DataFrame with health indicator data

        Example:
            >>> client = PublicHealthClient()
            >>> indicators = await client.load_health_indicators_from_excel(
            ...     "data/ochpp/chronic_disease_indicators.xlsx",
            ...     indicator_columns=["diabetes_rate", "hypertension_rate"]
            ... )
        """
        excel_path = Path(excel_path)

        if not excel_path.exists():
            raise FileNotFoundError(
                f"OCHPP Excel file not found: {excel_path}\n"
                f"Download from: https://www.ontariohealthprofiles.ca/dataTablesON.php"
            )

        logger.info(f"Loading health indicators from {excel_path}")

        df = pd.read_excel(excel_path, sheet_name=sheet_name)
        logger.info(f"Loaded {len(df)} rows from Excel")

        # Try to identify PHU name/ID column
        phu_col_candidates = [
            c for c in df.columns
            if any(term in c.lower() for term in ["phu", "health unit", "region"])
        ]
        if phu_col_candidates:
            df = df.rename(columns={phu_col_candidates[0]: "phu_name"})

        # Filter to specific columns if requested
        if indicator_columns:
            keep_cols = ["phu_name"] if "phu_name" in df.columns else []
            keep_cols.extend([c for c in indicator_columns if c in df.columns])
            df = df[keep_cols]

        logger.info(f"Processed {len(df)} health indicator records")
        return df

    async def get_health_indicators_with_boundaries(
        self,
        excel_path: Union[str, Path],
        indicator_columns: Optional[List[str]] = None,
        sheet_name: Union[str, int] = 0,
        join_column: str = "phu_name",
    ) -> gpd.GeoDataFrame:
        """Get health indicators joined with PHU boundaries.

        Loads indicator data from Excel and joins with PHU boundary geometries
        for spatial analysis and mapping.

        Args:
            excel_path: Path to OCHPP Excel file
            indicator_columns: Specific columns to extract
            sheet_name: Excel sheet to read
            join_column: Column to use for joining (default "phu_name")

        Returns:
            GeoDataFrame with health indicators and PHU boundaries

        Example:
            >>> client = PublicHealthClient()
            >>> gdf = await client.get_health_indicators_with_boundaries(
            ...     "data/ochpp/diabetes_rates.xlsx"
            ... )
        """
        # Load indicator data
        indicators_df = await self.load_health_indicators_from_excel(
            excel_path, indicator_columns, sheet_name
        )

        # Get PHU boundaries
        phu_gdf = await self.get_phu_boundaries()

        if phu_gdf.empty:
            logger.warning("No PHU boundaries available for join")
            return gpd.GeoDataFrame(indicators_df)

        # Standardize join columns for fuzzy matching
        if join_column == "phu_name" and "phu_name" in indicators_df.columns:
            indicators_df["_join_key"] = (
                indicators_df["phu_name"]
                .str.lower()
                .str.strip()
                .str.replace(r"[^\w\s]", "", regex=True)
            )
            phu_gdf["_join_key"] = (
                phu_gdf["name"]
                .str.lower()
                .str.strip()
                .str.replace(r"[^\w\s]", "", regex=True)
            )

            joined_gdf = phu_gdf.merge(
                indicators_df,
                on="_join_key",
                how="left",
            )
            joined_gdf = joined_gdf.drop(columns=["_join_key"])
        else:
            # Direct join
            joined_gdf = phu_gdf.merge(
                indicators_df,
                left_on="name",
                right_on=join_column,
                how="left",
            )

        logger.info(f"Joined {len(joined_gdf)} PHUs with health indicators")
        return joined_gdf

    async def fetch(
        self,
        dataset: str = "phu_boundaries",
        bounds: Optional[tuple] = None,
        excel_path: Optional[Union[str, Path]] = None,
        indicator_columns: Optional[List[str]] = None,
        **kwargs,
    ) -> Union[gpd.GeoDataFrame, List[Dict]]:
        """Fetch health data (implements BaseClient.fetch).

        Args:
            dataset: Dataset to fetch ("phu_boundaries" or "health_indicators")
            bounds: Optional bounding box for PHU boundaries
            excel_path: Path to OCHPP Excel file (for health_indicators)
            indicator_columns: Specific indicator columns to extract
            **kwargs: Additional arguments

        Returns:
            GeoDataFrame or list of dictionaries
        """
        if dataset == "phu_boundaries":
            return await self.get_phu_boundaries(bounds=bounds)

        elif dataset == "health_indicators":
            if excel_path is None:
                raise ValueError(
                    "excel_path is required for health_indicators dataset.\n"
                    "Download from: https://www.ontariohealthprofiles.ca/dataTablesON.php"
                )
            return await self.get_health_indicators_with_boundaries(
                excel_path=excel_path,
                indicator_columns=indicator_columns,
                **kwargs,
            )

        else:
            raise ValueError(f"Unknown dataset: {dataset}")


# OCHPP indicator categories and their typical column names
OCHPP_INDICATOR_CATEGORIES = {
    "chronic_disease": {
        "description": "Chronic disease prevalence rates",
        "indicators": [
            "diabetes_rate",
            "hypertension_rate",
            "copd_rate",
            "asthma_rate",
            "heart_disease_rate",
        ],
    },
    "mental_health": {
        "description": "Mental health and addiction indicators",
        "indicators": [
            "mental_health_ed_visits",
            "mental_health_hospitalizations",
            "addiction_ed_visits",
            "self_reported_mental_health",
        ],
    },
    "mortality": {
        "description": "Mortality rates and life expectancy",
        "indicators": [
            "all_cause_mortality",
            "premature_mortality",
            "infant_mortality",
            "life_expectancy",
            "avoidable_mortality",
        ],
    },
    "access_to_care": {
        "description": "Healthcare access and utilization",
        "indicators": [
            "primary_care_attachment",
            "cancer_screening_rate",
            "ed_visit_rate",
            "ambulatory_sensitive_conditions",
        ],
    },
    "reproductive_health": {
        "description": "Reproductive and infant health",
        "indicators": [
            "birth_rate",
            "teen_pregnancy_rate",
            "low_birth_weight_rate",
            "preterm_birth_rate",
        ],
    },
}
