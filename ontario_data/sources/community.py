"""Community socioeconomic data clients for Ontario.

Provides clients for:
- Community Well-Being Index scores (Statistics Canada)
- Indigenous infrastructure projects (ICIM)
"""

import io
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

import aiohttp
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from ontario_data.sources.base import BaseClient, DataSourceError

logger = logging.getLogger(__name__)


class CommunityWellBeingClient(BaseClient):
    """Client for Community Well-Being (CWB) Index data.

    Provides access to Statistics Canada Community Well-Being Index scores
    for Indigenous and non-Indigenous communities across Canada.

    Data source: Statistics Canada (based on Census data)
    """

    # Statistics Canada 2021 Census Subdivision boundaries shapefile
    # Download from: https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/files-fichiers/lcsd000a21a_e.zip
    CSD_SHAPEFILE = "data/raw/lcsd000a21a_e.shp"  # All Canada CSDs, 63MB

    def __init__(self, rate_limit: int = 60):
        """Initialize Community Well-Being client.

        Args:
            rate_limit: Requests per minute (default 60)
        """
        super().__init__(rate_limit=rate_limit)

    async def fetch_from_csv(
        self,
        csv_path: Union[str, Path],
        province: str = "ON",
        first_nations_only: bool = False,
    ) -> List[Dict]:
        """Fetch Community Well-Being data from CSV file.

        Args:
            csv_path: Path to CWB CSV file from Statistics Canada
            province: Province code to filter (default "ON" for Ontario)
            first_nations_only: Filter to First Nations communities only

        Returns:
            List of standardized CWB dictionaries

        Example:
            >>> client = CommunityWellBeingClient()
            >>> cwb_data = await client.fetch_from_csv(
            ...     "data/CWB_2021.csv",
            ...     province="ON",
            ...     first_nations_only=True
            ... )
        """
        csv_path = Path(csv_path)

        if not csv_path.exists():
            raise FileNotFoundError(
                f"CWB CSV file not found: {csv_path}\n"
                f"Download from Statistics Canada"
            )

        logger.info(f"Reading Community Well-Being data from {csv_path}")

        # Read CSV with Latin-1 encoding (common for Stats Canada files)
        try:
            df = pd.read_csv(csv_path, encoding="latin-1")
        except UnicodeDecodeError:
            df = pd.read_csv(csv_path, encoding="utf-8")

        logger.info(f"Loaded {len(df)} CWB records")

        # Filter for specified province (Ontario CSD codes start with "35")
        csd_col = "CSD Code 2021" if "CSD Code 2021" in df.columns else "CSD Code"
        if province == "ON" and csd_col in df.columns:
            df = df[df[csd_col].astype(str).str.startswith("35")].copy()
            logger.info(f"Filtered to {len(df)} Ontario records")

        # Filter to First Nations if requested
        comm_type_col = "Community Type 2021" if "Community Type 2021" in df.columns else "Community Type"
        if first_nations_only and comm_type_col in df.columns:
            df = df[df[comm_type_col].str.contains("First Nation", na=False, case=False)].copy()
            logger.info(f"Filtered to {len(df)} First Nations communities")

        # Process into standardized format
        communities = []
        for _, row in df.iterrows():
            community = self._transform_row(row)
            communities.append(community)

        logger.info(f"Processed {len(communities)} CWB records")

        return communities

    def _transform_row(self, row: pd.Series) -> Dict:
        """Transform a CSV row into standardized format.

        Args:
            row: Pandas Series from CSV

        Returns:
            Standardized community well-being dictionary
        """
        # Handle both with and without year suffix in column names
        return {
            "csd_code": str(row.get("CSD Code 2021", row.get("CSD Code", ""))),
            "csd_name": str(row.get("CSD Name 2021", row.get("CSD Name", ""))),
            "community_type": str(row.get("Community Type 2021", row.get("Community Type", ""))),
            "population": int(row.get("Census Population 2021", row.get("Population", 0))) if pd.notna(row.get("Census Population 2021", row.get("Population"))) else None,
            "income_score": float(row.get("Income 2021", row.get("Income Score", 0))) if pd.notna(row.get("Income 2021", row.get("Income Score"))) else None,
            "education_score": float(row.get("Education 2021", row.get("Education Score", 0))) if pd.notna(row.get("Education 2021", row.get("Education Score"))) else None,
            "housing_score": float(row.get("Housing 2021", row.get("Housing Score", 0))) if pd.notna(row.get("Housing 2021", row.get("Housing Score"))) else None,
            "labour_force_score": float(row.get("Labour Force Activity 2021", row.get("Labour Force Activity Score", 0))) if pd.notna(row.get("Labour Force Activity 2021", row.get("Labour Force Activity Score"))) else None,
            "cwb_score": float(row.get("CWB 2021", row.get("CWB Score", 0))) if pd.notna(row.get("CWB 2021", row.get("CWB Score"))) else None,
            "year": 2021,  # Based on 2021 Census
            "data_source": "Statistics Canada",
        }

    async def get_cwb_with_boundaries(
        self,
        csv_path: Union[str, Path],
        province: str = "ON",
        first_nations_only: bool = False,
    ) -> gpd.GeoDataFrame:
        """Get CWB data joined with census subdivision boundaries.

        Loads boundaries from local shapefile and joins with CWB scores.

        Args:
            csv_path: Path to CWB CSV file
            province: Province code (default "ON")
            first_nations_only: Filter to First Nations only

        Returns:
            GeoDataFrame with CWB scores and boundaries

        Example:
            >>> client = CommunityWellBeingClient()
            >>> gdf = await client.get_cwb_with_boundaries(
            ...     "data/CWB_2021.csv",
            ...     first_nations_only=True
            ... )
        """
        # Get CWB data
        cwb_data = await self.fetch_from_csv(csv_path, province, first_nations_only)
        cwb_df = pd.DataFrame(cwb_data)

        logger.info("Loading census subdivision boundaries from local shapefile")

        # Get the shapefile path (relative to module or absolute)
        shapefile_path = Path(__file__).parent.parent.parent / self.CSD_SHAPEFILE

        if not shapefile_path.exists():
            logger.error(f"Shapefile not found: {shapefile_path}")
            logger.error("Download from: https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/files-fichiers/lcsd000a21a_e.zip")
            return gpd.GeoDataFrame(cwb_df)

        logger.info(f"Reading shapefile: {shapefile_path}")

        # Read the entire shapefile (63MB, all Canada CSDs)
        boundaries_gdf = gpd.read_file(shapefile_path)
        logger.info(f"Loaded {len(boundaries_gdf)} census subdivision boundaries")

        # Filter to only CSDs we need from CWB data
        csd_codes = cwb_df['csd_code'].astype(str).unique()
        boundaries_gdf['CSDUID'] = boundaries_gdf['CSDUID'].astype(str)
        boundaries_gdf = boundaries_gdf[boundaries_gdf['CSDUID'].isin(csd_codes)]

        logger.info(f"Filtered to {len(boundaries_gdf)} CSDs matching CWB data")

        # Join CWB data with boundaries on CSD code
        joined_gdf = boundaries_gdf.merge(
            cwb_df,
            left_on="CSDUID",
            right_on="csd_code",
            how="inner"
        )

        # Convert to EPSG:4326 if needed
        if joined_gdf.crs is None:
            joined_gdf.set_crs("EPSG:4326", inplace=True)
        elif joined_gdf.crs != "EPSG:4326":
            joined_gdf = joined_gdf.to_crs("EPSG:4326")

        logger.info(f"Joined {len(joined_gdf)} communities with boundaries")

        return joined_gdf

    async def fetch(
        self,
        csv_path: Optional[Union[str, Path]] = None,
        province: str = "ON",
        first_nations_only: bool = False,
        include_boundaries: bool = False,
        **kwargs,
    ) -> Union[List[Dict], gpd.GeoDataFrame]:
        """Fetch Community Well-Being data (implements BaseClient.fetch).

        Args:
            csv_path: Required path to CWB CSV file
            province: Province code (default "ON")
            first_nations_only: Filter to First Nations only
            include_boundaries: Whether to join with census boundaries
            **kwargs: Additional arguments

        Returns:
            List of CWB dictionaries or GeoDataFrame with boundaries
        """
        if csv_path is None:
            raise ValueError(
                "csv_path is required. Download CWB data from Statistics Canada:\n"
                "https://www.sac-isc.gc.ca/eng/1419773101942/1419773233645"
            )

        if include_boundaries:
            return await self.get_cwb_with_boundaries(csv_path, province, first_nations_only)
        else:
            return await self.fetch_from_csv(csv_path, province, first_nations_only)

    def to_geodataframe(self, communities: List[Dict]) -> gpd.GeoDataFrame:
        """Convert CWB communities to GeoDataFrame.

        Note: Creates point geometries at community centroids.
        For actual boundaries, use get_cwb_with_boundaries().

        Args:
            communities: List of community dictionaries

        Returns:
            GeoDataFrame with point geometries
        """
        if not communities:
            return gpd.GeoDataFrame()

        df = pd.DataFrame(communities)

        # Note: This creates a simple GeoDataFrame
        # Actual implementation would need coordinates or boundary data
        logger.warning(
            "to_geodataframe() creates placeholder geometries. "
            "Use get_cwb_with_boundaries() for actual census boundaries."
        )

        return gpd.GeoDataFrame(df)


class InfrastructureClient(BaseClient):
    """Client for Indigenous Community Infrastructure Management (ICIM) data.

    Provides access to federal infrastructure project data for Indigenous
    communities across Canada.

    Data source: Indigenous Services Canada ICIM dataset
    """

    def __init__(self, rate_limit: int = 60):
        """Initialize Infrastructure client.

        Args:
            rate_limit: Requests per minute (default 60)
        """
        super().__init__(rate_limit=rate_limit)

    async def fetch_from_csv(
        self,
        csv_path: Union[str, Path],
        province: str = "ON",
        bounds: Optional[tuple] = None,
    ) -> List[Dict]:
        """Fetch infrastructure project data from ICIM CSV export.

        Args:
            csv_path: Path to ICIM CSV export file
            province: Province code to filter (default "ON")
            bounds: Optional bounding box to filter (swlat, swlng, nelat, nelng)

        Returns:
            List of standardized infrastructure project dictionaries

        Example:
            >>> client = InfrastructureClient()
            >>> projects = await client.fetch_from_csv(
            ...     "data/ICIM_Data_Export.csv",
            ...     province="ON"
            ... )
        """
        csv_path = Path(csv_path)

        if not csv_path.exists():
            raise FileNotFoundError(
                f"ICIM CSV file not found: {csv_path}\n"
                f"Request export from Indigenous Services Canada"
            )

        logger.info(f"Reading infrastructure project data from {csv_path}")

        # ICIM exports use UTF-16 encoding with tab delimiters
        try:
            df = pd.read_csv(csv_path, encoding="utf-16", sep="\t")
        except (UnicodeDecodeError, pd.errors.ParserError):
            # Fallback to UTF-8
            df = pd.read_csv(csv_path, encoding="utf-8")

        logger.info(f"Loaded {len(df)} infrastructure projects")

        # Remove rows without valid coordinates
        if "Latitude" in df.columns and "Longitude" in df.columns:
            df = df.dropna(subset=["Latitude", "Longitude"])
            df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
            df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")
            df = df.dropna(subset=["Latitude", "Longitude"])
            logger.info(f"{len(df)} projects with valid coordinates")

        # Filter by province if specified
        if province and "Province" in df.columns:
            df = df[df["Province"].str.upper() == province.upper()].copy()
            logger.info(f"Filtered to {len(df)} {province} projects")

        # Filter by bounds if specified
        if bounds:
            swlat, swlng, nelat, nelng = bounds
            df = df[
                (df["Latitude"] >= swlat) &
                (df["Latitude"] <= nelat) &
                (df["Longitude"] >= swlng) &
                (df["Longitude"] <= nelng)
            ].copy()
            logger.info(f"Filtered to {len(df)} projects within bounds")

        # Process into standardized format
        projects = []
        for _, row in df.iterrows():
            project = self._transform_row(row)
            projects.append(project)

        logger.info(f"Processed {len(projects)} infrastructure projects")

        return projects

    def _transform_row(self, row: pd.Series) -> Dict:
        """Transform a CSV row into standardized format.

        Args:
            row: Pandas Series from CSV

        Returns:
            Standardized infrastructure project dictionary
        """
        return {
            "community_name": str(row.get("Community", "")),
            "community_number": str(row.get("Community Number", "")),
            "project_name": str(row.get("Project Name", "")),
            "project_description": str(row.get("Description", "")),
            "infrastructure_category": str(row.get("Category", "")),
            "project_status": str(row.get("Status", "")),
            "investment_amount": float(row.get("Investment", 0)) if pd.notna(row.get("Investment")) else None,
            "latitude": float(row["Latitude"]) if "Latitude" in row else None,
            "longitude": float(row["Longitude"]) if "Longitude" in row else None,
            "province": str(row.get("Province", "")),
            "data_source": "Indigenous Services Canada ICIM",
        }

    async def fetch(
        self,
        csv_path: Optional[Union[str, Path]] = None,
        province: str = "ON",
        bounds: Optional[tuple] = None,
        **kwargs,
    ) -> List[Dict]:
        """Fetch infrastructure projects (implements BaseClient.fetch).

        Args:
            csv_path: Required path to ICIM CSV export
            province: Province code (default "ON")
            bounds: Optional bounding box filter
            **kwargs: Additional arguments

        Returns:
            List of infrastructure project dictionaries
        """
        if csv_path is None:
            raise ValueError(
                "csv_path is required. Request ICIM data export from:\n"
                "Indigenous Services Canada"
            )

        return await self.fetch_from_csv(csv_path, province, bounds)

    def to_geodataframe(self, projects: List[Dict]) -> gpd.GeoDataFrame:
        """Convert projects to GeoDataFrame.

        Args:
            projects: List of project dictionaries

        Returns:
            GeoDataFrame with Point geometries
        """
        if not projects:
            return gpd.GeoDataFrame()

        df = pd.DataFrame(projects)
        geometry = [
            Point(row["longitude"], row["latitude"])
            for _, row in df.iterrows()
            if row["latitude"] and row["longitude"]
        ]
        gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")

        return gdf
