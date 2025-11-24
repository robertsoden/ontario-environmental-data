#!/usr/bin/env python3
"""
Convert processed GeoTIFF rasters to PMTiles for web serving.

This script:
1. Downloads GeoTIFF files from S3
2. Converts them to vector tiles (polygonized and classified)
3. Generates PMTiles format
4. Uploads PMTiles to S3

Requires: gdal, tippecanoe, awscli
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
WORK_DIR = Path.home() / "pmtiles_processing"
DOWNLOAD_DIR = WORK_DIR / "downloads"
VECTOR_DIR = WORK_DIR / "vectors"
TILES_DIR = WORK_DIR / "tiles"

# S3 configuration
S3_BUCKET = "ontario-environmental-data"
S3_RASTER_PATH = "datasets/satellite"
S3_TILES_PATH = "tiles"


def setup_directories():
    """Create working directory structure."""
    logger.info("Setting up directories...")
    for d in [WORK_DIR, DOWNLOAD_DIR, VECTOR_DIR, TILES_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def download_from_s3(s3_key: str, local_path: Path):
    """Download a file from S3."""
    logger.info(f"Downloading s3://{S3_BUCKET}/{s3_key}...")
    cmd = ["aws", "s3", "cp", f"s3://{S3_BUCKET}/{s3_key}", str(local_path)]
    subprocess.run(cmd, check=True)
    logger.info(f"Downloaded to {local_path}")


def upload_to_s3(local_path: Path, s3_key: str):
    """Upload a file to S3."""
    logger.info(f"Uploading {local_path.name} to S3...")
    cmd = [
        "aws", "s3", "cp",
        str(local_path),
        f"s3://{S3_BUCKET}/{s3_key}",
        "--storage-class", "INTELLIGENT_TIERING",
        "--content-type", "application/x-protobuf",
        "--metadata", "format=pmtiles"
    ]
    subprocess.run(cmd, check=True)
    logger.info(f"Uploaded to s3://{S3_BUCKET}/{s3_key}")


def polygonize_raster(input_raster: Path, output_geojson: Path, field_name: str = "value"):
    """Convert raster to vector polygons using gdal_polygonize."""
    logger.info(f"Polygonizing {input_raster.name}...")

    cmd = [
        "gdal_polygonize.py",
        str(input_raster),
        str(output_geojson),
        "-f", "GeoJSON",
        "-b", "1",
        field_name
    ]

    subprocess.run(cmd, check=True)
    logger.info(f"Created vector file: {output_geojson}")


def create_pmtiles(input_geojson: Path, output_pmtiles: Path, layer_name: str,
                   min_zoom: int = 4, max_zoom: int = 12):
    """Create PMTiles from GeoJSON using tippecanoe."""
    logger.info(f"Creating PMTiles for {layer_name}...")

    cmd = [
        "tippecanoe",
        "-o", str(output_pmtiles),
        "-l", layer_name,
        "-z", str(max_zoom),
        "-Z", str(min_zoom),
        "--force",
        "--drop-densest-as-needed",
        "--extend-zooms-if-still-dropping",
        str(input_geojson)
    ]

    subprocess.run(cmd, check=True)

    size_mb = output_pmtiles.stat().st_size / (1024 * 1024)
    logger.info(f"Created PMTiles: {output_pmtiles} ({size_mb:.1f} MB)")


def process_landcover():
    """Process land cover 2020 data."""
    logger.info("=" * 80)
    logger.info("PROCESSING LAND COVER 2020")
    logger.info("=" * 80)

    # Download
    s3_key = f"{S3_RASTER_PATH}/landcover/ontario_landcover_2020.tif"
    local_raster = DOWNLOAD_DIR / "landcover_2020.tif"
    download_from_s3(s3_key, local_raster)

    # Polygonize
    vector_file = VECTOR_DIR / "landcover_2020.geojson"
    polygonize_raster(local_raster, vector_file, "class_id")

    # Create PMTiles
    pmtiles_file = TILES_DIR / "ontario_landcover_2020.pmtiles"
    create_pmtiles(vector_file, pmtiles_file, "landcover", min_zoom=4, max_zoom=14)

    # Upload
    s3_tiles_key = f"{S3_TILES_PATH}/ontario_landcover_2020.pmtiles"
    upload_to_s3(pmtiles_file, s3_tiles_key)

    # Cleanup
    logger.info("Cleaning up land cover files...")
    local_raster.unlink()
    vector_file.unlink()

    return s3_tiles_key


def process_ndvi():
    """Process NDVI 2024 data."""
    logger.info("=" * 80)
    logger.info("PROCESSING NDVI 2024")
    logger.info("=" * 80)

    # Download
    s3_key = f"{S3_RASTER_PATH}/ndvi/ontario_ndvi_2024_250m.tif"
    local_raster = DOWNLOAD_DIR / "ndvi_2024.tif"
    download_from_s3(s3_key, local_raster)

    # Polygonize
    vector_file = VECTOR_DIR / "ndvi_2024.geojson"
    polygonize_raster(local_raster, vector_file, "ndvi_value")

    # Create PMTiles
    pmtiles_file = TILES_DIR / "ontario_ndvi_2024.pmtiles"
    create_pmtiles(vector_file, pmtiles_file, "ndvi", min_zoom=4, max_zoom=12)

    # Upload
    s3_tiles_key = f"{S3_TILES_PATH}/ontario_ndvi_2024.pmtiles"
    upload_to_s3(pmtiles_file, s3_tiles_key)

    # Cleanup
    logger.info("Cleaning up NDVI files...")
    local_raster.unlink()
    vector_file.unlink()

    return s3_tiles_key


def main():
    """Main processing workflow."""
    logger.info("=" * 80)
    logger.info("PMTILES CONVERSION - ONTARIO SATELLITE DATA")
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
    logger.info("PMTILES CONVERSION COMPLETE")
    logger.info("=" * 80)

    for name, s3_key in results.items():
        if s3_key:
            logger.info(f"{name}: s3://{S3_BUCKET}/{s3_key}")
        else:
            logger.error(f"{name}: FAILED")


if __name__ == "__main__":
    main()
