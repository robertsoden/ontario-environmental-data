#!/usr/bin/env python3
"""
Convert existing GeoTIFF files to Cloud Optimized GeoTIFFs (COG).

This script:
1. Downloads GeoTIFF files from S3
2. Converts them to COG format with overviews
3. Uploads COG files back to S3

Requires: gdal (gdal_translate)
"""

import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Directories
WORK_DIR = Path.home() / "cog_processing"
DOWNLOAD_DIR = WORK_DIR / "downloads"
COG_DIR = WORK_DIR / "cog_output"

# S3 configuration
S3_BUCKET = "ontario-environmental-data"
S3_SATELLITE_PATH = "datasets/satellite"


def setup_directories():
    """Create working directory structure."""
    logger.info("Setting up directories...")
    for d in [WORK_DIR, DOWNLOAD_DIR, COG_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def download_from_s3(s3_key: str, local_path: Path):
    """Download a file from S3."""
    logger.info(f"Downloading s3://{S3_BUCKET}/{s3_key}...")
    cmd = ["aws", "s3", "cp", f"s3://{S3_BUCKET}/{s3_key}", str(local_path)]
    subprocess.run(cmd, check=True)

    size_mb = local_path.stat().st_size / (1024 * 1024)
    logger.info(f"Downloaded {local_path.name} ({size_mb:.1f} MB)")


def upload_to_s3(local_path: Path, s3_key: str):
    """Upload a file to S3."""
    logger.info(f"Uploading {local_path.name} to S3...")
    cmd = [
        "aws", "s3", "cp",
        str(local_path),
        f"s3://{S3_BUCKET}/{s3_key}",
        "--storage-class", "INTELLIGENT_TIERING",
        "--content-type", "image/tiff"
    ]
    subprocess.run(cmd, check=True)

    size_mb = local_path.stat().st_size / (1024 * 1024)
    logger.info(f"Uploaded to s3://{S3_BUCKET}/{s3_key} ({size_mb:.1f} MB)")


def convert_to_cog(input_tif: Path, output_tif: Path, compress: str = "LZW"):
    """
    Convert GeoTIFF to Cloud Optimized GeoTIFF.

    Args:
        input_tif: Input GeoTIFF file
        output_tif: Output COG file
        compress: Compression method (LZW, DEFLATE, etc.)
    """
    logger.info(f"Converting {input_tif.name} to COG...")

    cmd = [
        "gdal_translate",
        str(input_tif),
        str(output_tif),
        "-of", "COG",
        "-co", f"COMPRESS={compress}",
        "-co", "BLOCKSIZE=512",
        "-co", "BIGTIFF=YES",
        "-co", "NUM_THREADS=ALL_CPUS",
        "-co", "OVERVIEW_RESAMPLING=NEAREST",
        "-co", "OVERVIEW_COMPRESS=LZW"
    ]

    subprocess.run(cmd, check=True)

    input_size_mb = input_tif.stat().st_size / (1024 * 1024)
    output_size_mb = output_tif.stat().st_size / (1024 * 1024)
    logger.info(f"Created COG: {output_tif.name}")
    logger.info(f"  Input:  {input_size_mb:.1f} MB")
    logger.info(f"  Output: {output_size_mb:.1f} MB")


def process_landcover():
    """Process land cover 2020 data."""
    logger.info("=" * 80)
    logger.info("PROCESSING LAND COVER 2020")
    logger.info("=" * 80)

    # Download
    s3_key = f"{S3_SATELLITE_PATH}/landcover/ontario_landcover_2020.tif"
    local_tif = DOWNLOAD_DIR / "landcover_2020.tif"
    download_from_s3(s3_key, local_tif)

    # Convert to COG
    cog_file = COG_DIR / "ontario_landcover_2020_cog.tif"
    convert_to_cog(local_tif, cog_file, compress="LZW")

    # Upload (overwrite original with COG version)
    upload_to_s3(cog_file, s3_key)

    # Cleanup
    logger.info("Cleaning up land cover files...")
    local_tif.unlink()

    return s3_key


def process_ndvi():
    """Process NDVI 2024 data."""
    logger.info("=" * 80)
    logger.info("PROCESSING NDVI 2024")
    logger.info("=" * 80)

    # Download
    s3_key = f"{S3_SATELLITE_PATH}/ndvi/ontario_ndvi_2024_250m.tif"
    local_tif = DOWNLOAD_DIR / "ndvi_2024.tif"
    download_from_s3(s3_key, local_tif)

    # Convert to COG
    cog_file = COG_DIR / "ontario_ndvi_2024_cog.tif"
    convert_to_cog(local_tif, cog_file, compress="LZW")

    # Upload (overwrite original with COG version)
    upload_to_s3(cog_file, s3_key)

    # Cleanup
    logger.info("Cleaning up NDVI files...")
    local_tif.unlink()

    return s3_key


def main():
    """Main processing workflow."""
    logger.info("=" * 80)
    logger.info("COG CONVERSION - ONTARIO SATELLITE DATA")
    logger.info("=" * 80)

    setup_directories()

    results = {}

    # Process land cover
    try:
        results["landcover"] = process_landcover()
    except Exception as e:
        logger.error(f"Failed to process land cover: {e}")
        results["landcover"] = None

    # Process NDVI
    try:
        results["ndvi"] = process_ndvi()
    except Exception as e:
        logger.error(f"Failed to process NDVI: {e}")
        results["ndvi"] = None

    # Summary
    logger.info("=" * 80)
    logger.info("COG CONVERSION COMPLETE")
    logger.info("=" * 80)

    for name, s3_key in results.items():
        if s3_key:
            logger.info(f"{name}: s3://{S3_BUCKET}/{s3_key}")
        else:
            logger.error(f"{name}: FAILED")


if __name__ == "__main__":
    main()
