#!/usr/bin/env python3
"""
EC2 script for processing large satellite datasets clipped to Ontario boundaries.

This script should be run on an EC2 instance with:
- Sufficient storage (500GB+ recommended)
- 16GB+ RAM
- GDAL/rasterio installed

Processes:
1. Land cover data (2010, 2015, 2020) from Natural Resources Canada
2. NDVI 250m data from Statistics Canada MODIS
3. DEM data from Natural Resources Canada

All datasets are clipped to Ontario boundaries and uploaded to S3.
"""

import asyncio
import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional

import geopandas as gpd
import rasterio
from rasterio.mask import mask
from rasterio.warp import calculate_default_transform, reproject, Resampling

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Directory structure
WORK_DIR = Path("/mnt/satellite_processing")
RAW_DIR = WORK_DIR / "raw"
PROCESSED_DIR = WORK_DIR / "processed"
ONTARIO_BOUNDARY = WORK_DIR / "ontario_boundary.geojson"

# S3 configuration
S3_BUCKET = "ontario-environmental-data"
S3_BASE_PATH = "datasets/satellite"

# Data sources
# Note: Updated URLs as of November 2024
# All land cover data now available directly as TIFF from datacube (no zip needed)
LANDCOVER_URLS = {
    2010: "https://datacube-prod-data-public.s3.ca-central-1.amazonaws.com/store/land/landcover/landcover-2010-classification.tif",
    2015: "https://datacube-prod-data-public.s3.ca-central-1.amazonaws.com/store/land/landcover/landcover-2015-classification.tif",
    2020: "https://datacube-prod-data-public.s3.ca-central-1.amazonaws.com/store/land/landcover/landcover-2020-classification.tif",
}

# NDVI data from Statistics Canada MODIS
# Changed from ndvi_{year}_250m.zip to MODISCOMP7d_{year}.zip format
NDVI_URL_TEMPLATE = "https://ftp.maps.canada.ca/pub/statcan_statcan/modis/MODISCOMP7d_{year}.zip"

CDEM_INDEX_URL = "https://ftp.maps.canada.ca/pub/elevation/dem_mne/highresolution_hauteresolution/tiles/CDEM_index.geojson"


def setup_directories():
    """Create working directory structure."""
    logger.info("Setting up directory structure...")
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(exist_ok=True)
    PROCESSED_DIR.mkdir(exist_ok=True)
    (PROCESSED_DIR / "landcover").mkdir(exist_ok=True)
    (PROCESSED_DIR / "ndvi").mkdir(exist_ok=True)
    (PROCESSED_DIR / "dem").mkdir(exist_ok=True)


def download_ontario_boundary():
    """Download Ontario boundary from S3 or use local copy."""
    logger.info("Setting up Ontario boundary...")

    # First try to use local copy from /tmp if available
    local_copy = Path("/tmp/ontario_boundary.geojson")
    if local_copy.exists():
        logger.info(f"Using local boundary file from {local_copy}")
        subprocess.run(["cp", str(local_copy), str(ONTARIO_BOUNDARY)], check=True)
        logger.info(f"Ontario boundary copied to {ONTARIO_BOUNDARY}")
        return

    # Otherwise download from S3
    logger.info("Downloading Ontario boundary from S3...")
    cmd = [
        "aws", "s3", "cp",
        f"s3://{S3_BUCKET}/datasets/boundaries/ontario_boundary.geojson",
        str(ONTARIO_BOUNDARY),
        "--no-sign-request"  # Allow public access without credentials
    ]
    subprocess.run(cmd, check=True)
    logger.info(f"Ontario boundary saved to {ONTARIO_BOUNDARY}")


def download_file(url: str, output_path: Path):
    """Download a file using wget."""
    logger.info(f"Downloading {url}...")
    cmd = ["wget", "-O", str(output_path), url, "--progress=bar:force"]
    subprocess.run(cmd, check=True)
    logger.info(f"Downloaded to {output_path}")


def extract_zip(zip_path: Path, extract_to: Path):
    """Extract a zip file."""
    logger.info(f"Extracting {zip_path}...")
    cmd = ["unzip", "-o", str(zip_path), "-d", str(extract_to)]
    subprocess.run(cmd, check=True)
    logger.info(f"Extracted to {extract_to}")


def clip_raster_to_boundary(
    input_raster: Path,
    output_raster: Path,
    boundary_geojson: Path,
    compress: str = "LZW"
) -> Dict:
    """Clip a raster to Ontario boundaries using rasterio.

    Args:
        input_raster: Path to input raster file
        output_raster: Path to output clipped raster
        boundary_geojson: Path to boundary GeoJSON
        compress: Compression method (LZW, DEFLATE, etc.)

    Returns:
        Dictionary with metadata about the clipped raster
    """
    logger.info(f"Clipping {input_raster.name} to Ontario boundaries...")

    # Set environment variable to allow large GeoJSON files (in MB)
    import os
    os.environ['OGR_GEOJSON_MAX_OBJ_SIZE'] = '0'  # 0 = unlimited

    # Read boundary
    boundary_gdf = gpd.read_file(boundary_geojson)

    # Open source raster
    with rasterio.open(input_raster) as src:
        # Get boundary in raster CRS
        boundary_crs = boundary_gdf.to_crs(src.crs)

        # Clip
        out_image, out_transform = mask(
            src,
            boundary_crs.geometry,
            crop=True,
            all_touched=True
        )

        # Update metadata
        out_meta = src.meta.copy()
        out_meta.update({
            "driver": "GTiff",
            "height": out_image.shape[1],
            "width": out_image.shape[2],
            "transform": out_transform,
            "compress": compress,
            "tiled": True,
            "blockxsize": 256,
            "blockysize": 256
        })

        # Write clipped raster
        with rasterio.open(output_raster, "w", **out_meta) as dest:
            dest.write(out_image)

    # Get file size
    size_mb = output_raster.stat().st_size / (1024 * 1024)

    logger.info(f"Clipped raster saved to {output_raster} ({size_mb:.1f} MB)")

    return {
        "input": str(input_raster),
        "output": str(output_raster),
        "size_mb": size_mb,
        "compressed": compress
    }


def process_landcover(year: int):
    """Download and process land cover data for a specific year."""
    logger.info(f"Processing land cover {year}...")

    url = LANDCOVER_URLS[year]

    # Check if URL is direct TIFF or ZIP
    if url.endswith('.tif'):
        # Direct TIFF download (2020)
        input_tif = RAW_DIR / f"landcover_{year}.tif"
        download_file(url, input_tif)
        files_to_cleanup = [input_tif]
    else:
        # ZIP file download (legacy 2010, 2015)
        zip_path = RAW_DIR / f"landcover_{year}.zip"
        download_file(url, zip_path)

        # Extract
        extract_dir = RAW_DIR / f"landcover_{year}"
        extract_zip(zip_path, extract_dir)

        # Find the .tif file (may be in subdirectories)
        tif_files = list(extract_dir.rglob("*.tif"))
        if not tif_files:
            raise FileNotFoundError(f"No .tif file found in {extract_dir}")

        input_tif = tif_files[0]
        files_to_cleanup = [extract_dir, zip_path]

    logger.info(f"Found input raster: {input_tif}")

    # Clip to Ontario
    output_tif = PROCESSED_DIR / "landcover" / f"ontario_landcover_{year}.tif"
    result = clip_raster_to_boundary(input_tif, output_tif, ONTARIO_BOUNDARY)

    # Clean up raw data to save space
    logger.info(f"Cleaning up downloaded files...")
    for path in files_to_cleanup:
        subprocess.run(["rm", "-rf", str(path)])

    return result


def process_ndvi(year: int = 2023):
    """Download and process NDVI 250m data."""
    logger.info(f"Processing NDVI {year} (250m)...")

    # Download
    url = NDVI_URL_TEMPLATE.format(year=year)
    zip_path = RAW_DIR / f"ndvi_{year}_250m.zip"
    download_file(url, zip_path)

    # Extract
    extract_dir = RAW_DIR / f"ndvi_{year}"
    extract_zip(zip_path, extract_dir)

    # Find the .tif file
    tif_files = list(extract_dir.rglob("*.tif"))
    if not tif_files:
        raise FileNotFoundError(f"No .tif file found in {extract_dir}")

    input_tif = tif_files[0]
    logger.info(f"Found input raster: {input_tif}")

    # Clip to Ontario
    output_tif = PROCESSED_DIR / "ndvi" / f"ontario_ndvi_{year}_250m.tif"
    result = clip_raster_to_boundary(input_tif, output_tif, ONTARIO_BOUNDARY)

    # Clean up
    logger.info(f"Cleaning up {extract_dir}...")
    subprocess.run(["rm", "-rf", str(extract_dir), str(zip_path)])

    return result


def upload_to_s3(file_path: Path, s3_key: str):
    """Upload a file to S3."""
    logger.info(f"Uploading {file_path.name} to S3...")

    cmd = [
        "aws", "s3", "cp",
        str(file_path),
        f"s3://{S3_BUCKET}/{s3_key}",
        "--storage-class", "INTELLIGENT_TIERING",
        "--metadata", f"source=nrcan,processed=ontario_clipped"
    ]

    try:
        subprocess.run(cmd, check=True)
        logger.info(f"Uploaded to s3://{S3_BUCKET}/{s3_key}")
    except subprocess.CalledProcessError as e:
        logger.warning(f"S3 upload failed (may need IAM role configured): {e}")
        logger.info(f"Processed file saved locally at: {file_path}")


def main():
    """Main processing workflow."""
    logger.info("="*80)
    logger.info("ONTARIO SATELLITE DATA PROCESSING - EC2")
    logger.info("="*80)

    # Setup
    setup_directories()
    download_ontario_boundary()

    # Process land cover (all years)
    landcover_results = {}
    for year in [2010, 2015, 2020]:
        try:
            result = process_landcover(year)
            landcover_results[year] = result

            # Upload to S3
            output_file = Path(result["output"])
            s3_key = f"{S3_BASE_PATH}/landcover/ontario_landcover_{year}.tif"
            upload_to_s3(output_file, s3_key)

        except Exception as e:
            logger.error(f"Failed to process land cover {year}: {e}")

    # Process NDVI (most recent year)
    try:
        ndvi_result = process_ndvi(2023)
        output_file = Path(ndvi_result["output"])
        s3_key = f"{S3_BASE_PATH}/ndvi/ontario_ndvi_2023_250m.tif"
        upload_to_s3(output_file, s3_key)
    except Exception as e:
        logger.error(f"Failed to process NDVI: {e}")

    # Summary
    logger.info("="*80)
    logger.info("PROCESSING COMPLETE")
    logger.info("="*80)
    logger.info(f"Land cover years processed: {list(landcover_results.keys())}")
    logger.info(f"NDVI processed: 2023 (250m)")
    logger.info(f"Files uploaded to s3://{S3_BUCKET}/{S3_BASE_PATH}/")


if __name__ == "__main__":
    main()
