#!/usr/bin/env python3
"""
Create a single-band NDVI composite from multi-band time-series data.

Takes the maximum NDVI value across all time periods to get peak vegetation,
then converts to 8-bit for Mapbox upload.

The input 23-band NDVI files contain MODIS 16-day composites (~23 periods/year).
MODIS NDVI is scaled: actual_ndvi = (pixel_value - 10000) / 10000
So pixel values of 0-20000 map to NDVI of -1.0 to 1.0
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path
import tempfile

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_max_composite(input_file: Path, output_file: Path):
    """Create maximum NDVI composite from multi-band file."""
    try:
        import rasterio
        from rasterio.enums import Resampling
    except ImportError:
        logger.error("rasterio not installed. Run: pip install rasterio")
        sys.exit(1)

    logger.info(f"Reading {input_file}...")

    with rasterio.open(input_file) as src:
        logger.info(f"  Bands: {src.count}")
        logger.info(f"  Size: {src.width} x {src.height}")
        logger.info(f"  CRS: {src.crs}")
        logger.info(f"  Data type: {src.dtypes[0]}")

        # Read all bands and find max
        logger.info("Computing maximum NDVI across all bands...")
        max_ndvi = None

        for band_idx in range(1, src.count + 1):
            band_data = src.read(band_idx).astype(np.float32)
            # Mask out nodata/fill values (0 is typically fill for MODIS NDVI)
            band_data[band_data == 0] = np.nan

            if max_ndvi is None:
                max_ndvi = band_data
            else:
                max_ndvi = np.fmax(max_ndvi, band_data)

            if band_idx % 5 == 0:
                logger.info(f"  Processed band {band_idx}/{src.count}")

        # Fill any remaining NaN with 0
        max_ndvi = np.nan_to_num(max_ndvi, nan=0)

        # Get stats
        valid_mask = max_ndvi > 0
        if valid_mask.any():
            logger.info(f"  Min: {max_ndvi[valid_mask].min()}")
            logger.info(f"  Max: {max_ndvi[valid_mask].max()}")
            logger.info(f"  Mean: {max_ndvi[valid_mask].mean():.1f}")

        # MODIS NDVI scaling: raw values 0-20000 map to NDVI -1 to 1
        # For 8-bit: we'll scale to 0-255 where 0=nodata, 1-255 = NDVI range
        # NDVI -1 to 1 -> 1 to 255 (reserve 0 for nodata)
        logger.info("Scaling to 8-bit...")

        # First convert raw MODIS to actual NDVI (-1 to 1)
        # MODIS formula: NDVI = (raw - 10000) / 10000
        ndvi_actual = (max_ndvi - 10000) / 10000.0

        # Scale NDVI (-1 to 1) to 8-bit (1 to 255, 0 = nodata)
        # NDVI -1 -> 1, NDVI 1 -> 255
        ndvi_8bit = ((ndvi_actual + 1) / 2 * 254 + 1).astype(np.uint8)
        ndvi_8bit[max_ndvi == 0] = 0  # Keep nodata as 0

        # Update profile for single-band 8-bit output
        profile = src.profile.copy()
        profile.update(
            dtype=rasterio.uint8,
            count=1,
            compress='lzw',
            tiled=True,
            blockxsize=512,
            blockysize=512,
            nodata=0
        )

        # Write output
        logger.info(f"Writing {output_file}...")
        with rasterio.open(output_file, 'w', **profile) as dst:
            dst.write(ndvi_8bit, 1)
            dst.set_band_description(1, "Max NDVI (8-bit scaled: 1-255 = NDVI -1 to 1)")

    size_mb = output_file.stat().st_size / (1024 * 1024)
    logger.info(f"Created {output_file.name} ({size_mb:.1f} MB)")


def reproject_to_wgs84(input_file: Path, output_file: Path):
    """Reproject to WGS84 for Mapbox."""
    logger.info("Reprojecting to WGS84...")
    cmd = [
        "gdalwarp",
        "-t_srs", "EPSG:4326",
        "-r", "bilinear",
        "-co", "COMPRESS=LZW",
        "-co", "TILED=YES",
        str(input_file),
        str(output_file)
    ]
    subprocess.run(cmd, check=True)

    size_mb = output_file.stat().st_size / (1024 * 1024)
    logger.info(f"Created {output_file.name} ({size_mb:.1f} MB)")


def main():
    parser = argparse.ArgumentParser(
        description="Create 8-bit max NDVI composite from time-series"
    )
    parser.add_argument("--input", type=Path, required=True,
                        help="Input multi-band NDVI file")
    parser.add_argument("--output", type=Path, required=True,
                        help="Output single-band 8-bit file")
    parser.add_argument("--reproject", action="store_true",
                        help="Also reproject to WGS84")
    args = parser.parse_args()

    if not args.input.exists():
        logger.error(f"Input file not found: {args.input}")
        sys.exit(1)

    args.output.parent.mkdir(parents=True, exist_ok=True)

    # Create composite
    if args.reproject:
        # Create in native CRS first, then reproject
        with tempfile.NamedTemporaryFile(suffix='.tif', delete=False) as tmp:
            tmp_path = Path(tmp.name)

        create_max_composite(args.input, tmp_path)
        reproject_to_wgs84(tmp_path, args.output)
        tmp_path.unlink()
    else:
        create_max_composite(args.input, args.output)

    logger.info("Done!")


if __name__ == "__main__":
    main()
