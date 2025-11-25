#!/usr/bin/env python3
"""
Create color-styled raster tiles for Mapbox upload.

Applies color ramps to raw satellite data:
- NDVI: Green gradient (-1 to 1)
- Land Cover: NALCMS categorical colors

Output: Color-rendered GeoTIFFs ready for Mapbox upload
"""

import logging
import subprocess
import sys
from pathlib import Path
import tempfile

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Directories
WORK_DIR = Path.home() / "styled_tiles"
DOWNLOAD_DIR = WORK_DIR / "downloads"
STYLED_DIR = WORK_DIR / "styled"

# S3 configuration
S3_BUCKET = "ontario-environmental-data"

# NDVI color ramp (green gradient for vegetation health)
# Values range from -1 (water/bare) to 1 (dense vegetation)
NDVI_COLOR_RAMP = """
-1.0 165 0 38
-0.5 215 48 39
-0.2 244 109 67
0.0 253 174 97
0.1 254 224 139
0.2 217 239 139
0.3 166 217 106
0.4 102 189 99
0.5 26 152 80
0.7 0 104 55
1.0 0 68 27
nv 0 0 0 0
"""

# NALCMS Land Cover classification colors
# https://www.mrlc.gov/data/legends/north-american-land-change-monitoring-system
LANDCOVER_COLOR_RAMP = """
1 0 61 0
2 0 99 0
3 0 128 0
4 20 79 20
5 40 100 40
6 80 120 80
7 0 150 0
8 200 200 50
9 170 200 60
10 100 170 60
11 205 205 102
12 0 200 255
13 150 200 200
14 255 255 0
15 255 155 0
16 255 0 0
17 170 170 170
18 200 200 200
19 0 0 255
nv 0 0 0 0
"""


def setup_directories():
    """Create working directory structure."""
    logger.info("Setting up directories...")
    for d in [WORK_DIR, DOWNLOAD_DIR, STYLED_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def download_from_s3(s3_key: str, local_path: Path):
    """Download a file from S3."""
    if local_path.exists():
        logger.info(f"Using cached: {local_path.name}")
        return

    logger.info(f"Downloading s3://{S3_BUCKET}/{s3_key}...")
    cmd = ["aws", "s3", "cp", f"s3://{S3_BUCKET}/{s3_key}", str(local_path)]
    subprocess.run(cmd, check=True)

    size_mb = local_path.stat().st_size / (1024 * 1024)
    logger.info(f"Downloaded {local_path.name} ({size_mb:.1f} MB)")


def apply_color_ramp(input_tif: Path, output_tif: Path, color_ramp: str):
    """
    Apply a color ramp to a raster using gdaldem color-relief.

    Args:
        input_tif: Input single-band GeoTIFF
        output_tif: Output RGB GeoTIFF
        color_ramp: Color ramp text (value R G B format)
    """
    logger.info(f"Applying color ramp to {input_tif.name}...")

    # Write color ramp to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(color_ramp.strip())
        color_file = f.name

    try:
        cmd = [
            "gdaldem", "color-relief",
            str(input_tif),
            color_file,
            str(output_tif),
            "-alpha",  # Add alpha band for transparency
            "-co", "COMPRESS=LZW",
            "-co", "TILED=YES",
        ]

        subprocess.run(cmd, check=True)

        size_mb = output_tif.stat().st_size / (1024 * 1024)
        logger.info(f"Created styled raster: {output_tif.name} ({size_mb:.1f} MB)")

    finally:
        Path(color_file).unlink()


def upload_to_mapbox(tif_path: Path, tileset_name: str, mapbox_token: str, mapbox_username: str):
    """Upload a styled GeoTIFF to Mapbox as a tileset source."""
    logger.info(f"Uploading {tif_path.name} to Mapbox as {tileset_name}...")

    # Upload as tileset source
    cmd = [
        "curl", "-X", "POST",
        f"https://api.mapbox.com/tilesets/v1/sources/{mapbox_username}/{tileset_name}?access_token={mapbox_token}",
        "-F", f"file=@{tif_path}",
        "-F", f"name={tileset_name}"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    logger.info(f"Upload response: {result.stdout}")

    if result.returncode != 0:
        logger.error(f"Upload error: {result.stderr}")
        return False

    return True


def main():
    """Main processing workflow."""
    import argparse

    parser = argparse.ArgumentParser(description="Create styled satellite tilesets")
    parser.add_argument("--mapbox-token", help="Mapbox secret token")
    parser.add_argument("--mapbox-username", default="robertsoden", help="Mapbox username")
    parser.add_argument("--upload", action="store_true", help="Upload to Mapbox after styling")
    parser.add_argument("--dataset", choices=["ndvi", "landcover_2010", "landcover_2015", "landcover_2020", "all"],
                        default="all", help="Which dataset to process")
    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("STYLED TILESET GENERATION")
    logger.info("=" * 80)

    setup_directories()

    # Dataset configurations
    datasets = {
        "ndvi": {
            "s3_key": "datasets/satellite/ndvi/ontario_ndvi_2024_250m.tif",
            "color_ramp": NDVI_COLOR_RAMP,
            "tileset_name": "ndvi-2024-styled"
        },
        "landcover_2020": {
            "s3_key": "datasets/satellite/landcover/ontario_landcover_2020.tif",
            "color_ramp": LANDCOVER_COLOR_RAMP,
            "tileset_name": "landcover-2020-styled"
        },
        "landcover_2015": {
            "s3_key": "datasets/satellite/landcover/ontario_landcover_2015.tif",
            "color_ramp": LANDCOVER_COLOR_RAMP,
            "tileset_name": "landcover-2015-styled"
        },
        "landcover_2010": {
            "s3_key": "datasets/satellite/landcover/ontario_landcover_2010.tif",
            "color_ramp": LANDCOVER_COLOR_RAMP,
            "tileset_name": "landcover-2010-styled"
        }
    }

    # Filter datasets
    if args.dataset != "all":
        datasets = {args.dataset: datasets[args.dataset]}

    for name, config in datasets.items():
        logger.info(f"\n{'=' * 40}")
        logger.info(f"Processing: {name}")
        logger.info(f"{'=' * 40}")

        # Download
        local_tif = DOWNLOAD_DIR / f"{name}.tif"
        download_from_s3(config["s3_key"], local_tif)

        # Apply color ramp
        styled_tif = STYLED_DIR / f"{name}_styled.tif"
        apply_color_ramp(local_tif, styled_tif, config["color_ramp"])

        # Upload to Mapbox if requested
        if args.upload:
            if not args.mapbox_token:
                logger.error("--mapbox-token required for upload")
                continue

            upload_to_mapbox(
                styled_tif,
                config["tileset_name"],
                args.mapbox_token,
                args.mapbox_username
            )

    logger.info("\n" + "=" * 80)
    logger.info("PROCESSING COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Styled files in: {STYLED_DIR}")

    if not args.upload:
        logger.info("\nTo upload to Mapbox, run with --upload --mapbox-token YOUR_TOKEN")


if __name__ == "__main__":
    main()
