"""Fire data source clients for Ontario.

Provides clients for:
- CWFIS (Canadian Wildland Fire Information System)
- Fire perimeters and fuel type mapping
"""

import io
import logging
from typing import Dict, List, Optional

import aiohttp
import geopandas as gpd
import pandas as pd

from ontario_data.sources.base import BaseClient, DataSourceError

logger = logging.getLogger(__name__)


class CWFISClient(BaseClient):
    """Client for Canadian Wildland Fire Information System (CWFIS).

    Provides access to:
    - Historical fire perimeters
    - Current fire danger ratings
    - Wildland fuel type classifications

    Base URL: https://cwfis.cfs.nrcan.gc.ca/
    WFS/WMS: https://cwfis.cfs.nrcan.gc.ca/geoserver/public/ows
    """

    WFS_URL = "https://cwfis.cfs.nrcan.gc.ca/geoserver/public/wfs"
    WMS_URL = "https://cwfis.cfs.nrcan.gc.ca/geoserver/public/wms"

    def __init__(self, rate_limit: int = 60):
        """Initialize CWFIS client.

        Args:
            rate_limit: Requests per minute (default 60)
        """
        super().__init__(rate_limit=rate_limit)

    async def get_fire_perimeters(
        self,
        bounds: tuple,
        start_year: int,
        end_year: int,
        province: Optional[str] = None,
    ) -> gpd.GeoDataFrame:
        """Get historical fire perimeters from NBAC (National Burned Area Composite).

        Args:
            bounds: Bounding box (swlat, swlng, nelat, nelng) - optional if province specified
            start_year: Start year for fire data
            end_year: End year for fire data
            province: Optional 2-letter province code (e.g., 'ON', 'BC') for admin_area filter.
                     Recommended for province-wide queries due to CRS issues with bbox.

        Returns:
            GeoDataFrame with fire perimeter polygons

        Example:
            >>> client = CWFISClient()
            >>> # Province-wide (recommended):
            >>> fires = await client.get_fire_perimeters(None, 2010, 2024, province='ON')
            >>> # Specific bbox:
            >>> fires = await client.get_fire_perimeters((44.0, -79.0, 45.0, -78.0), 2010, 2024)
        """
        logger.info(f"Fetching fire perimeters ({start_year}-{end_year})")

        # Prepare spatial filter
        if province:
            # Use admin_area filter (more reliable for province-wide queries)
            spatial_filter = f"admin_area='{province}'"
            logger.info(f"  Using province filter: {province}")
        elif bounds:
            # Use BBOX function in CQL (note: NBAC geometry is in EPSG:3978)
            swlat, swlng, nelat, nelng = bounds
            bbox_str = f"{swlng},{swlat},{nelng},{nelat}"
            spatial_filter = f"BBOX(geometry,{bbox_str})"
            logger.info(f"  Using bbox filter: {bbox_str}")
        else:
            raise ValueError("Either bounds or province must be specified")

        all_perimeters = []

        async with aiohttp.ClientSession() as session:
            for year in range(start_year, end_year + 1):
                await self._rate_limit_wait()

                logger.info(f"  Fetching fire perimeters for {year}...")

                try:
                    # WFS GetFeature request for NBAC layer with spatial and year filter
                    # Note: bbox and CQL_FILTER are mutually exclusive, so we use spatial filter within CQL_FILTER
                    cql_filter = f"year={year} AND {spatial_filter}"

                    params = {
                        "service": "WFS",
                        "version": "2.0.0",
                        "request": "GetFeature",
                        "typeName": "public:nbac",  # Single NBAC layer (1972-2024)
                        "outputFormat": "application/json",
                        "srsName": "EPSG:4326",
                        "CQL_FILTER": cql_filter,  # Combined spatial and temporal filter
                    }

                    async with session.get(
                        self.WFS_URL, params=params, timeout=30
                    ) as response:
                        if response.status == 200:
                            content = await response.text()

                            if "features" in content:
                                gdf = gpd.read_file(io.StringIO(content))

                                if not gdf.empty:
                                    # Year field already exists in NBAC data
                                    all_perimeters.append(gdf)
                                    logger.info(f"    Found {len(gdf)} fire perimeters")
                                else:
                                    logger.info(f"    No fires found in AOI")
                            else:
                                logger.warning(f"    No data for {year}")
                        else:
                            logger.warning(f"    Request failed for {year}: HTTP {response.status}")

                except Exception as e:
                    logger.warning(f"    Error fetching {year}: {e}")
                    continue

        if all_perimeters:
            combined = gpd.GeoDataFrame(pd.concat(all_perimeters, ignore_index=True))
            combined = combined.set_crs("EPSG:4326")

            logger.info(f"Total fire perimeters: {len(combined)}")
            return combined
        else:
            logger.warning("No fire perimeter data downloaded")
            logger.info(
                "Note: NBAC data may require manual download from:\n"
                "  https://opendata.nfis.org/\n"
                "  https://cwfis.cfs.nrcan.gc.ca/datamart"
            )
            return gpd.GeoDataFrame()

    async def get_current_fire_danger(
        self,
        bounds: tuple,
    ) -> Dict:
        """Get current fire danger ratings for an area.

        Args:
            bounds: Bounding box (swlat, swlng, nelat, nelng)

        Returns:
            Dictionary with fire danger information

        Note:
            This is a simplified implementation. Full implementation would
            query the CWFIS Fire Weather Index (FWI) layers.
        """
        logger.info("Fetching current fire danger ratings")

        # This would require WMS GetFeatureInfo or WFS query
        # For now, return a placeholder structure

        logger.warning("Current fire danger ratings not yet implemented")
        logger.info("Visit https://cwfis.cfs.nrcan.gc.ca/ for current fire danger")

        return {
            "bounds": bounds,
            "note": "Current fire danger data requires WMS/WFS implementation",
            "source_url": "https://cwfis.cfs.nrcan.gc.ca/",
        }

    async def fetch(
        self,
        bounds: tuple,
        start_year: int = 2010,
        end_year: int = 2024,
        **kwargs,
    ) -> List[Dict]:
        """Fetch fire perimeters (implements BaseClient.fetch).

        Args:
            bounds: Bounding box (swlat, swlng, nelat, nelng)
            start_year: Start year (default 2010)
            end_year: End year (default 2024)
            **kwargs: Additional arguments

        Returns:
            List of fire perimeter dictionaries
        """
        gdf = await self.get_fire_perimeters(bounds, start_year, end_year)

        # Convert to list of dictionaries
        fires = []
        for _, row in gdf.iterrows():
            fire = {
                "fire_id": row.get("FIRE_ID", str(row.get("year", ""))),
                "fire_year": int(row.get("year", start_year)),
                "area_hectares": float(row.get("AREA_HA", 0)) if "AREA_HA" in row else None,
                "cause": row.get("CAUSE", ""),
                "geometry": gpd.GeoSeries([row.geometry]).to_json(),
                "data_source": "CWFIS/NBAC",
            }
            fires.append(fire)

        return fires
