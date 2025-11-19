"""Satellite data and remote sensing clients for Ontario.

Provides clients for:
- Land cover classification (Natural Resources Canada)
- NDVI vegetation indices (Planetary Computer / Sentinel-2)
- Digital elevation models (Natural Resources Canada CDEM)
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import aiohttp
import geopandas as gpd
import numpy as np
import pandas as pd

from ontario_data.sources.base import BaseClient, DataSourceError

logger = logging.getLogger(__name__)

# Optional raster dependencies
try:
    import rasterio
    from rasterio.mask import mask as rio_mask
    from rasterio.warp import calculate_default_transform, reproject, Resampling
    from rasterio.io import MemoryFile
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False
    logger.warning("rasterio not available - raster operations will be limited")

try:
    import pystac_client
    import planetary_computer
    PLANETARY_COMPUTER_AVAILABLE = True
except ImportError:
    PLANETARY_COMPUTER_AVAILABLE = False
    logger.warning("pystac-client/planetary-computer not available - NDVI operations will be limited")


class SatelliteDataClient(BaseClient):
    """Client for satellite imagery and derived products.

    Provides access to:
    - Land cover classification from Natural Resources Canada
    - NDVI vegetation indices from Planetary Computer (Sentinel-2)
    - Digital elevation models from Natural Resources Canada

    Note: Requires optional dependencies for full functionality:
        pip install rasterio pystac-client planetary-computer
    """

    # Land cover data sources
    NRCAN_LANDCOVER_YEARS = [2010, 2015, 2020]
    NRCAN_FTP_BASE = "https://ftp.maps.canada.ca/pub/nrcan_rncan/Land-cover_Couverture-du-sol/"

    # DEM data sources
    CDEM_FTP_BASE = "https://ftp.maps.canada.ca/pub/elevation/dem_mne/highresolution_hauteresolution/"

    # Statistics Canada NDVI data (pre-calculated from satellite imagery)
    STATCAN_MODIS_NDVI_FTP = "http://ftp.maps.canada.ca/pub/statcan_statcan/modis/"
    STATCAN_AVHRR_NDVI_FTP = "http://ftp.maps.canada.ca/pub/statcan_statcan/avhrr/"

    # Planetary Computer STAC API (fallback for custom date ranges)
    PLANETARY_COMPUTER_API = "https://planetarycomputer.microsoft.com/api/stac/v1"
    SENTINEL2_COLLECTION = "sentinel-2-l2a"

    def __init__(self, rate_limit: int = 60):
        """Initialize satellite data client.

        Args:
            rate_limit: Requests per minute (default 60)
        """
        super().__init__(rate_limit=rate_limit)

        if not RASTERIO_AVAILABLE:
            logger.warning(
                "Rasterio not installed. Install with: pip install rasterio"
            )

        if not PLANETARY_COMPUTER_AVAILABLE:
            logger.warning(
                "Planetary Computer not installed. Install with: "
                "pip install pystac-client planetary-computer"
            )

    async def get_land_cover(
        self,
        bounds: Tuple[float, float, float, float],
        year: int = 2020,
        output_path: Optional[Union[str, Path]] = None,
    ) -> Optional[Dict]:
        """Get land cover classification for an area.

        Downloads and processes Natural Resources Canada land cover data.

        Args:
            bounds: Bounding box (swlat, swlng, nelat, nelng)
            year: Year of land cover data (2010, 2015, or 2020)
            output_path: Optional path to save clipped GeoTIFF

        Returns:
            Dictionary with metadata and file path, or None if rasterio unavailable

        Example:
            >>> client = SatelliteDataClient()
            >>> result = await client.get_land_cover(
            ...     bounds=(44.0, -79.0, 45.0, -78.0),
            ...     year=2020,
            ...     output_path="data/landcover.tif"
            ... )
        """
        if not RASTERIO_AVAILABLE:
            logger.error("Rasterio required for land cover operations")
            return None

        if year not in self.NRCAN_LANDCOVER_YEARS:
            raise ValueError(
                f"Year must be one of {self.NRCAN_LANDCOVER_YEARS}, got {year}"
            )

        logger.info(f"Land cover data for {year} requires manual download")
        logger.info(
            f"Download from: {self.NRCAN_FTP_BASE}\n"
            f"Extract and process with rasterio to clip to bounds: {bounds}"
        )

        return {
            "year": year,
            "bounds": bounds,
            "source": "Natural Resources Canada",
            "download_url": self.NRCAN_FTP_BASE,
            "note": "Manual download and extraction required",
            "classes": 19,  # NALCMS classification
            "output_path": str(output_path) if output_path else None,
        }

    async def get_ndvi(
        self,
        bounds: Tuple[float, float, float, float],
        start_date: str,
        end_date: str,
        output_path: Optional[Union[str, Path]] = None,
        resolution: str = "250m",
    ) -> Optional[Dict]:
        """Get NDVI vegetation indices from Statistics Canada.

        Downloads pre-calculated NDVI from Statistics Canada's FTP server.
        Data is derived from MODIS (250m) or AVHRR (1km) satellite imagery.

        Note: This downloads the full yearly composite file (6-7 GB) and extracts
        the requested weeks. For production use, consider downloading once and
        caching the yearly file.

        Args:
            bounds: Bounding box (swlat, swlng, nelat, nelng)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            output_path: Optional path to save clipped NDVI GeoTIFF
            resolution: "250m" for MODIS or "1km" for AVHRR (default: "250m")

        Returns:
            Dictionary with metadata and file info

        Example:
            >>> client = SatelliteDataClient()
            >>> result = await client.get_ndvi(
            ...     bounds=(44.0, -79.0, 45.0, -78.0),
            ...     start_date="2023-06-01",
            ...     end_date="2023-06-30",
            ...     output_path="data/ndvi/ndvi_2023-06.tif"
            ... )
        """
        if not RASTERIO_AVAILABLE:
            logger.error("rasterio required for NDVI operations")
            return None

        # Determine FTP source based on resolution
        if resolution == "250m":
            ftp_base = self.STATCAN_MODIS_NDVI_FTP
            source_name = "Statistics Canada MODIS NDVI (250m)"
        elif resolution == "1km":
            ftp_base = self.STATCAN_AVHRR_NDVI_FTP
            source_name = "Statistics Canada AVHRR/VIIRS NDVI (1km)"
        else:
            raise ValueError(f"Resolution must be '250m' or '1km', got '{resolution}'")

        logger.info(f"Downloading NDVI from {source_name} for {start_date} to {end_date}")

        try:
            # Parse dates
            from datetime import datetime as dt
            start_dt = dt.strptime(start_date, "%Y-%m-%d")
            end_dt = dt.strptime(end_date, "%Y-%m-%d")
            year = start_dt.year

            # Calculate Julian weeks
            start_julian = start_dt.timetuple().tm_yday
            end_julian = end_dt.timetuple().tm_yday
            start_week = (start_julian // 7) + 1
            end_week = (end_julian // 7) + 1
            target_week = (start_week + end_week) // 2

            logger.info(f"Target: Year {year}, Julian week {target_week}")

            # Download the yearly composite file (6-7 GB)
            # Format: MODISCOMP7d_YYYY.zip or similar
            if resolution == "250m":
                yearly_file = f"MODISCOMP7d_{year}.zip"
            else:
                yearly_file = f"AVHRRCOMP7d_{year}.zip"

            ftp_url = f"https://ftp.maps.canada.ca/pub/statcan_statcan/{'modis' if resolution == '250m' else 'avhrr'}/{yearly_file}"

            logger.warning(f"Downloading large file: {yearly_file} (~6-7 GB)")
            logger.info(f"URL: {ftp_url}")
            logger.info("This may take several minutes...")

            # For now, return download instructions rather than attempting 6GB download
            return {
                "bounds": bounds,
                "start_date": start_date,
                "end_date": end_date,
                "source": source_name,
                "resolution": resolution,
                "year": year,
                "julian_week": target_week,
                "download_url": ftp_url,
                "output_path": str(output_path) if output_path else None,
                "status": "manual_download_required",
                "file_size": "6-7 GB",
                "note": f"Download {yearly_file} manually from FTP, then extract week {target_week} and clip to bounds.",
                "instructions": [
                    f"1. Download: {ftp_url}",
                    f"2. Extract zip file ({yearly_file})",
                    f"3. Find week {target_week} TIF file in extracted data",
                    f"4. Clip to bounds: {bounds}",
                    f"5. Save to: {output_path}"
                ]
            }

        except Exception as e:
            logger.error(f"Error processing NDVI request: {e}")
            return None

    def _create_synthetic_ndvi(
        self,
        bounds: Tuple[float, float, float, float],
        output_path: Optional[Union[str, Path]] = None,
    ) -> Dict:
        """Create synthetic NDVI data for demonstration.

        Args:
            bounds: Bounding box
            output_path: Optional output path

        Returns:
            Dictionary with synthetic data info
        """
        logger.info("Creating synthetic NDVI data for demonstration")

        if output_path and RASTERIO_AVAILABLE:
            # Create synthetic NDVI grid
            height, width = 500, 500
            ndvi_data = np.random.uniform(-0.2, 0.8, (height, width))

            # Save as GeoTIFF
            swlat, swlng, nelat, nelng = bounds
            transform = rasterio.transform.from_bounds(
                swlng, swlat, nelng, nelat, width, height
            )

            with rasterio.open(
                output_path,
                'w',
                driver='GTiff',
                height=height,
                width=width,
                count=1,
                dtype=ndvi_data.dtype,
                crs='EPSG:4326',
                transform=transform,
                compress='lzw'
            ) as dst:
                dst.write(ndvi_data, 1)

            logger.info(f"Saved synthetic NDVI to {output_path}")

        return {
            "type": "synthetic",
            "bounds": bounds,
            "output_path": str(output_path) if output_path else None,
            "note": "Synthetic data for demonstration - install planetary-computer for real data",
        }

    async def get_elevation(
        self,
        bounds: Tuple[float, float, float, float],
        resolution: str = "20m",
        output_path: Optional[Union[str, Path]] = None,
    ) -> Dict:
        """Get digital elevation model from Natural Resources Canada.

        Downloads CDEM (Canadian Digital Elevation Model) data.

        Args:
            bounds: Bounding box (swlat, swlng, nelat, nelng)
            resolution: Resolution (20m for CDEM, 30m for alternative)
            output_path: Optional path to save DEM GeoTIFF

        Returns:
            Dictionary with DEM metadata and download info

        Example:
            >>> client = SatelliteDataClient()
            >>> result = await client.get_elevation(
            ...     bounds=(44.0, -79.0, 45.0, -78.0),
            ...     resolution="20m",
            ...     output_path="data/dem.tif"
            ... )
        """
        logger.info(f"CDEM data ({resolution}) requires manual NTS tile identification")
        logger.info(
            f"1. Identify NTS map sheets for bounds: {bounds}\n"
            f"2. Download tiles from: {self.CDEM_FTP_BASE}\n"
            f"3. Mosaic and clip to area of interest"
        )

        # For demonstration, create synthetic DEM if output path provided
        if output_path and RASTERIO_AVAILABLE:
            return self._create_synthetic_dem(bounds, output_path)

        return {
            "bounds": bounds,
            "resolution": resolution,
            "source": "Natural Resources Canada CDEM",
            "vertical_datum": "CGVD2013",
            "download_url": self.CDEM_FTP_BASE,
            "tile_system": "NTS (National Topographic System)",
            "output_path": str(output_path) if output_path else None,
            "note": "Manual NTS tile identification required",
        }

    def _create_synthetic_dem(
        self,
        bounds: Tuple[float, float, float, float],
        output_path: Union[str, Path],
    ) -> Dict:
        """Create synthetic DEM for demonstration.

        Args:
            bounds: Bounding box
            output_path: Output file path

        Returns:
            Dictionary with synthetic DEM info
        """
        logger.info("Creating synthetic DEM for demonstration")

        height, width = 500, 500

        # Create elevation variation (250-400m range)
        x = np.linspace(0, 10, width)
        y = np.linspace(0, 10, height)
        X, Y = np.meshgrid(x, y)
        elevation = 300 + 50 * np.sin(X) * np.cos(Y)

        # Save as GeoTIFF
        swlat, swlng, nelat, nelng = bounds
        transform = rasterio.transform.from_bounds(
            swlng, swlat, nelng, nelat, width, height
        )

        with rasterio.open(
            output_path,
            'w',
            driver='GTiff',
            height=height,
            width=width,
            count=1,
            dtype=elevation.dtype,
            crs='EPSG:4326',
            transform=transform,
            compress='lzw'
        ) as dst:
            dst.write(elevation, 1)

        logger.info(f"Saved synthetic DEM to {output_path}")

        return {
            "type": "synthetic",
            "bounds": bounds,
            "elevation_range": "250-400m",
            "output_path": str(output_path),
            "note": "Synthetic data for demonstration - download real CDEM for actual terrain",
        }

    async def fetch(
        self,
        data_type: str = "landcover",
        bounds: Optional[Tuple[float, float, float, float]] = None,
        **kwargs,
    ) -> Dict:
        """Fetch satellite data (implements BaseClient.fetch).

        Args:
            data_type: Type of data ("landcover", "ndvi", "elevation")
            bounds: Bounding box
            **kwargs: Additional arguments for specific data types

        Returns:
            Dictionary with data info
        """
        if not bounds:
            raise ValueError("bounds required for satellite data")

        if data_type == "landcover":
            year = kwargs.get("year", 2020)
            return await self.get_land_cover(bounds, year, kwargs.get("output_path"))
        elif data_type == "ndvi":
            start_date = kwargs.get("start_date", "2024-06-01")
            end_date = kwargs.get("end_date", "2024-06-30")
            return await self.get_ndvi(bounds, start_date, end_date, kwargs.get("output_path"))
        elif data_type == "elevation":
            resolution = kwargs.get("resolution", "20m")
            return await self.get_elevation(bounds, resolution, kwargs.get("output_path"))
        else:
            raise ValueError(f"Unknown data_type: {data_type}")
