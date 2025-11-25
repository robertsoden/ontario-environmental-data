#!/usr/bin/env python3
"""
Download and process NALCMS land cover data for Ontario (2010, 2015).

Downloads land cover classification from Natural Resources Canada,
clips to Ontario boundary, and uploads to S3.

Data source: https://opendata.nfis.org/mapserver/nfis-change_eng.html
NALCMS (North American Land Change Monitoring System)
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
WORK_DIR = Path.home() / "landcover_processing"
DOWNLOAD_DIR = WORK_DIR / "downloads"
PROCESSED_DIR = WORK_DIR / "processed"
BOUNDARY_DIR = WORK_DIR / "boundaries"

# S3 configuration
S3_BUCKET = "ontario-environmental-data"
S3_LANDCOVER_PATH = "datasets/satellite/landcover"

# Data URLs - NALCMS from Natural Resources Canada
# 30m resolution land cover
LANDCOVER_URLS = {
    "2010": "https://datacube-prod-data-public.s3.ca-central-1.amazonaws.com/store/land/landcover/landcover-2010-classification.tif",
    "2015": "https://datacube-prod-data-public.s3.ca-central-1.amazonaws.com/store/land/landcover/landcover-2015-classification.tif",
}

# Ontario boundary from StatCan
ONTARIO_BOUNDARY_URL = "https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/files-fichiers/lpr_000a21a_e.zip"


def setup_directories():
    """Create working directory structure."""
    logger.info("Setting up directories...")
    for d in [WORK_DIR, DOWNLOAD_DIR, PROCESSED_DIR, BOUNDARY_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def download_file(url: str, output_path: Path):
    """Download a file using curl."""
    logger.info(f"Downloading {url}...")
    cmd = ["curl", "-L", "-o", str(output_path), url]
    subprocess.run(cmd, check=True)
    logger.info(f"Downloaded to {output_path}")


def get_ontario_boundary():
    """Download and prepare Ontario boundary for clipping."""
    logger.info("Preparing Ontario boundary...")

    boundary_zip = BOUNDARY_DIR / "ontario_boundary.zip"

    if not boundary_zip.exists():
        download_file(ONTARIO_BOUNDARY_URL, boundary_zip)

        # Unzip
        logger.info("Extracting boundary data...")
        subprocess.run(["unzip", "-o", str(boundary_zip), "-d", str(BOUNDARY_DIR)], check=True)

    # Find the shapefile for Ontario (province code 35)
    shapefile = BOUNDARY_DIR / "lpr_000a21a_e.shp"

    if not shapefile.exists():
        raise FileNotFoundError(f"Boundary shapefile not found: {shapefile}")

    # Extract Ontario and reproject to match raster (likely EPSG:3978 or similar)
    ontario_boundary = BOUNDARY_DIR / "ontario.shp"

    if not ontario_boundary.exists():
        logger.info("Extracting Ontario boundary...")
        cmd = [
            "ogr2ogr",
            "-f", "ESRI Shapefile",
            str(ontario_boundary),
            str(shapefile),
            "-where", "PRUID='35'",  # Ontario province code
        ]
        subprocess.run(cmd, check=True)

    return ontario_boundary


def clip_to_ontario(input_raster: Path, output_raster: Path, boundary: Path):
    """Clip raster to Ontario boundary."""
    logger.info(f"Clipping {input_raster.name} to Ontario boundary...")

    cmd = [
        "gdalwarp",
        "-cutline", str(boundary),
        "-crop_to_cutline",
        "-dstnodata", "0",
        "-co", "COMPRESS=LZW",
        "-co", "TILED=YES",
        "-co", "BLOCKXSIZE=512",
        "-co", "BLOCKYSIZE=512",
        "-co", "BIGTIFF=YES",
        str(input_raster),
        str(output_raster)
    ]

    subprocess.run(cmd, check=True)

    size_mb = output_raster.stat().st_size / (1024 * 1024)
    logger.info(f"Clipped raster: {output_raster.name} ({size_mb:.1f} MB)")


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
    logger.info(f"Uploaded to s3://{S3_BUCKET}/{s3_key}")


def process_year(year: str, boundary: Path):
    """Process land cover data for a specific year."""
    logger.info("=" * 80)
    logger.info(f"PROCESSING LAND COVER {year}")
    logger.info("=" * 80)

    url = LANDCOVER_URLS[year]

    # Download
    download_file_path = DOWNLOAD_DIR / f"landcover_{year}_raw.tif"
    if not download_file_path.exists():
        download_file(url, download_file_path)
    else:
        logger.info(f"Using cached download: {download_file_path}")

    # Clip to Ontario
    clipped_file = PROCESSED_DIR / f"ontario_landcover_{year}.tif"
    clip_to_ontario(download_file_path, clipped_file, boundary)

    # Upload to S3
    s3_key = f"{S3_LANDCOVER_PATH}/ontario_landcover_{year}.tif"
    upload_to_s3(clipped_file, s3_key)

    return s3_key


def main():
    """Main processing workflow."""
    logger.info("=" * 80)
    logger.info("NALCMS LAND COVER TIME SERIES - ONTARIO")
    logger.info("=" * 80)

    setup_directories()

    # Get Ontario boundary
    ontario_boundary = get_ontario_boundary()

    results = {}

    # Process each year
    for year in ["2010", "2015"]:
        try:
            results[year] = process_year(year, ontario_boundary)
        except Exception as e:
            logger.error(f"Failed to process {year}: {e}")
            results[year] = None

    # Summary
    logger.info("=" * 80)
    logger.info("LAND COVER PROCESSING COMPLETE")
    logger.info("=" * 80)

    for year, s3_key in results.items():
        if s3_key:
            logger.info(f"{year}: s3://{S3_BUCKET}/{s3_key}")
        else:
            logger.error(f"{year}: FAILED")

    logger.info("")
    logger.info("Next step: Run COG conversion to add overviews")


if __name__ == "__main__":
    main()
